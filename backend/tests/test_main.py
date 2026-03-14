from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_serves_html_placeholder() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "FastAPI hello world is running." in response.text


def test_api_hello_returns_message() -> None:
    response = client.get("/api/hello")

    assert response.status_code == 200
    assert response.json() == {"message": "hello from fastapi"}
