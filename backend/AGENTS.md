# Backend Agent Notes

This directory contains the FastAPI backend for the Project Management MVP.

## Current state

- `app/main.py` defines the Part 2 scaffold application.
- `/` serves placeholder HTML from FastAPI so Docker and script wiring can be verified before frontend integration.
- `/api/hello` returns a simple JSON response for backend smoke testing.
- Python dependencies are defined in `pyproject.toml`.
- Local dependency installation should use `uv sync` from `backend/`.

## Testing

- Backend tests live in `tests/`.
- Run them with `uv run pytest`.

## Near-term direction

- Part 3 will replace the placeholder `/` HTML with the built frontend.
- Later parts will add SQLite persistence and OpenRouter integration.
