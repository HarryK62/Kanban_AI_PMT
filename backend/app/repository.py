import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.models import Board


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
                  user_id INTEGER NOT NULL,
                  board_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  FOREIGN KEY (user_id) REFERENCES users(id)
                );
                """
            )

    def get_or_create_board(self, username: str) -> Board:
        self.initialize()

        with self.connect() as connection:
            user_id = self._get_or_create_user(connection, username)
            row = connection.execute(
                """
                SELECT board_json
                FROM boards
                WHERE user_id = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()

            if row is None:
                board = default_board()
                serialized_board = json.dumps(
                    board.model_dump(by_alias=True),
                    separators=(",", ":"),
                )
                timestamp = current_timestamp()
                connection.execute(
                    """
                    INSERT INTO boards (user_id, board_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, serialized_board, timestamp, timestamp),
                )
                return board

            return Board.model_validate(json.loads(row["board_json"]))

    def replace_board(self, username: str, board: Board) -> Board:
        self.initialize()

        with self.connect() as connection:
            user_id = self._get_or_create_user(connection, username)
            existing_board = connection.execute(
                """
                SELECT id
                FROM boards
                WHERE user_id = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()

            serialized_board = json.dumps(
                board.model_dump(by_alias=True),
                separators=(",", ":"),
            )
            timestamp = current_timestamp()

            if existing_board is None:
                connection.execute(
                    """
                    INSERT INTO boards (user_id, board_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, serialized_board, timestamp, timestamp),
                )
                return board

            connection.execute(
                """
                UPDATE boards
                SET board_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (serialized_board, timestamp, existing_board["id"]),
            )
            return board

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
