import json
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import default_board


AUTH_PASSWORD = "Str0ngPass!1"


class FakeAiClient:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages: list[dict[str, str]] | None = None

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        self.messages = messages
        return self.reply


def signup(
    client: TestClient, username: str, password: str = AUTH_PASSWORD
) -> dict[str, str]:
    """Sign up (bootstrapping a default board) and return auth headers."""
    response = client.post(
        "/api/auth/signup", json={"username": username, "password": password}
    )
    assert response.status_code == 201, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def signup_with_board_id(
    client: TestClient, username: str, password: str = AUTH_PASSWORD
) -> tuple[dict[str, str], int]:
    headers = signup(client, username, password)
    boards = client.get(f"/api/boards/{username}", headers=headers).json()
    assert len(boards) == 1
    return headers, boards[0]["board_id"]


def signup_with_board(
    client: TestClient, username: str, password: str = AUTH_PASSWORD
) -> tuple[dict[str, str], int, int]:
    """Sign up and return (headers, board_id, initial_board_state_id).

    board_states.id is a single autoincrementing sequence shared by every
    board in the database (including the seeded harry/kijanka account), so
    tests must not assume a freshly bootstrapped board starts at id 1.
    """
    headers = signup(client, username, password)
    boards = client.get(f"/api/boards/{username}", headers=headers).json()
    assert len(boards) == 1
    return headers, boards[0]["board_id"], boards[0]["current_board_state_id"]


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


def test_signup_bootstraps_a_default_board(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers = signup(client, "user")

    response = client.get("/api/boards/user", headers=headers)

    assert response.status_code == 200
    boards = response.json()
    assert len(boards) == 1
    assert boards[0]["title"] == "Kanban Studio"
    assert isinstance(boards[0]["current_board_state_id"], int)


def test_list_boards_requires_authentication(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    response = client.get("/api/boards/user")

    assert response.status_code == 401


def test_create_board_adds_a_second_board(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers, first_board_id = signup_with_board_id(client, "user")

    response = client.post(
        "/api/boards/user", json={"title": "Marketing"}, headers=headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["board_id"] != first_board_id
    assert body["board"]["title"] == "Marketing"
    assert body["board"]["cards"] == {}

    list_response = client.get("/api/boards/user", headers=headers)
    titles = [board["title"] for board in list_response.json()]
    assert titles == ["Kanban Studio", "Marketing"]


def test_create_board_defaults_title_when_omitted(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers = signup(client, "user")

    response = client.post("/api/boards/user", json={}, headers=headers)

    assert response.status_code == 201
    assert response.json()["board"]["title"] == "New board"


def test_get_board_returns_the_requested_board(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers, board_id, initial_state_id = signup_with_board(client, "user")

    response = client.get(f"/api/boards/user/{board_id}", headers=headers)

    assert response.status_code == 200
    assert response.json() == {
        "username": "user",
        "board_id": board_id,
        "current_board_state_id": initial_state_id,
        "board": default_board().model_dump(by_alias=True),
    }


def test_get_board_returns_404_for_unknown_board_id(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers = signup(client, "user")

    response = client.get("/api/boards/user/999999", headers=headers)

    assert response.status_code == 404


def test_board_route_rejects_a_token_for_a_different_username(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    alice_headers, alice_board_id = signup_with_board_id(client, "alice")
    bob_headers = signup(client, "bob")

    response = client.get(f"/api/boards/alice/{alice_board_id}", headers=bob_headers)

    assert response.status_code == 401


def test_get_board_returns_404_for_a_board_id_owned_by_another_user(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    _, bob_board_id = signup_with_board_id(client, "bob")
    alice_headers, _ = signup_with_board_id(client, "alice")

    # alice is properly authenticated as herself, but asks for a board id
    # that belongs to bob -- the mismatch must surface as "not found", not
    # leak bob's board content.
    response = client.get(f"/api/boards/alice/{bob_board_id}", headers=alice_headers)

    assert response.status_code == 404


def test_board_replace_updates_persisted_board(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers, board_id, initial_state_id = signup_with_board(client, "user")

    board_payload = default_board().model_dump(by_alias=True)
    board_payload["title"] = "Updated Board"
    board_payload["columns"][0]["title"] = "Ideas"
    board_payload["cards"]["card-1"]["title"] = "Updated task"

    response = client.put(
        f"/api/boards/user/{board_id}", json=board_payload, headers=headers
    )
    follow_up_response = client.get(f"/api/boards/user/{board_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["current_board_state_id"] == initial_state_id + 1
    assert response.json()["board"]["title"] == "Updated Board"
    assert response.json()["board"]["columns"][0]["title"] == "Ideas"
    assert response.json()["board"]["cards"]["card-1"]["title"] == "Updated task"
    assert follow_up_response.json() == response.json()

    with sqlite3.connect(db_path) as connection:
        board_row = connection.execute(
            "SELECT current_board_state_id FROM boards WHERE id = ?", (board_id,)
        ).fetchone()
        board_states = connection.execute(
            """
            SELECT id, previous_board_state_id
            FROM board_states
            WHERE board_id = ?
            ORDER BY id ASC
            """,
            (board_id,),
        ).fetchall()

    assert board_row is not None
    assert len(board_states) == 2
    assert board_states[0][1] is None
    assert board_states[1][1] == board_states[0][0]
    assert board_row[0] == board_states[1][0]


def test_board_replace_rejects_invalid_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers, board_id = signup_with_board_id(client, "user")

    board_payload = default_board().model_dump(by_alias=True)
    board_payload["columns"][0]["cardIds"].append("missing-card")

    response = client.put(
        f"/api/boards/user/{board_id}", json=board_payload, headers=headers
    )

    assert response.status_code == 422


def test_board_replace_rejects_missing_fixed_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers, board_id = signup_with_board_id(client, "user")

    board_payload = default_board().model_dump(by_alias=True)
    board_payload["columns"] = board_payload["columns"][:1]

    response = client.put(
        f"/api/boards/user/{board_id}", json=board_payload, headers=headers
    )

    assert response.status_code == 422


def test_delete_board_removes_it_from_the_list(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers, board_id = signup_with_board_id(client, "user")
    second_board_id = client.post(
        "/api/boards/user", json={"title": "Second"}, headers=headers
    ).json()["board_id"]

    response = client.delete(f"/api/boards/user/{board_id}", headers=headers)

    assert response.status_code == 204
    remaining = client.get("/api/boards/user", headers=headers).json()
    assert [board["board_id"] for board in remaining] == [second_board_id]


def test_delete_board_returns_404_for_unknown_board(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers = signup(client, "user")

    response = client.delete("/api/boards/user/999999", headers=headers)

    assert response.status_code == 404


def test_chat_message_route_requires_authentication(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    response = client.post(
        "/api/chat/user/1/messages", json={"message": "Hello."}
    )

    assert response.status_code == 401


def test_chat_message_route_rejects_invalid_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers, board_id = signup_with_board_id(client, "user")

    response = client.post(
        f"/api/chat/user/{board_id}/messages", json={}, headers=headers
    )

    assert response.status_code == 422


def test_chat_message_route_returns_404_for_unknown_board(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )
    headers = signup(client, "user")

    response = client.post(
        "/api/chat/user/999999/messages",
        json={"message": "Hello."},
        headers=headers,
    )

    assert response.status_code == 404


def test_chat_message_route_returns_no_op_reply(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    ai_client = FakeAiClient('{"reply":"Done.","board_update":null}')
    client = TestClient(
        create_app(
            frontend_out_dir=Path("/tmp/does-not-exist"),
            db_path=db_path,
            ai_client=ai_client,
        )
    )
    headers, board_id, initial_state_id = signup_with_board(client, "user")

    response = client.post(
        f"/api/chat/user/{board_id}/messages",
        json={"message": "Move the analytics task to In Progress."},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "chat_id": 1,
        "assistant_message": {
            "id": 2,
            "sequence_number": 2,
            "role": "assistant",
            "content": "Done.",
        },
        "current_board_state_id": initial_state_id,
        "board": default_board().model_dump(by_alias=True),
    }
    assert ai_client.messages is not None
    assert ai_client.messages[-1] == {
        "role": "user",
        "content": "Move the analytics task to In Progress.",
    }


def test_chat_history_is_isolated_between_two_boards_of_the_same_user(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "app.db"
    first_ai_client = FakeAiClient('{"reply":"Noted on board one.","board_update":null}')
    client = TestClient(
        create_app(
            frontend_out_dir=Path("/tmp/does-not-exist"),
            db_path=db_path,
            ai_client=first_ai_client,
        )
    )
    headers, first_board_id = signup_with_board_id(client, "user")
    second_board_id = client.post(
        "/api/boards/user", json={"title": "Second"}, headers=headers
    ).json()["board_id"]

    first_response = client.post(
        f"/api/chat/user/{first_board_id}/messages",
        json={"message": "First board message."},
        headers=headers,
    )
    assert first_response.status_code == 200

    second_ai_client = FakeAiClient('{"reply":"Noted on board two.","board_update":null}')
    client = TestClient(
        create_app(
            frontend_out_dir=Path("/tmp/does-not-exist"),
            db_path=db_path,
            ai_client=second_ai_client,
        )
    )
    second_response = client.post(
        f"/api/chat/user/{second_board_id}/messages",
        json={"message": "Second board message."},
        headers=headers,
    )

    assert second_response.status_code == 200
    assert second_ai_client.messages is not None
    # The second board's chat must not see the first board's history.
    assert all(
        message["content"] != "First board message."
        for message in second_ai_client.messages
    )


def test_chat_session_route_resets_existing_chat_context(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    first_ai_client = FakeAiClient('{"reply":"Done.","board_update":null}')
    client = TestClient(
        create_app(
            frontend_out_dir=Path("/tmp/does-not-exist"),
            db_path=db_path,
            ai_client=first_ai_client,
        )
    )
    headers, board_id = signup_with_board_id(client, "user")

    first_response = client.post(
        f"/api/chat/user/{board_id}/messages",
        json={"message": "First session message."},
        headers=headers,
    )

    assert first_response.status_code == 200

    reset_response = client.post(
        f"/api/chat/user/{board_id}/session", headers=headers
    )
    assert reset_response.status_code == 200
    reset_chat_id = reset_response.json()["chat_id"]

    second_ai_client = FakeAiClient('{"reply":"Fresh context.","board_update":null}')
    client = TestClient(
        create_app(
            frontend_out_dir=Path("/tmp/does-not-exist"),
            db_path=db_path,
            ai_client=second_ai_client,
        )
    )
    second_response = client.post(
        f"/api/chat/user/{board_id}/messages",
        json={"message": "Second session message."},
        headers=headers,
    )

    assert second_response.status_code == 200
    assert second_response.json()["chat_id"] == reset_chat_id
    assert second_ai_client.messages is not None
    assert second_ai_client.messages[-1] == {
        "role": "user",
        "content": "Second session message.",
    }
    assert all(
        message["content"] != "First session message."
        for message in second_ai_client.messages
    )


def test_chat_message_route_persists_board_update(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    updated_board = default_board().model_dump(by_alias=True)
    updated_board["columns"][2]["title"] = "Doing"
    ai_client = FakeAiClient(
        json.dumps(
            {
                "reply": "I renamed In Progress to Doing.",
                "board_update": {
                    "kind": "replace_board",
                    "board": updated_board,
                },
            }
        )
    )
    client = TestClient(
        create_app(
            frontend_out_dir=Path("/tmp/does-not-exist"),
            db_path=db_path,
            ai_client=ai_client,
        )
    )
    headers, board_id, initial_state_id = signup_with_board(client, "user")

    response = client.post(
        f"/api/chat/user/{board_id}/messages",
        json={"message": "Rename In Progress to Doing."},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["current_board_state_id"] == initial_state_id + 1
    assert response.json()["assistant_message"]["sequence_number"] == 2
    assert response.json()["board"]["columns"][2]["title"] == "Doing"

    follow_up_response = client.get(f"/api/boards/user/{board_id}", headers=headers)
    assert follow_up_response.status_code == 200
    assert follow_up_response.json()["current_board_state_id"] == initial_state_id + 1
    assert follow_up_response.json()["board"]["columns"][2]["title"] == "Doing"

    with sqlite3.connect(db_path) as connection:
        chat_messages = connection.execute(
            """
            SELECT sequence_number, role, content, board_state_id
            FROM chat_messages
            ORDER BY sequence_number ASC
            """
        ).fetchall()

    assert chat_messages == [
        (1, "user", "Rename In Progress to Doing.", initial_state_id),
        (2, "assistant", "I renamed In Progress to Doing.", initial_state_id + 1),
    ]


def test_chat_message_route_rejects_ai_board_with_missing_fixed_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    invalid_board = default_board().model_dump(by_alias=True)
    invalid_board["columns"] = invalid_board["columns"][:1]
    ai_client = FakeAiClient(
        json.dumps(
            {
                "reply": "I simplified the board.",
                "board_update": {
                    "kind": "replace_board",
                    "board": invalid_board,
                },
            }
        )
    )
    client = TestClient(
        create_app(
            frontend_out_dir=Path("/tmp/does-not-exist"),
            db_path=db_path,
            ai_client=ai_client,
        )
    )
    headers, board_id, initial_state_id = signup_with_board(client, "user")

    response = client.post(
        f"/api/chat/user/{board_id}/messages",
        json={"message": "Collapse this board to one column."},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"] == "I simplified the board."
    assert response.json()["current_board_state_id"] == initial_state_id
    assert response.json()["board"] == default_board().model_dump(by_alias=True)

    follow_up_response = client.get(f"/api/boards/user/{board_id}", headers=headers)
    assert follow_up_response.status_code == 200
    assert follow_up_response.json()["current_board_state_id"] == initial_state_id
    assert follow_up_response.json()["board"] == default_board().model_dump(by_alias=True)


def test_chat_message_route_rejects_malformed_ai_reply(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    ai_client = FakeAiClient("not json")
    client = TestClient(
        create_app(
            frontend_out_dir=Path("/tmp/does-not-exist"),
            db_path=db_path,
            ai_client=ai_client,
        )
    )
    headers, board_id, initial_state_id = signup_with_board(client, "user")

    response = client.post(
        f"/api/chat/user/{board_id}/messages",
        json={"message": "Do something."},
        headers=headers,
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI response was malformed."}

    with sqlite3.connect(db_path) as connection:
        board_states = connection.execute(
            "SELECT id FROM board_states WHERE board_id = ? ORDER BY id ASC",
            (board_id,),
        ).fetchall()
        chat_messages = connection.execute(
            "SELECT sequence_number, role, content, board_state_id FROM chat_messages ORDER BY sequence_number ASC"
        ).fetchall()

    assert board_states == [(initial_state_id,)]
    # The user message must not be persisted when the AI call fails, otherwise
    # it would be replayed as unanswered context on the next turn.
    assert chat_messages == []


def test_chat_message_route_rejects_invalid_board_update(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    invalid_board = default_board().model_dump(by_alias=True)
    invalid_board["columns"][0]["cardIds"].append("missing-card")
    ai_client = FakeAiClient(
        json.dumps(
            {
                "reply": "I updated the board.",
                "board_update": {
                    "kind": "replace_board",
                    "board": invalid_board,
                },
            }
        )
    )
    client = TestClient(
        create_app(
            frontend_out_dir=Path("/tmp/does-not-exist"),
            db_path=db_path,
            ai_client=ai_client,
        )
    )
    headers, board_id, initial_state_id = signup_with_board(client, "user")

    response = client.post(
        f"/api/chat/user/{board_id}/messages",
        json={"message": "Break the board."},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["assistant_message"]["content"] == "I updated the board."
    assert response.json()["current_board_state_id"] == initial_state_id
    assert response.json()["board"] == default_board().model_dump(by_alias=True)

    with sqlite3.connect(db_path) as connection:
        board_states = connection.execute(
            "SELECT id FROM board_states WHERE board_id = ? ORDER BY id ASC",
            (board_id,),
        ).fetchall()
        chat_messages = connection.execute(
            "SELECT sequence_number, role, content, board_state_id FROM chat_messages ORDER BY sequence_number ASC"
        ).fetchall()

    assert board_states == [(initial_state_id,)]
    assert chat_messages == [
        (1, "user", "Break the board.", initial_state_id),
        (2, "assistant", "I updated the board.", initial_state_id),
    ]


def test_ai_connectivity_route_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    response = client.post("/api/ai/test")

    assert response.status_code == 500
    assert response.json() == {"detail": "OPENROUTER_API_KEY is not configured."}
