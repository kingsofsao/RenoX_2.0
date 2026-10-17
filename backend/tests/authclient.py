"""A TestClient that behaves like the web app: keeps the session cookie and echoes the CSRF token."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

SAFE = {"GET", "HEAD", "OPTIONS"}
PASSWORD = "violet-harbour-lantern-42"


class Client(TestClient):
    def request(self, method, url, **kwargs):
        token = self.cookies.get("rm_csrf")
        if token and method.upper() not in SAFE:
            headers = dict(kwargs.pop("headers", None) or {})
            headers.setdefault("X-CSRF-Token", token)
            kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


def new_client() -> Client:
    c = Client(app)
    c.get("/api/auth/csrf")
    return c


def sign_up(client: Client | None = None, email: str = "ada@example.org", name: str = "Ada Lovelace",
            password: str = PASSWORD, **extra) -> tuple[Client, dict, str]:
    """Create an account and return (signed-in client, user, id of the user's first project)."""
    client = client or new_client()
    r = client.post("/api/auth/signup", json={"email": email, "name": name, "password": password, **extra})
    assert r.status_code == 201, r.text
    projects = client.get("/api/projects").json()["projects"]
    return client, r.json(), projects[0]["id"]
