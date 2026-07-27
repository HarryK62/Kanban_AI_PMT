# Project Management MVP

Start here:

- Read the plan: [docs/PLAN.md](/Users/wesley/code/ai-coding/pm/docs/PLAN.md)
- Database design: [docs/DATABASE.md](/Users/wesley/code/ai-coding/pm/docs/DATABASE.md)
- Chat design: [docs/CHAT.md](/Users/wesley/code/ai-coding/pm/docs/CHAT.md)

## Current stack

- Frontend: Next.js in `frontend/`
- Backend: FastAPI in `backend/`
- Persistence: SQLite in `backend/data/` with immutable board states
- Packaging: Docker from the project root
- AI provider: OpenRouter with model `openai/gpt-oss-120b`

## Environment

Create `.env` from `.env.example` at the project root.

Current required variable:

```env
OPENROUTER_API_KEY=your_key_here
```

## Repo layout

- `frontend/`: Next.js app, unit tests, Playwright tests
- `backend/`: FastAPI app, SQLite persistence, backend tests
- `scripts/`: start/stop scripts for macOS, Linux, and Windows
- `docs/`: plan and design notes

## Backend dev

Install backend dependencies:

```bash
cd backend
uv sync
```

Notes:

- local `uv sync` installs the development dependencies used for testing
- Docker uses `uv sync --no-dev` for the lean runtime image

Run backend tests:

```bash
cd backend
uv run pytest
```

Run the backend locally:

```bash
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Frontend dev

Install frontend dependencies:

```bash
cd frontend
npm ci
```

Run the frontend locally:

```bash
cd frontend
npm run dev
```

Run frontend unit tests:

```bash
cd frontend
npm run test:unit
```

Build the static frontend export:

```bash
cd frontend
npm run build
```

## Docker app

The start and stop scripts below use Docker Compose so the app appears as a project in Docker Desktop.

Start the full app from the project root:

```bash
./scripts/start-mac.sh
```

Linux:

```bash
./scripts/start-linux.sh
```

Windows:

```bat
scripts\start-windows.bat
```

Stop the full app from the project root:

```bash
./scripts/stop-mac.sh
```

Linux:

```bash
./scripts/stop-linux.sh
```

Windows:

```bat
scripts\stop-windows.bat
```

## Smoke checks

With the app running:

```bash
curl -i http://127.0.0.1:8000/
curl -i http://127.0.0.1:8000/api/hello
curl -i http://127.0.0.1:8000/api/board/user
curl -i -X POST http://127.0.0.1:8000/api/ai/test
```

## Browser tests against the integrated app

Start the app first, then run:

```bash
cd frontend
npm run test:e2e:integration
```

## Current behavior

- Login is frontend-only with `user` / `password`
- The frontend uses the backend board API as its source of truth
- The backend auto-creates a default board for a user on first fetch
- AI connectivity is available at `POST /api/ai/test`

## Working rule

Use [docs/PLAN.md](/Users/wesley/code/ai-coding/pm/docs/PLAN.md) as the execution checklist and this README as the practical runbook.
