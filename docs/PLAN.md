# Project Plan

This document is the execution plan for the Project Management MVP. It breaks the work into checklists, defines tests for each phase, and states the success criteria required before moving on.

## Session status (2026-07-28): user management + multi-board — complete

The three "Additional completed work" entries below (parts 1-3, all dated 2026-07-28) cover one continuous session's work and are all **done, verified, and pushed** (`kanban-ai-pmt/main` at `6cb8183`):

- Part 1 — backend-authoritative user management (real signup/login/logout, hashed passwords, session tokens).
- Part 2 — session tokens actually enforced on the board/chat routes (closed part 1's known gap).
- Part 3 — multi-board-per-user support (closed part 2's next step): create/list/switch/delete boards, board-scoped AI chat.

Each part's own "Next step" note was resolved by the part that follows it, so none of those are open anymore. The only genuinely open follow-ups are the small polish items listed at the end of part 3 (replace the `window.prompt()` board-creation UI, support renaming a board's title outside of chat) — neither is a correctness or security gap, just UX polish for a future session.

## Additional completed work (2026-07-28, part 3): multi-board support

Replaced the one-board-per-user model with real multi-board support, now that every board/chat request is authenticated (previous entry's "next step").

- **CHANGED:** `boards.user_id` no longer has a `UNIQUE` constraint; a user can own any number of boards. `chats` now has a `UNIQUE` `board_id` (was `UNIQUE` `user_id`) so each board gets its own isolated AI chat thread instead of one chat shared across all of a user's boards.
- **ADDED:** `BoardRepository.initialize()` detects the old single-board schema (legacy `UNIQUE(user_id)` on `boards`, or `chats` missing `board_id`) and rebuilds those four tables in place — acceptable one-time data loss since `backend/data/` is a local, gitignored dev database with no production deployment.
- **ADDED:** `BoardRepository`: `create_board` (empty starter board, used for "+ New board"), `bootstrap_default_board` (sample-filled board, used once at signup/seed time), `list_boards`, `get_board`, `delete_board`; `replace_board`/chat methods now take an explicit `board_id`. New `UsernameNotFoundError`/`BoardNotFoundError` exceptions.
- **CHANGED:** API surface: `/api/board/{username}` and `/api/chat/{username}/messages|session` are replaced by `GET/POST /api/boards/{username}`, `GET/PUT/DELETE /api/boards/{username}/{board_id}`, and `POST /api/chat/{username}/{board_id}/messages|session`. A `board_id` that exists but belongs to a different user 404s rather than leaking content.
- **ADDED:** `POST /api/auth/signup` now also calls `bootstrap_default_board` so new accounts land with one sample-filled board.
- **CHANGED:** `KanbanBoard.tsx` fetches the board list on mount, renders a tab-style switcher (create/select/delete), and drives the active board's load/save/chat calls off the selected `board_id`. `AppShell.tsx` no longer eagerly starts a chat session at login — that's now board-scoped and owned by `KanbanBoard` (fires whenever the active board changes).
- **ADDED:** Backend tests for board list/create/delete, cross-user board isolation (own-path-but-someone-else's-board-id returns 404), and per-board chat history isolation, both at the repository level (`test_repository.py`) and the route level (`test_main.py`). Frontend: new Playwright flow that creates a second board, switches to it, and deletes it. All pre-existing tests updated to the new API shape.
- **Known test-environment note:** the "rename a column" Vitest test switched from `userEvent.clear()`/`userEvent.type()` to `fireEvent.change()`, because `userEvent`'s focus/selection simulation proved unreliable specifically once the board load became a two-step async sequence (board list, then the selected board's content) — worth remembering if similar flakiness shows up in future input-editing tests.
- Full verification pass: backend pytest (53 passed, +15 new), frontend vitest (22 passed), Playwright integration suite (9 passed, +1 new), `next build` and `eslint` clean.
- **Next steps:** the board switcher's "create board" flow uses a bare `window.prompt()` for the title — worth replacing with an inline form for a more polished UX; board titles aren't yet renameable after creation without going through a chat request.

## Additional completed work (2026-07-28, part 2): enforce session tokens on board/chat routes

Closed the "known gap" left by the previous change: the bearer token is now actually checked, not just issued.

- **ADDED:** `require_session` dependency in `backend/app/main.py` — extracts `Authorization: Bearer <token>`, resolves it via `BoardRepository.get_username_for_token`, and 401s if the token is missing, unknown, or belongs to a different username than the `{username}` path parameter.
- **CHANGED:** `GET/PUT /api/board/{username}` and `POST /api/chat/{username}/messages|session` all depend on `require_session`.
- **CHANGED:** `KanbanBoard.tsx` now takes a required `token` prop, sends `Authorization: Bearer <token>` on every board/chat fetch, and calls `onLogout` automatically when a request comes back 401 (e.g. an expired/invalidated session). `AppShell.tsx` passes its stored `authToken` through.
- **ADDED:** Backend tests for the two new failure modes (missing token, token for a different user) plus updated every existing board/chat test in `test_main.py` to sign up and authenticate first via a new `auth_headers()` helper.
- **ADDED:** Frontend tests: the bearer token is asserted on the board fetch, and a new test confirms a 401 board response triggers `onLogout`.
- Full verification pass: backend pytest (38 passed, +3 new), frontend vitest (22 passed, +2 new), Playwright integration suite (8 passed against the live enforced backend), `next build` and `eslint` clean.
- **Next step (done — see part 3 above):** multi-board-per-user support, now that every board/chat request is authenticated.

## Additional completed work (2026-07-28): backend-authoritative user management

Replaced the frontend-only `localStorage` account store with real backend accounts, as the first step of a broader "comprehensive PM application" push (multi-board support, further hardening) that will continue across follow-up sessions.

- **ADDED:** `backend/app/auth.py` — PBKDF2-HMAC-SHA256 password hashing with a random per-user salt, constant-time verification, secure token generation (`secrets.token_urlsafe`), username normalization, and server-side username-format/password-strength validation.
- **ADDED:** `sessions` table and a `password_hash` column migration (`ALTER TABLE ... ADD COLUMN`, applied idempotently in `BoardRepository.initialize()`) on the existing `users` table.
- **ADDED:** `BoardRepository.create_user/verify_login/create_session/get_username_for_token/delete_session`.
- **ADDED:** `POST /api/auth/signup`, `POST /api/auth/login`, `POST /api/auth/logout` routes with `SignupRequest`/`LoginRequest`/`AuthResponse` models. Signup returns 409 on duplicate username, 400 on invalid username/weak password; login returns 401 on bad credentials.
- **ADDED:** The default `harry`/`kijanka` account is now seeded server-side (hashed) on first database initialization, replacing the old frontend-hardcoded default.
- **CHANGED:** `AppShell.tsx` now calls `/api/auth/signup` and `/api/auth/login` instead of reading/writing `localStorage["pm:accounts"]`; the returned session token is stored in `sessionStorage` and sent as `Authorization: Bearer <token>` on the chat-session-start call and on `POST /api/auth/logout`.
- **Known gap (done — see parts 2 and 3 above):** `GET/PUT /api/board/{username}` and `/api/chat/{username}/*` did not yet verify the bearer token against the path username at the time of this entry. Part 2 added that enforcement; part 3 then replaced these routes entirely with the board-scoped `/api/boards/...` and `/api/chat/{username}/{board_id}/...` surface.
- Full verification pass: backend pytest (35 passed, +13 new auth tests), frontend vitest (20 passed, +2 new AppShell tests), Playwright integration suite (8 passed), `next build` and `eslint` clean.

## Additional completed work (2026-07-27, part 2)

Addressed the remaining medium- and low-priority findings from `docs/code_review.md` (2026-03-24), plus its noted test coverage gaps.

- **FIXED:** `OpenRouterClient` no longer raises `fastapi.HTTPException`; it raises `OpenRouterConfigurationError` (missing API key) or `OpenRouterRequestError` (upstream/malformed response), translated to `HTTPException` at the route level in `main.py`. `test_ai.py` no longer imports FastAPI.
- **FIXED:** The chat route's `except Exception` around AI reply parsing now catches only the specific exceptions that parsing can raise (`json.JSONDecodeError`, `KeyError`, `AttributeError`, `TypeError`, `ValueError`).
- **FIXED:** `anyio` is now an explicit dev dependency (`backend/pyproject.toml`) instead of relying on it being a transitive dependency of `httpx`/`starlette`; added `backend/tests/conftest.py` with an explicit `anyio_backend` fixture pinned to `"asyncio"`.
- **FIXED:** Removed the dead `get_or_create_chat` method from `BoardRepository` (all callers already used `_get_or_create_chat_id`).
- **FIXED:** Moved the function-local `import json` in `repository.py` and `ai.py` to module level.
- **FIXED:** Removed the redundant `CREATE UNIQUE INDEX` statements on `boards.user_id` and `boards.current_board_state_id` — both columns already have a column-level `UNIQUE` constraint.
- **FIXED:** `docs/DATABASE.md` now matches the actual DDL: `current_board_state_id` is documented as nullable (needed for the two-step board bootstrap), with no FK on that column.
- **FIXED:** Deduplicated the `ChatMessage` type (was defined identically in `KanbanBoard.tsx` and `AiChatSidebar.tsx`) into `frontend/src/lib/chat.ts`.
- **FIXED:** `KanbanBoard` now filters out any card lookup that resolves to `undefined` before passing cards to `KanbanColumn`, so a stale `cardIds` entry can't crash the render path.
- **ADDED:** Minimal "Saving..." indicator in the board header while a board save is in flight (previously only the initial load showed progress).
- **ADDED:** `frontend/tests/helpers.ts` with a `defaultBoard(overrides?)` helper; the Playwright chat-update test no longer inlines a full ~65-line board JSON payload.
- **ADDED:** Backend test coverage for previously untested paths: `replace_board` bootstrapping a board for a brand-new user in one PUT, and `append_chat_message` creating a chat row when none exists yet (new `backend/tests/test_repository.py`).
- **ADDED:** Frontend test coverage: chat error state rendering on a failed AI request, and the optimistic board update surviving a successful save.
- Full verification pass after the fixes: backend pytest (22 passed), frontend vitest (19 passed), Playwright integration suite (8 passed).

## Additional completed work (2026-07-27)

Addressed the four high-priority findings from `docs/code_review.md` (2026-03-24):

- **FIXED:** `BoardRepository.initialize()` now runs once in `create_app` instead of on every repository method call.
- **FIXED:** The user's chat message is now persisted only after the AI call succeeds, so a malformed/failed AI response no longer leaves an unanswered user turn in `chat_messages`. The in-flight user message is still included in the AI prompt context before being written to the database.
- **FIXED:** Column rename input debounces the `PUT /api/board/{username}` call (400ms) instead of firing one request per keystroke; the input itself still updates immediately for responsiveness.
- **FIXED:** `KanbanBoard` tracks a save generation counter so a stale in-flight board save can no longer overwrite a newer board state (covers both rapid manual edits and an AI chat board update landing while a prior save is still in flight).
- Updated `backend/tests/test_main.py` and `frontend/src/components/KanbanBoard.test.tsx` assertions to match the corrected behavior.
- Full verification pass after the fixes: backend pytest (20 passed), frontend vitest (17 passed), Playwright integration suite (8 passed).

## Additional completed work (2026-07-26)

The following implementation and stabilization work was completed after the initial plan draft and is now part of delivered scope.

- **ADDED:** Hardcoded login credentials changed from `user` / `password` to `harry` / `kijanka`.
- **ADDED:** Sign-in screen simplified to a single centered form (removed left-side credential panel).
- **ADDED:** Frontend auth expanded from single hardcoded credentials to local multi-account sign in and sign up.
- **ADDED:** Signup validation and security checks:
  - username format validation
  - password confirmation
  - password strength checks (length, upper/lowercase, number, symbol)
- **ADDED:** Auth test coverage expanded:
  - unit tests for signup success and weak-password rejection
  - Playwright integration test for new-user signup then sign in
- **ADDED:** AI chat UX hardening:
  - request timeout and submit-state failsafe to prevent stuck "submitting" UI
  - preserve typed message on failed send
  - consistent user-facing failure text: "Unable to reach the AI now."
- **ADDED:** Backend runtime reliability for AI calls:
  - automatic project-root `.env` loading via `python-dotenv`
  - verified OpenRouter connectivity with live `POST /api/ai/test`
- **ADDED:** Integration test stabilization:
  - Playwright locators made robust against duplicate text matches
  - drag-and-drop test made resilient to non-default board state
- **ADDED:** Full verification passes completed:
  - backend test suite
  - frontend unit tests
  - Playwright integration tests

## Working assumptions

- The app is a local-only MVP running in Docker.
- The frontend starts from the existing Next.js demo in `frontend/`.
- The backend will be a FastAPI app in `backend/`.
- Authentication begins as a frontend-only gate in the phase before frontend/backend integration.
- The persistent board state will be stored in SQLite as immutable board snapshots with a current-state pointer.
- AI calls will use OpenRouter with model `openai/gpt-oss-120b`.
- Each part should be completed and verified before moving to the next part.

## Proposed persistent data shape

### Database approach

- `users` table
  - `id`
  - `username` unique
  - `created_at`
- `boards` table
  - `id`
  - `user_id` unique
  - `current_board_state_id`
  - `created_at`
  - `updated_at`
- `board_states` table
  - `id`
  - `board_id`
  - `previous_board_state_id`
  - `board_json`
  - `created_at`

This keeps board identity relational while making each board state immutable and addressable. That fits chat context better and supports future undo/redo without switching persistence models later.

### Board JSON schema

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

Notes:

- `columns` preserves visible column order.
- `cardIds` preserves card order within a column.
- `cards` is a dictionary keyed by card id for simple updates.
- `version` allows later migrations without redesigning storage.

## Proposed AI structured output contract

The backend AI route should eventually return a single structured payload with both chat text and an optional board mutation.

```json
{
  "reply": "I moved the analytics task into In Progress and added a follow-up card for QA.",
  "board_update": {
    "kind": "replace_board",
    "board": {
      "version": 1,
      "title": "Kanban Studio",
      "columns": [],
      "cards": {}
    }
  }
}
```

Rules:

- `reply` is always required.
- `board_update` is optional.
- For the MVP, `board_update.kind` should be `replace_board`.
- The backend validates the full returned board against the app's board schema before saving it.

Reasoning:

- Returning a full next-board snapshot is simpler and more reliable than incremental patches for the MVP.
- Validation stays straightforward.
- The UI refresh logic becomes deterministic after AI actions.
- The validated result can be persisted as a new immutable board state.

## Architecture note

After the original persistence design was approved, the domain model became clearer during chat design. In particular:

- each chat message needs an explicit relationship to the board state visible at that turn
- future undo and redo need board revision history
- immutable board snapshots are a better fit than a single mutable `boards.board_json`

The plan therefore changed from a single mutable board document to a revisioned `board_states` model before Part 9 implementation.

## Part 1: Plan and Documentation

### Checklist

- [x] Review the root instructions in `AGENTS.md`.
- [x] Review the current high-level plan in this file.
- [x] Inspect the existing frontend structure and tests.
- [x] Expand this file into a detailed execution plan.
- [x] Add tests and success criteria for each phase.
- [x] Document the current frontend codebase in `frontend/AGENTS.md`.
- [x] Get user approval on this plan before starting Part 2.

### Tests

- Manual review of this document for completeness and sequencing.
- Manual review of `frontend/AGENTS.md` against the current `frontend/` codebase.

### Success criteria

- The plan is specific enough to execute without guessing.
- Storage strategy and AI output strategy are documented.
- The user explicitly approves the plan.

## Part 2: Scaffolding

### Checklist

- [x] Create the backend project structure under `backend/`.
- [x] Add FastAPI app entrypoint and routing structure.
- [x] Define Python dependencies in `backend/pyproject.toml`.
- [x] Use `uv sync` as the local backend dependency setup flow.
- [x] Use the same `backend/pyproject.toml` dependency definition in Docker.
- [x] Add Dockerfile and any supporting container configuration.
- [x] Add start and stop scripts for macOS, Linux, and Windows in `scripts/`.
- [x] Serve a minimal HTML page from `/` through FastAPI.
- [x] Add a simple API route such as `/api/health` or `/api/hello`.
- [x] Ensure the container reads required environment variables from the project setup.
- [x] Add `.env.example`, require `.env`, and leave README unchanged because the script flow is currently self-explanatory.

### Tests

- Backend unit test for the example API route.
- Manual smoke test:
  - Start the app via the provided script.
  - Load `/` and confirm the example HTML renders.
  - Call the example API route and confirm it responds.
- Container smoke test:
  - Build the Docker image.
  - Run the container locally.
  - Confirm both page and API work inside the containerized setup.

### Success criteria

- A local Dockerized hello-world stack works end to end.
- Backend routing and script entrypoints are in place for later phases.
- The root page and at least one API route are served by FastAPI.

## Part 3: Add in Frontend

### Checklist

- [x] Decide the static export/build strategy for the Next.js app.
- [x] Adapt the frontend build output so FastAPI can serve it at `/`.
- [x] Preserve the existing board behavior and styling.
- [x] Wire the backend root route to serve the built frontend assets instead of example HTML.
- [x] Keep local development flow practical for frontend iteration.
- [x] Add or adjust tests for the integrated static-serving setup.

### Tests

- Existing frontend unit tests still pass.
- Existing frontend Playwright tests still pass against the integrated app.
- Manual test:
  - Build frontend assets.
  - Start the backend.
  - Confirm `/` renders the demo kanban board, not placeholder HTML.

### Success criteria

- The demo Kanban board is visible at `/` when served through FastAPI.
- No core board interactions regress during integration.
- The frontend remains buildable in a deterministic way.

## Part 4: Fake User Sign In

### Checklist

- [x] Add a login screen shown before the board is accessible.
- [x] Implement hardcoded credential check for `user` / `password`.
- [x] **ADDED:** Update hardcoded credential check to `harry` / `kijanka`.
- [x] **ADDED:** Replace single-user hardcoded auth with local multi-account auth.
- [x] **ADDED:** Add sign-up mode with explicit "New here? Sign up" toggle.
- [x] **ADDED:** Add password-strength checks and confirm-password validation for signup.
- [x] Store login state on the frontend only for this phase.
- [x] Add a logout control.
- [x] Prevent direct access to the board UI until logged in.
- [x] Keep the UI consistent with the defined color scheme and current frontend style.

### Tests

- Frontend unit/integration tests:
  - valid credentials allow access
  - invalid credentials show an error
  - signup creates a new account and allows login
  - weak signup password is rejected
  - logout returns the user to the login screen
- Playwright flow:
  - visit `/`
  - sign up a new user
  - log in
  - see the board
  - log out
  - confirm board is hidden again

### Success criteria

- The user must log in before seeing the board.
- The app supports multiple local accounts created through signup.
- Signup enforces password-strength and confirmation checks.
- Login and logout are covered by automated tests.

## Part 5: Database Modeling

### Checklist

- [x] Write a short design note in `docs/` describing the SQLite storage approach.
- [x] Define the database schema for `users`, `boards`, and `board_states`.
- [x] Define the JSON schema for the board document.
- [x] Document how a default board is created for a new user.
- [x] Document how versioning and future board migrations would work.
- [x] Get explicit user sign-off on the database design before implementing it.

### Tests

- Manual review of the design doc for clarity and MVP scope.
- Validate that the proposed board JSON shape matches the current frontend model.

### Success criteria

- The persistence design is documented and approved.
- The storage model is simple enough for the MVP and extensible enough for later phases.

## Part 6: Backend API

### Checklist

- [x] Add SQLite initialization on backend startup or first use.
- [x] Create tables if they do not already exist.
- [x] Implement backend model/service helpers for loading and saving board state.
- [x] Implement API routes to fetch the current user's board.
- [x] Implement API routes to replace the current user's board.
- [x] Return consistent JSON responses and clear error handling.
- [x] Seed a default board for a user when no board exists yet.

### Tests

- Backend unit tests for:
  - database initialization
  - default board creation
  - fetching board state
  - replacing board state
  - invalid payload rejection
- Integration test with a temporary SQLite database file.

### Success criteria

- The backend can create, read, and update a board for a user.
- The database is created automatically if missing.
- Invalid board payloads are rejected cleanly.

## Part 7: Frontend + Backend

### Checklist

- [x] Replace in-memory board initialization with backend fetch on load.
- [x] Send board updates to the backend when the user renames columns, adds cards, deletes cards, or moves cards.
- [x] Add loading and error states that are minimal but usable.
- [x] Preserve the current board interactions and visual design.
- [x] Ensure the login flow and the chosen user identity line up with backend requests.

### Tests

- Frontend integration tests with mocked API responses.
- Backend integration tests remain green.
- Playwright end-to-end tests covering:
  - login
  - page refresh persistence
  - rename column persistence
  - add card persistence
  - move card persistence
  - delete card persistence

### Success criteria

- Board changes persist across reloads.
- Frontend and backend exchange the same board JSON shape.
- Core board interactions remain stable under persistence.

## Part 8: AI Connectivity

### Checklist

- [x] Add backend configuration for `OPENROUTER_API_KEY`.
- [x] Implement a minimal OpenRouter client in the backend.
- [x] Add a temporary test route or service path to send a simple prompt.
- [x] Use model `openai/gpt-oss-120b`.
- [x] Confirm a basic prompt such as `2+2` returns a valid response.
- [x] Add minimal error handling for missing API key and upstream failures.
- [x] **ADDED:** Load `.env` automatically from project root in backend runtime so `OPENROUTER_API_KEY` is available during local runs.

### Tests

- Backend unit tests for request construction and response parsing using mocks.
- Manual connectivity test with a real API key:
  - send `2+2`
  - confirm the response is sensible
- Manual failure test:
  - missing API key returns a clean backend error

### Success criteria

- The backend can successfully call OpenRouter.
- Configuration errors and upstream failures are surfaced clearly.
- The chosen model is wired through configuration or code in one obvious place.

## Part 9: AI Board Mutation API

### Checklist

- [x] Write a short design note in `docs/` describing chat persistence and sequencing.
- [x] Define the database schema for `chats` and `chat_messages`.
- [x] Define how message ordering is represented and enforced.
- [x] Define how each message relates to a visible `board_state_id`.
- [x] Get explicit user sign-off on the chat design before implementing it.
- [x] Define backend request and response models for AI chat.
- [x] Send the current board snapshot, conversation history, and latest user message to the AI.
- [x] Instruct the AI to return the agreed structured output.
- [x] Validate the AI response structure.
- [x] Validate any returned board against the board JSON schema.
- [x] Persist a new board state only if validation succeeds.
- [x] Return both the assistant reply and the resulting board state to the frontend.

### Tests

- Manual review of the chat design doc for clarity and MVP scope.
- Backend unit tests for:
  - structured response parsing
  - board validation success
  - board validation failure
  - persistence after valid board update
  - no-op reply with no board update
- Integration tests with mocked OpenRouter responses covering valid and invalid outputs.

### Success criteria

- The chat persistence design is documented and approved.
- The backend can safely accept AI-generated board updates.
- Invalid AI output never corrupts stored board state.
- The API contract is deterministic for the frontend.

## Part 10: AI Chat Sidebar

### Checklist

- [x] Update the chat flow so each login starts a fresh backend chat session for that user.
- [x] Keep backend chat persistence for the active session only; do not load prior session history into the UI.
- [x] Design and implement a sidebar chat UI that fits the existing product style.
- [x] Render only the current page session's messages in the sidebar and provide a message input.
- [x] Connect the sidebar to the backend AI route.
- [x] Show request progress and error states.
- [x] Refresh or replace board state automatically after valid AI updates.
- [x] Keep the UI responsive on desktop and mobile widths.
- [x] **ADDED:** Implement mobile bottom-sheet chat entry point.
- [x] **ADDED:** Preserve assistant reply when AI board update is invalid; ignore only invalid board mutation.
- [x] **ADDED:** Add chat request timeout and UI submit-state failsafe.
- [x] **ADDED:** Keep message text in input when send fails to support retry.

### Tests

- Frontend component/integration tests for chat UI behavior.
- Backend tests for starting a fresh chat session and clearing prior session context.
- Playwright end-to-end tests covering:
  - open app and log in
  - send a chat request
  - receive assistant reply
  - observe board update reflected in the UI when returned
- Manual usability pass for sidebar layout and board refresh behavior.
- **ADDED:** Playwright assertions hardened to avoid strict-locator collisions on repeated text and persisted board content.

### Success criteria

- The user can chat with the AI from the board page.
- Logging in starts a fresh backend chat context for that user.
- AI replies are visible in the sidebar for the current page session.
- Valid AI board changes are reflected in the board automatically.
- **ADDED:** Failed AI requests recover gracefully without leaving chat controls stuck disabled.

## Sequence gates

The following approvals are required before proceeding:

- After Part 1: user approves this plan.
- After Part 5: user approves the database design note.
- Before Part 9 implementation: user approves the chat design note.

The following behaviors should remain true throughout execution:

- Keep the MVP simple.
- Prefer root-cause fixes over speculative changes.
- Avoid unnecessary abstractions and extra features.
