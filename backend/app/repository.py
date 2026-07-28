import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.ai import json_dumps
from app.auth import (
    generate_token,
    hash_password,
    normalize_username,
    validate_password_strength,
    validate_username,
    verify_password,
)
from app.models import Board, BoardSummary, ChatMessageRecord, MVP_COLUMN_IDS


SEEDED_ACCOUNTS = (("harry", "kijanka"),)

DEFAULT_COLUMN_TITLES = {
    "col-backlog": "Backlog",
    "col-discovery": "Discovery",
    "col-progress": "In Progress",
    "col-review": "Review",
    "col-done": "Done",
}


class UsernameTakenError(ValueError):
    """Raised when signup targets a username that already exists."""


class InvalidCredentialsError(ValueError):
    """Raised when login credentials do not match a stored account."""


class UsernameNotFoundError(ValueError):
    """Raised when an operation references a username with no account."""


class BoardNotFoundError(ValueError):
    """Raised when a board id does not exist or is not owned by the user."""


def current_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def empty_board(title: str) -> Board:
    return Board.model_validate(
        {
            "version": 1,
            "title": title,
            "columns": [
                {"id": column_id, "title": DEFAULT_COLUMN_TITLES[column_id], "cardIds": []}
                for column_id in MVP_COLUMN_IDS
            ],
            "cards": {},
        }
    )


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
            self._migrate_legacy_schema(connection)
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id INTEGER PRIMARY KEY,
                  username TEXT NOT NULL UNIQUE,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS boards (
                  id INTEGER PRIMARY KEY,
                  user_id INTEGER NOT NULL,
                  current_board_state_id INTEGER,
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
                  user_id INTEGER NOT NULL,
                  board_id INTEGER NOT NULL UNIQUE,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id),
                  FOREIGN KEY (board_id) REFERENCES boards(id)
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

                CREATE TABLE IF NOT EXISTS sessions (
                  id INTEGER PRIMARY KEY,
                  user_id INTEGER NOT NULL,
                  token TEXT NOT NULL UNIQUE,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id)
                );
                """
            )

            existing_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(users)").fetchall()
            }
            if "password_hash" not in existing_columns:
                connection.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")

            for username, password in SEEDED_ACCOUNTS:
                self._seed_account_if_missing(connection, username, password)

    def _migrate_legacy_schema(self, connection: sqlite3.Connection) -> None:
        boards_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(boards)").fetchall()
        }
        if not boards_columns:
            return  # Fresh database: nothing to migrate.

        has_legacy_unique_board_per_user = any(
            index["unique"] for index in connection.execute("PRAGMA index_list(boards)").fetchall()
        )

        chats_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(chats)").fetchall()
        }
        chats_missing_board_id = bool(chats_columns) and "board_id" not in chats_columns

        if has_legacy_unique_board_per_user or chats_missing_board_id:
            # backend/data/ is a local, gitignored dev database with no
            # production deployment yet, so it's simplest to rebuild these
            # tables rather than hand-write an ALTER TABLE path for a
            # UNIQUE-constraint removal, which SQLite cannot do in place.
            connection.executescript(
                """
                DROP TABLE IF EXISTS chat_messages;
                DROP TABLE IF EXISTS chats;
                DROP TABLE IF EXISTS board_states;
                DROP TABLE IF EXISTS boards;
                """
            )

    def _seed_account_if_missing(
        self, connection: sqlite3.Connection, username: str, password: str
    ) -> None:
        normalized_username = normalize_username(username)
        row = connection.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
        if row is not None:
            if row["password_hash"] is None:
                connection.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (hash_password(password), row["id"]),
                )
            return

        cursor = connection.execute(
            """
            INSERT INTO users (username, created_at, password_hash)
            VALUES (?, ?, ?)
            """,
            (normalized_username, current_timestamp(), hash_password(password)),
        )
        user_id = int(cursor.lastrowid)
        self._insert_new_board(connection, user_id, default_board())

    # -- Auth -----------------------------------------------------------

    def create_user(self, username: str, password: str) -> int:
        normalized_username = normalize_username(username)
        validate_username(normalized_username)
        validate_password_strength(password)

        with self.connect() as connection:
            existing_row = connection.execute(
                "SELECT id FROM users WHERE username = ?",
                (normalized_username,),
            ).fetchone()
            if existing_row is not None:
                raise UsernameTakenError(
                    f"Username '{normalized_username}' is already taken."
                )

            cursor = connection.execute(
                """
                INSERT INTO users (username, created_at, password_hash)
                VALUES (?, ?, ?)
                """,
                (normalized_username, current_timestamp(), hash_password(password)),
            )
            return int(cursor.lastrowid)

    def verify_login(self, username: str, password: str) -> int:
        normalized_username = normalize_username(username)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                (normalized_username,),
            ).fetchone()

        if (
            row is None
            or row["password_hash"] is None
            or not verify_password(password, row["password_hash"])
        ):
            raise InvalidCredentialsError("Invalid username or password.")
        return int(row["id"])

    def create_session(self, user_id: int) -> str:
        token = generate_token()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (user_id, token, created_at)
                VALUES (?, ?, ?)
                """,
                (user_id, token, current_timestamp()),
            )
        return token

    def get_username_for_token(self, token: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT users.username AS username
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                """,
                (token,),
            ).fetchone()
        return row["username"] if row is not None else None

    def delete_session(self, token: str) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))

    def _get_user_id(self, connection: sqlite3.Connection, username: str) -> int:
        normalized_username = normalize_username(username)
        row = connection.execute(
            "SELECT id FROM users WHERE username = ?",
            (normalized_username,),
        ).fetchone()
        if row is None:
            raise UsernameNotFoundError(f"User '{normalized_username}' was not found.")
        return int(row["id"])

    # -- Boards -----------------------------------------------------------

    def bootstrap_default_board(self, username: str) -> tuple[int, int, Board]:
        """Create the sample-filled starter board for a brand-new account."""
        with self.connect() as connection:
            user_id = self._get_user_id(connection, username)
            board = default_board()
            row = self._insert_new_board(connection, user_id, board)
            return int(row["board_id"]), int(row["current_board_state_id"]), board

    def create_board(self, username: str, title: str | None = None) -> tuple[int, int, Board]:
        with self.connect() as connection:
            user_id = self._get_user_id(connection, username)
            board = empty_board(title.strip() if title and title.strip() else "New board")
            row = self._insert_new_board(connection, user_id, board)
            return int(row["board_id"]), int(row["current_board_state_id"]), board

    def list_boards(self, username: str) -> list[BoardSummary]:
        with self.connect() as connection:
            user_id = self._get_user_id(connection, username)
            rows = connection.execute(
                """
                SELECT boards.id AS board_id, boards.current_board_state_id,
                       boards.created_at, boards.updated_at, board_states.board_json
                FROM boards
                JOIN board_states ON board_states.id = boards.current_board_state_id
                WHERE boards.user_id = ?
                ORDER BY boards.id ASC
                """,
                (user_id,),
            ).fetchall()
            return [
                BoardSummary(
                    board_id=int(row["board_id"]),
                    title=self._deserialize_board(row["board_json"]).title,
                    current_board_state_id=int(row["current_board_state_id"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def get_board(self, username: str, board_id: int) -> tuple[int, Board]:
        with self.connect() as connection:
            user_id = self._get_user_id(connection, username)
            row = self._get_owned_board_row(connection, user_id, board_id)
            return int(row["current_board_state_id"]), self._deserialize_board(
                row["board_json"]
            )

    def replace_board(self, username: str, board_id: int, board: Board) -> tuple[int, Board]:
        with self.connect() as connection:
            user_id = self._get_user_id(connection, username)
            existing = self._get_owned_board_row(connection, user_id, board_id)
            timestamp = current_timestamp()

            next_board_state_id = self._insert_board_state(
                connection=connection,
                board_id=board_id,
                previous_board_state_id=int(existing["current_board_state_id"]),
                board=board,
                timestamp=timestamp,
            )

            connection.execute(
                """
                UPDATE boards
                SET current_board_state_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_board_state_id, timestamp, board_id),
            )
            return next_board_state_id, board

    def delete_board(self, username: str, board_id: int) -> None:
        with self.connect() as connection:
            user_id = self._get_user_id(connection, username)
            self._get_owned_board_row(connection, user_id, board_id)

            chat_row = connection.execute(
                "SELECT id FROM chats WHERE board_id = ?", (board_id,)
            ).fetchone()
            if chat_row is not None:
                connection.execute(
                    "DELETE FROM chat_messages WHERE chat_id = ?", (chat_row["id"],)
                )
                connection.execute("DELETE FROM chats WHERE id = ?", (chat_row["id"],))

            connection.execute("DELETE FROM board_states WHERE board_id = ?", (board_id,))
            connection.execute("DELETE FROM boards WHERE id = ?", (board_id,))

    def _get_owned_board_row(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        board_id: int,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT boards.id AS board_id, boards.current_board_state_id, board_states.board_json
            FROM boards
            JOIN board_states ON board_states.id = boards.current_board_state_id
            WHERE boards.id = ? AND boards.user_id = ?
            """,
            (board_id, user_id),
        ).fetchone()
        if row is None:
            raise BoardNotFoundError(f"Board {board_id} was not found for this user.")
        return row

    def _insert_new_board(
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
        row = connection.execute(
            "SELECT id AS board_id, current_board_state_id FROM boards WHERE id = ?",
            (board_id,),
        ).fetchone()
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
        return Board.model_validate(json.loads(board_json))

    # -- Chat (scoped to a single board) -----------------------------------

    def reset_chat_session(self, username: str, board_id: int) -> int:
        with self.connect() as connection:
            user_id = self._get_user_id(connection, username)
            self._get_owned_board_row(connection, user_id, board_id)

            existing_chat_row = connection.execute(
                "SELECT id FROM chats WHERE board_id = ?", (board_id,)
            ).fetchone()
            if existing_chat_row is not None:
                existing_chat_id = int(existing_chat_row["id"])
                connection.execute(
                    "DELETE FROM chat_messages WHERE chat_id = ?", (existing_chat_id,)
                )
                connection.execute("DELETE FROM chats WHERE id = ?", (existing_chat_id,))

            timestamp = current_timestamp()
            cursor = connection.execute(
                """
                INSERT INTO chats (user_id, board_id, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, board_id, timestamp, timestamp),
            )
            return int(cursor.lastrowid)

    def list_chat_history(self, username: str, board_id: int) -> list[dict[str, str]]:
        with self.connect() as connection:
            user_id = self._get_user_id(connection, username)
            chat_id = self._get_or_create_chat_id(connection, user_id, board_id)
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
        board_id: int,
        role: str,
        content: str,
        board_state_id: int,
    ) -> tuple[int, ChatMessageRecord]:
        with self.connect() as connection:
            user_id = self._get_user_id(connection, username)
            chat_id = self._get_or_create_chat_id(connection, user_id, board_id)
            row = self._insert_chat_message(
                connection=connection,
                chat_id=chat_id,
                role=role,
                content=content,
                board_state_id=board_state_id,
            )
            return chat_id, self._chat_message_from_row(row)

    def _get_or_create_chat_id(
        self, connection: sqlite3.Connection, user_id: int, board_id: int
    ) -> int:
        self._get_owned_board_row(connection, user_id, board_id)

        row = connection.execute(
            "SELECT id FROM chats WHERE board_id = ?", (board_id,)
        ).fetchone()
        if row is not None:
            return int(row["id"])

        timestamp = current_timestamp()
        cursor = connection.execute(
            """
            INSERT INTO chats (user_id, board_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, board_id, timestamp, timestamp),
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
