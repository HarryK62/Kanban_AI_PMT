from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import default_board


def test_root_serves_html_placeholder() -> None:
    client = TestClient(create_app(frontend_out_dir=Path("/tmp/does-not-exist")))
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "FastAPI hello world is running." in response.text


def test_api_hello_returns_message() -> None:
    client = TestClient(create_app(frontend_out_dir=Path("/tmp/does-not-exist")))
    response = client.get("/api/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "hello from fastapi"}


def test_root_serves_static_frontend_when_built(tmp_path: Path) -> None:
    frontend_out_dir = tmp_path / "out"
    frontend_out_dir.mkdir()
    (frontend_out_dir / "index.html").write_text(
        "<!DOCTYPE html><html><body><h1>Kanban Studio</h1></body></html>",
        encoding="utf-8",
    )

    client = TestClient(create_app(frontend_out_dir=frontend_out_dir))
    response = client.get("/")

    assert response.status_code == 200
    assert "Kanban Studio" in response.text


def test_board_fetch_initializes_database_and_creates_default_board(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    response = client.get("/api/board/user")

    assert response.status_code == 200
    assert db_path.exists()
    assert response.json() == {
        "username": "user",
        "board": default_board().model_dump(by_alias=True),
    }


def test_board_fetch_returns_same_board_for_same_user(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    first_response = client.get("/api/board/user")
    second_response = client.get("/api/board/user")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json() == second_response.json()


def test_board_replace_updates_persisted_board(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    board_payload = default_board().model_dump(by_alias=True)
    board_payload["title"] = "Updated Board"
    board_payload["columns"][0]["title"] = "Ideas"
    board_payload["cards"]["card-1"]["title"] = "Updated task"

    response = client.put("/api/board/user", json=board_payload)
    follow_up_response = client.get("/api/board/user")

    assert response.status_code == 200
    assert response.json()["board"]["title"] == "Updated Board"
    assert response.json()["board"]["columns"][0]["title"] == "Ideas"
    assert response.json()["board"]["cards"]["card-1"]["title"] == "Updated task"
    assert follow_up_response.json() == response.json()


def test_board_replace_rejects_invalid_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    board_payload = default_board().model_dump(by_alias=True)
    board_payload["columns"][0]["cardIds"].append("missing-card")

    response = client.put("/api/board/user", json=board_payload)

    assert response.status_code == 422


def test_ai_connectivity_route_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    response = client.post("/api/ai/test")

    assert response.status_code == 500
    assert response.json() == {"detail": "OPENROUTER_API_KEY is not configured."}
