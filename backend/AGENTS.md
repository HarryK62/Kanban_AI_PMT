# Backend Agent Notes

This directory contains the FastAPI backend for the Project Management MVP.

## Current state

- `app/main.py` serves the exported frontend from `frontend/out` when that build output exists.
- If `frontend/out` does not exist yet, `/` falls back to the Part 2 placeholder HTML so backend-only work can still be smoke-tested.
- `/api/hello` returns a simple JSON response for backend smoke testing.
- `/api/board/{username}` supports `GET` and `PUT` for board persistence.
- `app/models.py` defines the Pydantic board schema and validation rules.
- `app/repository.py` handles SQLite initialization, default board creation, and board reads/writes.
- Python dependencies are defined in `pyproject.toml`.
- Local dependency installation should use `uv sync` from `backend/`.

## Testing

- Backend tests live in `tests/`.
- Run them with `uv run pytest`.

## Near-term direction

- Part 7 will connect the frontend to the board API.
- Later parts will add OpenRouter integration.
