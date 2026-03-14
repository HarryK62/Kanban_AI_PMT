# Project Management MVP

## Testing

### Backend tests

```bash
cd backend
uv sync
uv run pytest
```

### Docker smoke test

Start the app:

```bash
./scripts/start-mac.sh
```

Then verify:

```bash
curl -i http://127.0.0.1:8000/
curl -i http://127.0.0.1:8000/api/hello
```

Stop the app:

```bash
./scripts/stop-mac.sh
```

On Linux, use `scripts/start-linux.sh` and `scripts/stop-linux.sh`.
On Windows, use `scripts/start-windows.bat` and `scripts/stop-windows.bat`.
