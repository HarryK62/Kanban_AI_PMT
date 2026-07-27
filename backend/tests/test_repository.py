import sqlite3
from pathlib import Path

from app.repository import BoardRepository


def test_append_chat_message_creates_chat_when_none_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "app.db"
    repository = BoardRepository(db_path)
    repository.initialize()

    board_state_id, _ = repository.get_or_create_board("user")

    with sqlite3.connect(db_path) as connection:
        chats_before = connection.execute("SELECT id FROM chats").fetchall()
    assert chats_before == []

    chat_id, message = repository.append_chat_message(
        username="user",
        role="user",
        content="Hello.",
        board_state_id=board_state_id,
    )

    assert message.sequence_number == 1
    assert message.role == "user"
    assert message.content == "Hello."

    with sqlite3.connect(db_path) as connection:
        chats = connection.execute("SELECT id FROM chats").fetchall()

    assert len(chats) == 1
    assert chats[0][0] == chat_id

    # A second message for the same user must reuse the existing chat
    # rather than creating another one.
    second_chat_id, second_message = repository.append_chat_message(
        username="user",
        role="assistant",
        content="Hi there.",
        board_state_id=board_state_id,
    )

    assert second_chat_id == chat_id
    assert second_message.sequence_number == 2

    with sqlite3.connect(db_path) as connection:
        chats_after = connection.execute("SELECT id FROM chats").fetchall()

    assert len(chats_after) == 1
