# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Backend**

```bash
cd backend && uv sync              # install dependencies
uv run pytest                      # run all backend tests
uv run pytest tests/test_main.py::test_name  # run a single test
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000  # run locally
```

**Frontend**

```bash
cd frontend && npm ci              # install dependencies
npm run dev                        # run locally
npm run test:unit                  # unit tests (vitest)
npm run build                      # static export to frontend/out/
npm run test:e2e:integration       # Playwright tests (requires app running)
```

**Docker (full stack)**

```bash
./scripts/start-mac.sh             # start
./scripts/stop-mac.sh              # stop
```

## Architecture

The app is a local kanban board with AI chat. FastAPI serves both the API and the Next.js static export.

```
backend/app/
  main.py        # app factory (create_app), all API routes
  models.py      # Pydantic domain models: Board, Card, Column, ChatReply, AiStructuredReply
  repository.py  # BoardRepository — all SQLite access
  ai.py          # OpenRouterClient, build_chat_messages
  auth.py        # password hashing (pbkdf2_hmac), token generation, username/password validation

frontend/src/
  lib/kanban.ts                  # BoardData type and pure board logic (moveCard, createId)
  components/AppShell.tsx        # auth gate, login form, session lifecycle
  components/KanbanBoard.tsx     # main board UI, backend API calls
  components/AiChatSidebar.tsx   # chat sidebar, sends/receives messages
```

**Data flow (multi-board)**

- Each user can own multiple boards. `KanbanBoard.tsx` fetches `GET /api/boards/{username}` on mount to list them (id, title, `current_board_state_id`), picks an active `board_id` (restores the previous selection if still present, else the first board), and renders a tab switcher in the header plus a "+ New board" control (`POST /api/boards/{username}`) and a per-board delete control (`DELETE /api/boards/{username}/{board_id}`).
- Selecting a board fetches its content via `GET /api/boards/{username}/{board_id}`, saves edits via `PUT /api/boards/{username}/{board_id}`, and resets that board's AI chat context via `POST /api/chat/{username}/{board_id}/session` — the chat sidebar always starts empty for whichever board is currently active.
- Chat messages are sent to `POST /api/chat/{username}/{board_id}/messages`, which calls OpenRouter with only that board's history/snapshot and returns both an AI reply and an updated board (if the AI chose to mutate it). The frontend replaces the board state in-place when a chat reply includes a board update.
- Signing up (`POST /api/auth/signup`) bootstraps one sample-filled default board (`BoardRepository.bootstrap_default_board`) so a new account always has something to open.

**Board invariants (enforced by `Board.validate_consistency`)**

- Exactly five columns with fixed ids in order: `col-backlog`, `col-discovery`, `col-progress`, `col-review`, `col-done`.
- Column ids are unique; each card appears in exactly one column; each card dict key matches its `id` field.
- Board mutations from AI are validated against these rules before being persisted.
- A user's *additional* boards (created via "+ New board") start with the five fixed columns but no cards (`repository.empty_board`); only the signup/seed bootstrap board is pre-filled with samples (`repository.default_board`).

**Storage**

SQLite at `backend/data/app.db`. `boards.user_id` has no uniqueness constraint — a user can have any number of boards. Board states are immutable append-only snapshots (`board_states.id` is a single autoincrementing sequence shared across every board in the database, so a freshly created board's first state id is not guaranteed to be `1`). `boards.current_board_state_id` points to each board's latest state. `chats` has a `UNIQUE` `board_id` — chat history is scoped per board, not per user, so switching boards switches AI context. `chat_messages` rows reference the `board_state_id` visible at that turn. `BoardRepository.initialize()` rebuilds the `boards`/`board_states`/`chats`/`chat_messages` tables in place if it detects the pre-multi-board schema (legacy `UNIQUE(user_id)` on `boards`, or `chats` missing `board_id`) — acceptable since `backend/data/` is a local, gitignored dev database with no production deployment.

**AI**

OpenRouter model `openai/gpt-oss-120b`. The AI is instructed to return JSON matching `AiStructuredReply`: `{"reply": "...", "board_update": null | {"kind": "replace_board", "board": {...}}}`. The backend validates the full returned board before persisting it.

**Auth**

Backend-authoritative. `users.password_hash` stores salted PBKDF2-HMAC-SHA256 hashes (`app/auth.py`); a seeded default account (`harry`/`kijanka`) is created on first `BoardRepository.initialize()`. `POST /api/auth/signup` validates username format and password strength (length/upper/lower/number/symbol) server-side and returns 400/409 on failure; `POST /api/auth/login` verifies credentials and both routes return a bearer `token` recorded in the `sessions` table. `POST /api/auth/logout` deletes the session row for the given token.

`GET/POST/PUT/DELETE /api/boards/{username}[/​{board_id}]` and `/api/chat/{username}/{board_id}/messages|session` all depend on `require_session`, which extracts the `Authorization: Bearer <token>` header, looks up its username via `BoardRepository.get_username_for_token`, and 401s if the token is missing/unknown or its username doesn't match the `{username}` path parameter. A `board_id` that exists but isn't owned by that user 404s (via `BoardNotFoundError`), rather than leaking another user's board. `AppShell.tsx` calls the auth routes instead of managing accounts in `localStorage`; the active session (`isAuthenticated`, username, token) lives in `sessionStorage`, so it resets on new window/refresh. `KanbanBoard.tsx` sends the token as `Authorization: Bearer <token>` on every board/chat fetch and calls `onLogout` automatically on a 401 response.

**Environment**

`backend/app/ai.py` loads `OPENROUTER_API_KEY` from a `.env` file at the project root via `python-dotenv` (not `backend/.env`).
