# Database Design

This document defines the MVP persistence model for the Project Management app.

## Recommendation

Use SQLite with:

- a relational `users` table
- a relational `boards` table
- the full Kanban board stored as a single JSON document in `boards.board_json`

This is the simplest fit for the current product shape. The board is naturally a nested document with ordered columns, ordered card ids within each column, and card data keyed by id. Normalizing that structure into multiple relational tables would add implementation cost now without a clear MVP benefit.

## Why this approach

- The current frontend already models the board as one object.
- The MVP only needs one board per user.
- Full-board reads and writes are acceptable for the MVP.
- AI updates will be easier to validate if the backend works with one board document.
- SQLite handles text storage cleanly, and JSON validation can happen in the backend.

## Database schema

### `users`

Columns:

- `id` integer primary key
- `username` text not null unique
- `created_at` text not null

Notes:

- For the MVP, the only real user is `user`.
- The table still supports future multi-user expansion.

### `boards`

Columns:

- `id` integer primary key
- `user_id` integer not null references `users(id)`
- `board_json` text not null
- `created_at` text not null
- `updated_at` text not null

Notes:

- `board_json` stores the canonical board state.

Example DDL:

```sql
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
```

## Board JSON schema

The persisted board document should follow this shape:

```json
{
  "version": 1,
  "title": "Kanban Studio",
  "columns": [
    {
      "id": "col-backlog",
      "title": "Backlog",
      "cardIds": ["card-1", "card-2"]
    }
  ],
  "cards": {
    "card-1": {
      "id": "card-1",
      "title": "Align roadmap themes",
      "details": "Draft quarterly themes with impact statements and metrics."
    }
  }
}
```

Required rules:

- `version` is an integer.
- `title` is a string.
- `columns` is an ordered array.
- every column has:
  - `id` string
  - `title` string
  - `cardIds` ordered string array
- `cards` is an object keyed by card id
- every card has:
  - `id` string
  - `title` string
  - `details` string

Consistency rules enforced in backend validation:

- every `cardIds` entry must exist in `cards`
- every card id should appear in exactly one column
- every column id should be unique
- every card id should match its key in `cards`

## Relation to current frontend model

This matches the current frontend `BoardData` model:

```ts
type BoardData = {
  columns: Column[];
  cards: Record<string, Card>;
};
```

The only addition for persistence is top-level metadata:

- `version`
- `title`

That means the backend can preserve the current UI behavior without forcing a frontend redesign.

## Default board creation

When a user exists but no board exists yet:

1. create a board row for that user
2. use the current example board as the initial board
3. set `version` to `1`
4. set `title` to `"Kanban Studio"`

This should happen lazily on first board fetch or first board write. That keeps startup simple and avoids unnecessary seed logic.

## Update model

For the MVP, board updates should be full-document replacement:

- the frontend sends the complete board
- the backend validates it
- the backend overwrites `board_json`
- the backend updates `updated_at`

This is intentionally simple. Partial patching can be added later if needed, but it is not necessary for the MVP.

## Versioning and migrations

Use `board_json.version` for board-document evolution.

Initial rule:

- current board format is `version: 1`

If the board shape changes later:

1. read stored board JSON
2. inspect `version`
3. migrate older versions to the latest supported version in backend code
4. save the migrated result back when appropriate

This avoids needing a normalized schema migration for every board-shape change.

## Out of scope for MVP

- board history
- multiple boards per user
- collaborative editing
- relational card tables
- audit logs
- server-side authentication/session management

## Approval request

The proposed MVP design is:

- SQLite database
- `users` and `boards` relational tables
- one board per user
- full board state stored as JSON in `boards.board_json`
- backend validation of the board document before persistence

This is the design that should be approved before Part 6 implementation starts.
