# Database Design

This document defines the MVP persistence model for the Project Management app.

## Recommendation

Use SQLite with:

- a relational `users` table
- a relational `boards` table
- a relational `board_states` table containing immutable board snapshots

This keeps board identity separate from board state. Each board state is an immutable revision of the board at one moment in time, and the board points to its current state.

## Why this approach

- The board is naturally modeled as a single object snapshot.
- Undo and redo require revision history, not just current state.
- Chat messages need to be associated with the board state that was visible at that turn.
- Full snapshots are simpler and safer than custom diff logic for the MVP.
- The backend can still validate the full board document with the current `Board` schema.

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
- `user_id` integer not null unique references `users(id)`
- `current_board_state_id` integer not null unique references `board_states(id)`
- `created_at` text not null
- `updated_at` text not null

Notes:

- `boards` is the stable board identity for a user.
- `current_board_state_id` points to the latest visible board state.
- One board per user remains the MVP rule.

### `board_states`

Columns:

- `id` integer primary key
- `board_id` integer not null references `boards(id)`
- `previous_board_state_id` integer references `board_states(id)`
- `board_json` text not null
- `created_at` text not null

Notes:

- `board_states` stores immutable board snapshots.
- `previous_board_state_id` links revisions into a linear history for the MVP.
- Undo can move the board's current pointer back to a prior state.
- Redo can move the pointer forward again as long as that future state is still reachable in the revision chain.

Example DDL:

```sql
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS boards (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL UNIQUE,
  current_board_state_id INTEGER NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id),
  FOREIGN KEY (current_board_state_id) REFERENCES board_states(id)
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
  version: number;
  title: string;
  columns: Column[];
  cards: Record<string, Card>;
};
```

The revision model changes how the board is persisted, not the shape exchanged with the frontend.

## Default board creation

When a user exists but no board exists yet:

1. create a `board_states` row with the default board JSON
2. create a `boards` row for that user
3. point `boards.current_board_state_id` to the new board state
4. set `version` to `1`
5. set `title` to `"Kanban Studio"`

This should happen lazily on first board fetch or first board write.

## Update model

For the MVP, board updates should create new immutable board states:

- the frontend or AI produces the complete next board
- the backend validates it
- the backend inserts a new `board_states` row
- `previous_board_state_id` points to the board's former current state
- the backend updates `boards.current_board_state_id`
- the backend updates `boards.updated_at`

This preserves history without requiring diff calculation.

## Undo and redo model

This design supports history-aware board navigation:

- undo moves `boards.current_board_state_id` to `previous_board_state_id`
- redo can move forward to a known later state if the application keeps track of the next state to reapply

For the MVP, explicit undo and redo UI is still out of scope, but the persistence model supports adding it later without redesigning storage.

## Versioning and migrations

Use `board_json.version` for board-document evolution.

Initial rule:

- current board format is `version: 1`

If the board shape changes later:

1. read the targeted board state JSON
2. inspect `version`
3. migrate older versions to the latest supported version in backend code
4. save the migrated result back as a new board state when appropriate

This avoids needing a normalized schema migration for every board-shape change.

## Out of scope for MVP

- normalized relational card tables
- collaborative editing
- branching board histories
- diff-based board storage
- explicit undo and redo UI
- server-side authentication/session management

## Approval request

The proposed MVP design is:

- SQLite database
- `users`, `boards`, and `board_states` relational tables
- one board per user
- immutable board snapshots in `board_states.board_json`
- `boards.current_board_state_id` as the current-state pointer
- backend validation of each board snapshot before persistence

This is the design that should be approved before backend persistence implementation continues.
