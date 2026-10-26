import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("RECIPES_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    from recipekeeper.api import app
    return TestClient(app)


def signup(client, email="kristen@example.com", name="Kristen", **extra):
    r = client.post("/api/auth/signup", json={"email": email, "password": "cookies-123",
                                              "display_name": name, **extra})
    assert r.status_code == 200, r.text
    return r
