# Project Plan

This document is the execution plan for the Project Management MVP. It breaks the work into checklists, defines tests for each phase, and states the success criteria required before moving on.

## Working assumptions

- The app is a local-only MVP running in Docker.
- The frontend starts from the existing Next.js demo in `frontend/`.
- The backend will be a FastAPI app in `backend/`.
- Authentication begins as a frontend-only gate in the phase before frontend/backend integration.
- The persistent board state will be stored in SQLite as a JSON document, wrapped by a minimal relational schema.
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
  - `board_json` text or SQLite JSON column usage
  - `created_at`
  - `updated_at`

This keeps identity relational and keeps the kanban board as a single JSON document, which is the simplest fit for the MVP.

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
- A full-board replacement is simpler and more reliable than incremental patches for the MVP.
- Validation stays straightforward.
- The UI refresh logic becomes deterministic after AI actions.

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
- [x] Store login state on the frontend only for this phase.
- [x] Add a logout control.
- [x] Prevent direct access to the board UI until logged in.
- [x] Keep the UI consistent with the defined color scheme and current frontend style.

### Tests

- Frontend unit/integration tests:
  - valid credentials allow access
  - invalid credentials show an error
  - logout returns the user to the login screen
- Playwright flow:
  - visit `/`
  - log in
  - see the board
  - log out
  - confirm board is hidden again

### Success criteria

- The user must log in before seeing the board.
- The only accepted credentials are `user` / `password`.
- Login and logout are covered by automated tests.

## Part 5: Database Modeling

### Checklist

- [x] Write a short design note in `docs/` describing the SQLite storage approach.
- [x] Define the database schema for `users` and `boards`.
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
- [x] Implement backend model/service helpers for loading and saving board JSON.
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

- [ ] Define backend request and response models for AI chat.
- [ ] Send the current board JSON, conversation history, and latest user message to the AI.
- [ ] Instruct the AI to return the agreed structured output.
- [ ] Validate the AI response structure.
- [ ] Validate any returned board against the board JSON schema.
- [ ] Persist the board only if validation succeeds.
- [ ] Return both the assistant reply and the resulting board state to the frontend.

### Tests

- Backend unit tests for:
  - structured response parsing
  - board validation success
  - board validation failure
  - persistence after valid board update
  - no-op reply with no board update
- Integration tests with mocked OpenRouter responses covering valid and invalid outputs.

### Success criteria

- The backend can safely accept AI-generated board updates.
- Invalid AI output never corrupts stored board state.
- The API contract is deterministic for the frontend.

## Part 10: AI Chat Sidebar

### Checklist

- [ ] Design and implement a sidebar chat UI that fits the existing product style.
- [ ] Add message history rendering and message input.
- [ ] Connect the sidebar to the backend AI route.
- [ ] Show request progress and error states.
- [ ] Refresh or replace board state automatically after valid AI updates.
- [ ] Keep the UI responsive on desktop and mobile widths.

### Tests

- Frontend component/integration tests for chat UI behavior.
- Playwright end-to-end tests covering:
  - open app and log in
  - send a chat request
  - receive assistant reply
  - observe board update reflected in the UI when returned
- Manual usability pass for sidebar layout and board refresh behavior.

### Success criteria

- The user can chat with the AI from the board page.
- AI replies are visible in the sidebar.
- Valid AI board changes are reflected in the board automatically.

## Sequence gates

The following approvals are required before proceeding:

- After Part 1: user approves this plan.
- After Part 5: user approves the database design note.

The following behaviors should remain true throughout execution:

- Keep the MVP simple.
- Prefer root-cause fixes over speculative changes.
- Avoid unnecessary abstractions and extra features.
