# Chat Design

This document defines the MVP chat persistence model for the Project Management app.

## Recommendation

Use SQLite with:

- a relational `chats` table
- a relational `chat_messages` table
- each chat message linked to the board state visible for that turn

This keeps the chat session explicit, keeps message ordering explicit, and ties each turn to the board context that actually existed when that turn happened.

## Why this approach

- A chat session is a real domain concept, not just an implied stream of user messages.
- Message order is part of the business meaning and should be represented directly.
- The board state visible during a message is part of that message's context.
- Linking messages to immutable board states is simpler and more reliable than reconstructing context from inferred diffs.
- The model supports future undo and redo behavior because board state history is preserved independently.

## Database schema

### `chats`

Columns:

- `id` integer primary key
- `user_id` integer not null references `users(id)`
- `created_at` text not null
- `updated_at` text not null

Notes:

- For the MVP, each user has one active chat.
- A future "new chat" action can create another row without redesigning the schema.

### `chat_messages`

Columns:

- `id` integer primary key
- `chat_id` integer not null references `chats(id)`
- `sequence_number` integer not null
- `role` text not null
- `content` text not null
- `board_state_id` integer not null references `board_states(id)`
- `created_at` text not null

Constraints:

- `UNIQUE(chat_id, sequence_number)`

Notes:

- `sequence_number` is the explicit ordering field within a chat.
- `board_state_id` points to the board state visible when the message was created.
- `role` is limited by application validation to `user` or `assistant`.

Example DDL:

```sql
CREATE TABLE IF NOT EXISTS chats (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
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
```

## Message model

The persisted message shape is conceptually:

```ts
type ChatMessage = {
  id: number;
  chatId: number;
  sequenceNumber: number;
  role: "user" | "assistant";
  content: string;
  boardStateId: number;
  createdAt: string;
};
```

The sequential relationship is derived from:

- the message's `chat_id`
- the message's `sequence_number`

The board context for that message is derived from:

- the message's `board_state_id`

That means the application can reconstruct both:

- the prior conversation in the same chat
- the exact board state visible at that turn

## Session meaning

A `Chat` is one accumulating context thread.

That means:

- each new message in a chat inherits the earlier messages in that chat as prior conversational context
- each message also has an explicit associated board state
- a new chat starts a new context thread

For the MVP, there is one active chat per user.

## MVP behavior

For the MVP:

1. get or create the user's board and current board state
2. get or create the user's single active chat
3. append the user's message with the next `sequence_number` and the current `board_state_id`
4. load the full ordered message history for that chat as AI context
5. send the history, the current board snapshot, and the latest user message to the AI
6. if the assistant returns no board change:
7. append an assistant message pointing to the same `board_state_id`
8. if the assistant returns a valid board change:
9. create a new `board_states` row linked to the prior current board state
10. move `boards.current_board_state_id` to the new board state
11. append the assistant message pointing to the new `board_state_id`

This keeps every chat turn tied to a concrete board snapshot.

## AI mutation rule

The AI is allowed full mutative permissions over the board for the MVP.

The permission boundary is:

- any new board state is allowed
- the board snapshot must satisfy the backend `Board` validation rules

This means the AI may create, edit, move, delete, rename, or otherwise reorganize board content as long as the resulting board is valid.

## Out of scope for MVP

- multiple active chats per user in the UI
- chat branching
- editing or deleting prior messages
- diff-based board history
- semantic command storage instead of board snapshots

## Approval request

The proposed MVP design is:

- SQLite database
- `chats` and `chat_messages` relational tables
- one active chat per user for the MVP
- message ordering enforced with `UNIQUE(chat_id, sequence_number)`
- each message linked to a `board_state_id`
- AI allowed to produce any valid next board state

This is the design that should be approved before Part 9 implementation starts.
