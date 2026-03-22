import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.ai import json_dumps
from app.models import Board, ChatMessageRecord


DEFAULT_USERNAME = "user"


def current_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def default_board() -> Board:
    return Board.model_validate(
        {
            "version": 1,
            "title": "Kanban Studio",
            "columns": [
                {
                    "id": "col-backlog",
                    "title": "Backlog",
                    "cardIds": ["card-1", "card-2"],
                },
                {"id": "col-discovery", "title": "Discovery", "cardIds": ["card-3"]},
                {
                    "id": "col-progress",
                    "title": "In Progress",
                    "cardIds": ["card-4", "card-5"],
                },
                {"id": "col-review", "title": "Review", "cardIds": ["card-6"]},
                {"id": "col-done", "title": "Done", "cardIds": ["card-7", "card-8"]},
            ],
            "cards": {
                "card-1": {
                    "id": "card-1",
                    "title": "Align roadmap themes",
                    "details": "Draft quarterly themes with impact statements and metrics.",
                },
                "card-2": {
                    "id": "card-2",
                    "title": "Gather customer signals",
                    "details": "Review support tags, sales notes, and churn feedback.",
                },
                "card-3": {
                    "id": "card-3",
                    "title": "Prototype analytics view",
                    "details": "Sketch initial dashboard layout and key drill-downs.",
                },
                "card-4": {
                    "id": "card-4",
                    "title": "Refine status language",
                    "details": "Standardize column labels and tone across the board.",
                },
                "card-5": {
                    "id": "card-5",
                    "title": "Design card layout",
                    "details": "Add hierarchy and spacing for scanning dense lists.",
                },
                "card-6": {
                    "id": "card-6",
                    "title": "QA micro-interactions",
                    "details": "Verify hover, focus, and loading states.",
                },
                "card-7": {
                    "id": "card-7",
                    "title": "Ship marketing page",
                    "details": "Final copy approved and asset pack delivered.",
                },
                "card-8": {
                    "id": "card-8",
                    "title": "Close onboarding sprint",
                    "details": "Document release notes and share internally.",
                },
            },
        }
    )


class BoardRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id INTEGER PRIMARY KEY,
                  username TEXT NOT NULL UNIQUE,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS boards (
                  id INTEGER PRIMARY KEY,
                  user_id INTEGER NOT NULL UNIQUE,
                  current_board_state_id INTEGER UNIQUE,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS board_states (
                  id INTEGER PRIMARY KEY,
                  board_id INTEGER NOT NULL,
                  previous_board_state_id INTEGER,
                  board_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY (board_id) REFERENCES boards(id),
                  FOREIGN KEY (previous_board_state_id) REFERENCES board_states(id)
                );

                CREATE TABLE IF NOT EXISTS chats (
                  id INTEGER PRIMARY KEY,
                  user_id INTEGER NOT NULL UNIQUE,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS chat_messages (
                  id INTEGER PRIMARY KEY,
                  chat_id INTEGER NOT NULL,
                  sequence_number INTEGER NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  board_state_id INTEGER NOT NULL,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY (chat_id) REFERENCES chats(id),
                  FOREIGN KEY (board_state_id) REFERENCES board_states(id),
                  UNIQUE(chat_id, sequence_number)
                );
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_boards_user_id
                ON boards(user_id)
                """
            )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_boards_current_board_state_id
                ON boards(current_board_state_id)
                WHERE current_board_state_id IS NOT NULL
                """
            )

    def get_or_create_board(self, username: str) -> tuple[int, Board]:
        self.initialize()

        with self.connect() as connection:
            user_id = self._get_or_create_user(connection, username)
            row = self._read_current_board_row(connection, user_id)

            if row is None:
                row = self._create_board(connection, user_id, default_board())

            return int(row["current_board_state_id"]), self._deserialize_board(
                row["board_json"]
            )

    def replace_board(self, username: str, board: Board) -> tuple[int, Board]:
        self.initialize()

        with self.connect() as connection:
            user_id = self._get_or_create_user(connection, username)
            existing_board = self._read_current_board_row(connection, user_id)
            timestamp = current_timestamp()

            if existing_board is None:
                self._create_board(connection, user_id, default_board(), timestamp=timestamp)
                existing_board = self._read_current_board_row(connection, user_id)

            next_board_state_id = self._insert_board_state(
                connection=connection,
                board_id=int(existing_board["board_id"]),
                previous_board_state_id=int(existing_board["current_board_state_id"]),
                board=board,
                timestamp=timestamp,
            )

            connection.execute(
                """
                UPDATE boards
                SET current_board_state_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_board_state_id, timestamp, existing_board["board_id"]),
            )
            return next_board_state_id, board

    def _get_or_create_user(self, connection: sqlite3.Connection, username: str) -> int:
        row = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is not None:
            return int(row["id"])

        cursor = connection.execute(
            """
            INSERT INTO users (username, created_at)
            VALUES (?, ?)
            """,
            (username, current_timestamp()),
        )
        return int(cursor.lastrowid)

    def _read_current_board_row(
        self,
        connection: sqlite3.Connection,
        user_id: int,
    ) -> sqlite3.Row | None:
        return connection.execute(
            """
            SELECT boards.id AS board_id, boards.current_board_state_id, board_states.board_json
            FROM boards
            JOIN board_states ON board_states.id = boards.current_board_state_id
            WHERE boards.user_id = ?
            ORDER BY boards.id ASC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

    def _create_board(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        board: Board,
        timestamp: str | None = None,
    ) -> sqlite3.Row:
        created_at = timestamp or current_timestamp()
        board_cursor = connection.execute(
            """
            INSERT INTO boards (user_id, current_board_state_id, created_at, updated_at)
            VALUES (?, NULL, ?, ?)
            """,
            (user_id, created_at, created_at),
        )
        board_id = int(board_cursor.lastrowid)
        board_state_id = self._insert_board_state(
            connection=connection,
            board_id=board_id,
            previous_board_state_id=None,
            board=board,
            timestamp=created_at,
        )
        connection.execute(
            """
            UPDATE boards
            SET current_board_state_id = ?
            WHERE id = ?
            """,
            (board_state_id, board_id),
        )
        row = self._read_current_board_row(connection, user_id)
        if row is None:
            raise RuntimeError("Board creation failed to produce a current board state.")
        return row

    def _insert_board_state(
        self,
        connection: sqlite3.Connection,
        board_id: int,
        previous_board_state_id: int | None,
        board: Board,
        timestamp: str,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO board_states (board_id, previous_board_state_id, board_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                board_id,
                previous_board_state_id,
                self._serialize_board(board),
                timestamp,
            ),
        )
        return int(cursor.lastrowid)

    def _serialize_board(self, board: Board) -> str:
        return json_dumps(board.model_dump(by_alias=True))

    def _deserialize_board(self, board_json: str) -> Board:
        import json

        return Board.model_validate(json.loads(board_json))

    def get_or_create_chat(self, username: str) -> int:
        self.initialize()

        with self.connect() as connection:
            user_id = self._get_or_create_user(connection, username)
            board_row = self._read_current_board_row(connection, user_id)
            if board_row is None:
                self._create_board(connection, user_id, default_board())

            row = connection.execute(
                """
                SELECT id
                FROM chats
                WHERE user_id = ?
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if row is not None:
                return int(row["id"])

            timestamp = current_timestamp()
            cursor = connection.execute(
                """
                INSERT INTO chats (user_id, created_at, updated_at)
                VALUES (?, ?, ?)
                """,
                (user_id, timestamp, timestamp),
            )
            return int(cursor.lastrowid)

    def reset_chat_session(self, username: str) -> int:
        self.initialize()

        with self.connect() as connection:
            user_id = self._get_or_create_user(connection, username)
            board_row = self._read_current_board_row(connection, user_id)
            if board_row is None:
                self._create_board(connection, user_id, default_board())

            existing_chat_row = connection.execute(
                """
                SELECT id
                FROM chats
                WHERE user_id = ?
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if existing_chat_row is not None:
                existing_chat_id = int(existing_chat_row["id"])
                connection.execute(
                    """
                    DELETE FROM chat_messages
                    WHERE chat_id = ?
                    """,
                    (existing_chat_id,),
                )
                connection.execute(
                    """
                    DELETE FROM chats
                    WHERE id = ?
                    """,
                    (existing_chat_id,),
                )

            timestamp = current_timestamp()
            cursor = connection.execute(
                """
                INSERT INTO chats (user_id, created_at, updated_at)
                VALUES (?, ?, ?)
                """,
                (user_id, timestamp, timestamp),
            )
            return int(cursor.lastrowid)

    def list_chat_history(self, username: str) -> list[dict[str, str]]:
        self.initialize()

        with self.connect() as connection:
            chat_id = self._get_or_create_chat_id(connection, username)
            rows = connection.execute(
                """
                SELECT role, content
                FROM chat_messages
                WHERE chat_id = ?
                ORDER BY sequence_number ASC
                """,
                (chat_id,),
            ).fetchall()
            return [{"role": row["role"], "content": row["content"]} for row in rows]

    def append_chat_message(
        self,
        username: str,
        role: str,
        content: str,
        board_state_id: int,
    ) -> tuple[int, ChatMessageRecord]:
        self.initialize()

        with self.connect() as connection:
            chat_id = self._get_or_create_chat_id(connection, username)
            row = self._insert_chat_message(
                connection=connection,
                chat_id=chat_id,
                role=role,
                content=content,
                board_state_id=board_state_id,
            )
            return chat_id, self._chat_message_from_row(row)

    def get_board_snapshot(self, username: str) -> tuple[int, Board]:
        return self.get_or_create_board(username)

    def apply_board_state(self, username: str, board: Board) -> tuple[int, Board]:
        return self.replace_board(username, board)

    def _get_or_create_chat_id(self, connection: sqlite3.Connection, username: str) -> int:
        user_id = self._get_or_create_user(connection, username)
        board_row = self._read_current_board_row(connection, user_id)
        if board_row is None:
            self._create_board(connection, user_id, default_board())

        row = connection.execute(
            """
            SELECT id
            FROM chats
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if row is not None:
            return int(row["id"])

        timestamp = current_timestamp()
        cursor = connection.execute(
            """
            INSERT INTO chats (user_id, created_at, updated_at)
            VALUES (?, ?, ?)
            """,
            (user_id, timestamp, timestamp),
        )
        return int(cursor.lastrowid)

    def _insert_chat_message(
        self,
        connection: sqlite3.Connection,
        chat_id: int,
        role: str,
        content: str,
        board_state_id: int,
    ) -> sqlite3.Row:
        next_sequence_number = (
            connection.execute(
                """
                SELECT COALESCE(MAX(sequence_number), 0) + 1
                FROM chat_messages
                WHERE chat_id = ?
                """,
                (chat_id,),
            ).fetchone()[0]
        )
        timestamp = current_timestamp()
        cursor = connection.execute(
            """
            INSERT INTO chat_messages (chat_id, sequence_number, role, content, board_state_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chat_id, next_sequence_number, role, content, board_state_id, timestamp),
        )
        connection.execute(
            """
            UPDATE chats
            SET updated_at = ?
            WHERE id = ?
            """,
            (timestamp, chat_id),
        )
        row = connection.execute(
            """
            SELECT id, sequence_number, role, content
            FROM chat_messages
            WHERE id = ?
            """,
            (int(cursor.lastrowid),),
        ).fetchone()
        if row is None:
            raise RuntimeError("Chat message insert failed.")
        return row

    def _chat_message_from_row(self, row: sqlite3.Row) -> ChatMessageRecord:
        return ChatMessageRecord(
            id=int(row["id"]),
            sequence_number=int(row["sequence_number"]),
            role=row["role"],
            content=row["content"],
        )
