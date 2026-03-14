# Project Management MVP

## Testing

### Backend tests

```bash
cd backend
uv sync
uv run pytest
```

### Frontend tests

```bash
cd frontend
npm ci
npm run test:unit
```

### Docker smoke test

Start the app from the project root:

```bash
./scripts/start-mac.sh
```

Then verify from the project root:

```bash
curl -i http://127.0.0.1:8000/
curl -i http://127.0.0.1:8000/api/hello
```

Run the integrated browser tests:

```bash
cd frontend
npm run test:e2e:integration
```

Stop the app from the project root:

```bash
./scripts/stop-mac.sh
```

On Linux, use `scripts/start-linux.sh` and `scripts/stop-linux.sh`.
On Windows, use `scripts/start-windows.bat` and `scripts/stop-windows.bat`.
