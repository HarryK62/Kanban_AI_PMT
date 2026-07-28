import sqlite3
from pathlib import Path

import pytest

from app.repository import BoardNotFoundError, BoardRepository


PASSWORD = "Str0ngPass!1"


def make_repository(tmp_path: Path) -> BoardRepository:
    repository = BoardRepository(tmp_path / "app.db")
    repository.initialize()
    return repository


def test_append_chat_message_creates_chat_when_none_exists(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.create_user("user", PASSWORD)
    board_id, board_state_id, _ = repository.bootstrap_default_board("user")

    with sqlite3.connect(repository.db_path) as connection:
        chats_before = connection.execute("SELECT id FROM chats").fetchall()
    assert chats_before == []

    chat_id, message = repository.append_chat_message(
        username="user",
        board_id=board_id,
        role="user",
        content="Hello.",
        board_state_id=board_state_id,
    )

    assert message.sequence_number == 1
    assert message.role == "user"
    assert message.content == "Hello."

    with sqlite3.connect(repository.db_path) as connection:
        chats = connection.execute("SELECT id FROM chats").fetchall()

    assert len(chats) == 1
    assert chats[0][0] == chat_id

    # A second message for the same board must reuse the existing chat
    # rather than creating another one.
    second_chat_id, second_message = repository.append_chat_message(
        username="user",
        board_id=board_id,
        role="assistant",
        content="Hi there.",
        board_state_id=board_state_id,
    )

    assert second_chat_id == chat_id
    assert second_message.sequence_number == 2

    with sqlite3.connect(repository.db_path) as connection:
        chats_after = connection.execute("SELECT id FROM chats").fetchall()

    assert len(chats_after) == 1


def test_create_board_adds_an_additional_board_for_the_user(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.create_user("user", PASSWORD)
    first_board_id, _, _ = repository.bootstrap_default_board("user")

    second_board_id, second_board_state_id, second_board = repository.create_board(
        "user", title="Marketing launch"
    )

    assert second_board_id != first_board_id
    assert second_board.title == "Marketing launch"
    # A freshly created (non-bootstrap) board starts empty.
    assert all(len(column.card_ids) == 0 for column in second_board.columns)
    assert second_board.cards == {}

    fetched_state_id, fetched_board = repository.get_board("user", second_board_id)
    assert fetched_state_id == second_board_state_id
    assert fetched_board.title == "Marketing launch"


def test_create_board_defaults_title_when_blank(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.create_user("user", PASSWORD)

    _, _, board = repository.create_board("user", title="   ")

    assert board.title == "New board"


def test_list_boards_returns_all_boards_for_the_user_in_creation_order(
    tmp_path: Path,
) -> None:
    repository = make_repository(tmp_path)
    repository.create_user("user", PASSWORD)
    first_board_id, _, _ = repository.bootstrap_default_board("user")
    second_board_id, _, _ = repository.create_board("user", title="Second board")

    summaries = repository.list_boards("user")

    assert [summary.board_id for summary in summaries] == [first_board_id, second_board_id]
    assert summaries[0].title == "Kanban Studio"
    assert summaries[1].title == "Second board"


def test_list_boards_does_not_include_another_users_boards(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.create_user("alice", PASSWORD)
    repository.create_user("bob", PASSWORD)
    repository.bootstrap_default_board("alice")
    repository.bootstrap_default_board("bob")

    alice_boards = repository.list_boards("alice")
    bob_boards = repository.list_boards("bob")

    assert len(alice_boards) == 1
    assert len(bob_boards) == 1
    assert alice_boards[0].board_id != bob_boards[0].board_id


def test_get_board_raises_for_a_board_owned_by_another_user(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.create_user("alice", PASSWORD)
    repository.create_user("bob", PASSWORD)
    alice_board_id, _, _ = repository.bootstrap_default_board("alice")
    repository.bootstrap_default_board("bob")

    with pytest.raises(BoardNotFoundError):
        repository.get_board("bob", alice_board_id)


def test_delete_board_removes_the_board_and_its_chat(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.create_user("user", PASSWORD)
    board_id, board_state_id, _ = repository.bootstrap_default_board("user")
    repository.append_chat_message(
        username="user",
        board_id=board_id,
        role="user",
        content="Hello.",
        board_state_id=board_state_id,
    )

    repository.delete_board("user", board_id)

    with pytest.raises(BoardNotFoundError):
        repository.get_board("user", board_id)

    with sqlite3.connect(repository.db_path) as connection:
        remaining_boards = connection.execute(
            "SELECT id FROM boards WHERE id = ?", (board_id,)
        ).fetchall()
        remaining_chats = connection.execute(
            "SELECT id FROM chats WHERE board_id = ?", (board_id,)
        ).fetchall()
        remaining_board_states = connection.execute(
            "SELECT id FROM board_states WHERE board_id = ?", (board_id,)
        ).fetchall()

    assert remaining_boards == []
    assert remaining_chats == []
    assert remaining_board_states == []


def test_delete_board_does_not_affect_the_users_other_boards(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.create_user("user", PASSWORD)
    first_board_id, _, _ = repository.bootstrap_default_board("user")
    second_board_id, _, _ = repository.create_board("user", title="Keep me")

    repository.delete_board("user", first_board_id)

    remaining = repository.list_boards("user")
    assert [summary.board_id for summary in remaining] == [second_board_id]


def test_chat_history_is_isolated_per_board(tmp_path: Path) -> None:
    repository = make_repository(tmp_path)
    repository.create_user("user", PASSWORD)
    first_board_id, first_state_id, _ = repository.bootstrap_default_board("user")
    second_board_id, second_state_id, _ = repository.create_board("user", title="Other")

    repository.append_chat_message(
        username="user",
        board_id=first_board_id,
        role="user",
        content="About the first board.",
        board_state_id=first_state_id,
    )
    repository.append_chat_message(
        username="user",
        board_id=second_board_id,
        role="user",
        content="About the second board.",
        board_state_id=second_state_id,
    )

    first_history = repository.list_chat_history("user", first_board_id)
    second_history = repository.list_chat_history("user", second_board_id)

    assert [message["content"] for message in first_history] == ["About the first board."]
    assert [message["content"] for message in second_history] == ["About the second board."]
