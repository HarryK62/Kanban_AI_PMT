from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import BoardRepository


def make_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "app.db"
    return TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )


def test_signup_creates_account_and_returns_token(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/signup",
        json={"username": "newuser", "password": "StrongPass1!"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "newuser"
    assert isinstance(body["token"], str) and body["token"]


def test_signup_normalizes_username_case_and_whitespace(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/signup",
        json={"username": "  NewUser  ", "password": "StrongPass1!"},
    )

    assert response.status_code == 201
    assert response.json()["username"] == "newuser"


def test_signup_rejects_duplicate_username(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post(
        "/api/auth/signup",
        json={"username": "newuser", "password": "StrongPass1!"},
    )

    response = client.post(
        "/api/auth/signup",
        json={"username": "newuser", "password": "AnotherPass1!"},
    )

    assert response.status_code == 409


def test_signup_rejects_duplicate_username_case_insensitively(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post(
        "/api/auth/signup",
        json={"username": "newuser", "password": "StrongPass1!"},
    )

    response = client.post(
        "/api/auth/signup",
        json={"username": "NEWUSER", "password": "AnotherPass1!"},
    )

    assert response.status_code == 409


def test_signup_rejects_weak_password(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/signup",
        json={"username": "newuser", "password": "weak"},
    )

    assert response.status_code == 400


def test_signup_rejects_invalid_username(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/signup",
        json={"username": "a!", "password": "StrongPass1!"},
    )

    assert response.status_code == 400


def test_login_succeeds_with_seeded_default_account(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/login",
        json={"username": "harry", "password": "kijanka"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "harry"
    assert isinstance(body["token"], str) and body["token"]


def test_login_succeeds_after_signup(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post(
        "/api/auth/signup",
        json={"username": "newuser", "password": "StrongPass1!"},
    )

    response = client.post(
        "/api/auth/login",
        json={"username": "newuser", "password": "StrongPass1!"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == "newuser"


def test_login_rejects_wrong_password(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/login",
        json={"username": "harry", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_rejects_unknown_username(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post(
        "/api/auth/login",
        json={"username": "ghost", "password": "whatever1!"},
    )

    assert response.status_code == 401


def test_login_issues_a_fresh_token_each_time(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    first_response = client.post(
        "/api/auth/login",
        json={"username": "harry", "password": "kijanka"},
    )
    second_response = client.post(
        "/api/auth/login",
        json={"username": "harry", "password": "kijanka"},
    )

    assert first_response.json()["token"] != second_response.json()["token"]


def test_logout_invalidates_the_session_token(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    login_response = client.post(
        "/api/auth/login",
        json={"username": "harry", "password": "kijanka"},
    )
    token = login_response.json()["token"]

    repository = BoardRepository(tmp_path / "app.db")
    assert repository.get_username_for_token(token) == "harry"

    logout_response = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert logout_response.status_code == 204
    assert repository.get_username_for_token(token) is None


def test_logout_without_a_token_is_a_no_op(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
