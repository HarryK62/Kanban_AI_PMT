from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_root_serves_html_placeholder() -> None:
    client = TestClient(create_app(frontend_out_dir=Path("/tmp/does-not-exist")))
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "FastAPI hello world is running." in response.text


def test_api_hello_returns_message() -> None:
    client = TestClient(create_app(frontend_out_dir=Path("/tmp/does-not-exist")))
    response = client.get("/api/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "hello from fastapi"}


def test_root_serves_static_frontend_when_built(tmp_path: Path) -> None:
    frontend_out_dir = tmp_path / "out"
    frontend_out_dir.mkdir()
    (frontend_out_dir / "index.html").write_text(
        "<!DOCTYPE html><html><body><h1>Kanban Studio</h1></body></html>",
        encoding="utf-8",
    )

    client = TestClient(create_app(frontend_out_dir=frontend_out_dir))
    response = client.get("/")

    assert response.status_code == 200
    assert "Kanban Studio" in response.text
