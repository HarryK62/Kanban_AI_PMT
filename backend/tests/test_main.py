import json
from pathlib import Path
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import default_board


class FakeAiClient:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.messages: list[dict[str, str]] | None = None

    async def complete_messages(self, messages: list[dict[str, str]]) -> str:
        self.messages = messages
        return self.reply


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
        "current_board_state_id": 1,
        "board": default_board().model_dump(by_alias=True),
    }

    with sqlite3.connect(db_path) as connection:
        board_row = connection.execute(
            "SELECT id, user_id, current_board_state_id FROM boards"
        ).fetchone()
        board_state_row = connection.execute(
            """
            SELECT board_id, previous_board_state_id, board_json
            FROM board_states
            """
        ).fetchone()

    assert board_row is not None
    assert board_state_row is not None
    assert board_state_row[0] == board_row[0]
    assert board_state_row[1] is None


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
    assert first_response.json()["current_board_state_id"] == 1


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
    assert response.json()["current_board_state_id"] == 2
    assert response.json()["board"]["title"] == "Updated Board"
    assert response.json()["board"]["columns"][0]["title"] == "Ideas"
    assert response.json()["board"]["cards"]["card-1"]["title"] == "Updated task"
    assert follow_up_response.json() == response.json()

    with sqlite3.connect(db_path) as connection:
        board_row = connection.execute(
            "SELECT current_board_state_id FROM boards"
        ).fetchone()
        board_states = connection.execute(
            """
            SELECT id, previous_board_state_id
            FROM board_states
            ORDER BY id ASC
            """
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

    board_payload = default_board().model_dump(by_alias=True)
    board_payload["columns"][0]["cardIds"].append("missing-card")

    response = client.put("/api/board/user", json=board_payload)

    assert response.status_code == 422


def test_board_replace_rejects_missing_fixed_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    board_payload = default_board().model_dump(by_alias=True)
    board_payload["columns"] = board_payload["columns"][:1]

    response = client.put("/api/board/user", json=board_payload)

    assert response.status_code == 422


def test_chat_message_route_rejects_invalid_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    response = client.post("/api/chat/user/messages", json={})

    assert response.status_code == 422


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

    response = client.post(
        "/api/chat/user/messages",
        json={"message": "Move the analytics task to In Progress."},
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
        "current_board_state_id": 1,
        "board": default_board().model_dump(by_alias=True),
    }
    assert ai_client.messages is not None
    assert ai_client.messages[-1] == {
        "role": "user",
        "content": "Move the analytics task to In Progress.",
    }


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

    first_response = client.post(
        "/api/chat/user/messages",
        json={"message": "First session message."},
    )

    assert first_response.status_code == 200

    reset_response = client.post("/api/chat/user/session")
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
        "/api/chat/user/messages",
        json={"message": "Second session message."},
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

    response = client.post(
        "/api/chat/user/messages",
        json={"message": "Rename In Progress to Doing."},
    )

    assert response.status_code == 200
    assert response.json()["current_board_state_id"] == 2
    assert response.json()["assistant_message"]["sequence_number"] == 2
    assert response.json()["board"]["columns"][2]["title"] == "Doing"

    follow_up_response = client.get("/api/board/user")
    assert follow_up_response.status_code == 200
    assert follow_up_response.json()["current_board_state_id"] == 2
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
        (1, "user", "Rename In Progress to Doing.", 1),
        (2, "assistant", "I renamed In Progress to Doing.", 2),
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

    response = client.post(
        "/api/chat/user/messages",
        json={"message": "Collapse this board to one column."},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI response was malformed."}

    follow_up_response = client.get("/api/board/user")
    assert follow_up_response.status_code == 200
    assert follow_up_response.json()["current_board_state_id"] == 1
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

    response = client.post(
        "/api/chat/user/messages",
        json={"message": "Do something."},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI response was malformed."}

    with sqlite3.connect(db_path) as connection:
        board_states = connection.execute(
            "SELECT id FROM board_states ORDER BY id ASC"
        ).fetchall()
        chat_messages = connection.execute(
            "SELECT sequence_number, role, content, board_state_id FROM chat_messages ORDER BY sequence_number ASC"
        ).fetchall()

    assert board_states == [(1,)]
    assert chat_messages == [(1, "user", "Do something.", 1)]


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

    response = client.post(
        "/api/chat/user/messages",
        json={"message": "Break the board."},
    )

    assert response.status_code == 502
    assert response.json() == {"detail": "AI response was malformed."}

    with sqlite3.connect(db_path) as connection:
        board_states = connection.execute(
            "SELECT id FROM board_states ORDER BY id ASC"
        ).fetchall()
        chat_messages = connection.execute(
            "SELECT sequence_number, role, content, board_state_id FROM chat_messages ORDER BY sequence_number ASC"
        ).fetchall()

    assert board_states == [(1,)]
    assert chat_messages == [(1, "user", "Break the board.", 1)]


def test_ai_connectivity_route_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    db_path = tmp_path / "app.db"
    client = TestClient(
        create_app(frontend_out_dir=Path("/tmp/does-not-exist"), db_path=db_path)
    )

    response = client.post("/api/ai/test")

    assert response.status_code == 500
    assert response.json() == {"detail": "OPENROUTER_API_KEY is not configured."}
