"""MOCKED security tests: accounts, sessions, CSRF, tenant isolation, rate limits and headers.

Users and sessions live in MemoryAccounts and projects in MemoryRegistry (conftest), so the same
code paths as production run without a database.
"""

import time

import pytest
from fastapi import Depends

from app import database
from app.main import app
from app.services import investigation_service
from app.services.investigation_service import InvestigationManager
from authclient import PASSWORD, Client, new_client, sign_up
from fakes import P1, FakeStore, FakeTools
from researchmind.agent import Investigator

QUESTION = "Do graph attention models generalize to unseen proteins?"


def signup(client, body):
    """POST /api/auth/signup the way the web form does: with a fresh form challenge."""
    return client.post("/api/auth/signup", json={"challenge": client.get("/api/forms/challenge").json()["challenge"], **body})


@pytest.fixture
def fake_data(memory_registry):
    """Each project gets its own FakeStore; investigations run offline over FakeTools."""
    stores: dict[str, FakeStore] = {}

    def store(project=Depends(database.get_project)):
        return stores.setdefault(project.id, FakeStore())
    manager = InvestigationManager(4, 30, investigator_factory=lambda s, **kw: Investigator(s, use_llm=False, tools=FakeTools()))
    app.dependency_overrides[database.get_store] = store
    app.dependency_overrides[investigation_service.get_manager] = lambda: manager
    yield stores
    app.dependency_overrides.pop(database.get_store, None)
    app.dependency_overrides.pop(investigation_service.get_manager, None)


# ---------------------------------------------------------------------- sign up / sign in

def test_sign_up_sign_in_sign_out(memory_accounts):
    client, user, pid = sign_up(email="Ada@Example.ORG", name="  Ada\u0000  Lovelace ")
    assert user["email"] == "Ada@example.org" and user["name"] == "Ada Lovelace"
    assert "password" not in str(user) and "hash" not in str(user)
    stored = memory_accounts.get_user(user["id"])
    assert stored.password_hash.startswith("$argon2id$") and PASSWORD not in stored.password_hash
    assert client.get("/api/auth/me").json()["id"] == user["id"]
    assert client.get("/api/auth/session").json()["user"]["id"] == user["id"]
    assert pid.startswith("prj_")

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    # The start-up check answers visitors with 200 and no user, never with account data.
    r = client.get("/api/auth/session")
    assert r.status_code == 200 and r.json() == {"user": None}

    again = new_client()
    r = again.post("/api/auth/login", json={"email": "ada@example.org", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["id"] == user["id"]
    assert again.get("/api/projects").json()["projects"][0]["id"] == pid  # same workspace, not a new one


def test_cookies_are_http_only_and_same_site():
    c = new_client()
    r = signup(c, {"email": "a@b.co", "name": "Alan Turing", "password": PASSWORD})
    cookies = r.headers.get_list("set-cookie")
    session = next(h for h in cookies if h.startswith("rm_session="))
    csrf = next(h for h in cookies if h.startswith("rm_csrf="))
    assert "HttpOnly" in session and "SameSite=lax" in session and "Path=/" in session
    assert "HttpOnly" not in csrf and "SameSite=strict" in csrf


@pytest.mark.parametrize("password, message", [
    ("short", "at least 12"), ("x" * 129, "at most 128"), ("aaaaaaaaaaaaaaaa", "too common"),
    ("password1234", "too common"), ("lovelace-is-great", "email address or name"),
])
def test_password_policy(password, message):
    r = signup(new_client(), {"email": "ada@example.org", "name": "Ada Lovelace", "password": password})
    assert r.status_code == 422 and message in r.json()["error"]["message"]
    assert password not in r.text or len(password) < 6


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "a b@c.de", "x@" + "a" * 300 + ".com"])
def test_invalid_emails_are_rejected(email):
    r = signup(new_client(), {"email": email, "name": "Ada Lovelace", "password": PASSWORD})
    assert r.status_code == 422


def test_duplicate_email_case_insensitive():
    sign_up(email="ada@example.org")
    r = signup(new_client(), {"email": "ADA@example.org", "name": "Other", "password": PASSWORD})
    assert r.status_code == 409


def test_wrong_password_and_unknown_email_look_the_same():
    sign_up()
    c = new_client()
    wrong = c.post("/api/auth/login", json={"email": "ada@example.org", "password": "nope-nope-nope-1"})
    unknown = c.post("/api/auth/login", json={"email": "nobody@example.org", "password": "nope-nope-nope-1"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_account_locks_after_repeated_failures(memory_accounts):
    _, user, _ = sign_up()
    c = new_client()
    for _ in range(8):
        c.post("/api/auth/login", json={"email": "ada@example.org", "password": "wrong-password-0"})
    assert memory_accounts.get_user(user["id"]).locked_until > time.time()
    r = c.post("/api/auth/login", json={"email": "ada@example.org", "password": PASSWORD})
    assert r.status_code == 401  # even the right password is refused while locked


def test_auth_endpoints_are_rate_limited():
    c = new_client()
    codes = [c.post("/api/auth/login", json={"email": "x@example.org", "password": "whatever-123456"}).status_code
             for _ in range(25)]
    assert codes[0] == 401 and codes[-1] == 429
    r = c.post("/api/auth/login", json={"email": "x@example.org", "password": "whatever-123456"})
    assert int(r.headers["Retry-After"]) > 0


def test_validation_errors_never_echo_passwords():
    r = new_client().post("/api/auth/login", json={"email": "a@b.co", "password": "s3cret-value-xyz", "extra": 1})
    assert r.status_code == 422 and "s3cret-value-xyz" not in r.text


def test_signup_can_be_disabled(monkeypatch):
    from dataclasses import replace
    from app.config import get_api_settings
    from app.routes import auth as auth_routes
    closed = replace(get_api_settings(), allow_signup=False)
    monkeypatch.setattr(auth_routes, "get_api_settings", lambda: closed)
    r = signup(new_client(), {"email": "a@b.co", "name": "Ada Lovelace", "password": PASSWORD})
    assert r.status_code == 403


# ---------------------------------------------------------------------- sessions

def test_sessions_are_revoked_server_side(memory_accounts):
    client, user, _ = sign_up()
    stolen = client.cookies.get("rm_session")
    client.post("/api/auth/logout")
    thief = Client(app)
    thief.cookies.set("rm_session", stolen)
    assert thief.get("/api/auth/me").status_code == 401
    assert memory_accounts.list_sessions(user["id"]) == []


def test_session_tokens_are_stored_hashed(memory_accounts):
    client, user, _ = sign_up()
    token = client.cookies.get("rm_session")
    ids = [s.id for s in memory_accounts.list_sessions(user["id"])]
    assert token not in ids and len(ids[0]) == 64


def test_idle_and_expired_sessions_are_rejected(memory_accounts):
    client, user, _ = sign_up()
    session = memory_accounts.list_sessions(user["id"])[0]
    memory_accounts.sessions[session.id].last_seen_at = time.time() - 25 * 3600
    assert client.get("/api/auth/me").status_code == 401
    assert memory_accounts.list_sessions(user["id"]) == []


def test_sign_in_replaces_the_previous_session(memory_accounts):
    client, user, _ = sign_up()
    before = {s.id for s in memory_accounts.list_sessions(user["id"])}
    client.post("/api/auth/login", json={"email": "ada@example.org", "password": PASSWORD})
    after = {s.id for s in memory_accounts.list_sessions(user["id"])}
    assert len(after) == 1 and not (before & after)


def test_password_change_signs_out_other_sessions(memory_accounts):
    laptop, user, _ = sign_up()
    phone = new_client()
    phone.post("/api/auth/login", json={"email": "ada@example.org", "password": PASSWORD})
    assert laptop.post("/api/auth/password", json={"current_password": "wrong-one-123456", "new_password": "x" * 20}).status_code == 403
    r = laptop.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "amber-glacier-meadow-77"})
    assert r.status_code == 204
    assert laptop.get("/api/auth/me").status_code == 200
    assert phone.get("/api/auth/me").status_code == 401
    assert new_client().post("/api/auth/login", json={"email": "ada@example.org", "password": PASSWORD}).status_code == 401
    assert new_client().post("/api/auth/login", json={"email": "ada@example.org", "password": "amber-glacier-meadow-77"}).status_code == 200


def test_list_and_revoke_other_sessions():
    laptop, _, _ = sign_up()
    phone = new_client()
    phone.post("/api/auth/login", json={"email": "ada@example.org", "password": PASSWORD})
    sessions = laptop.get("/api/auth/sessions").json()["sessions"]
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    assert laptop.delete("/api/auth/sessions").status_code == 204
    assert phone.get("/api/auth/me").status_code == 401 and laptop.get("/api/auth/me").status_code == 200


def test_profile_settings():
    client, _, _ = sign_up()
    r = client.patch("/api/auth/me", json={"theme": "dark", "language": "ta", "name": "Ada King"})
    assert r.status_code == 200 and r.json()["theme"] == "dark" and r.json()["language"] == "ta"
    assert client.patch("/api/auth/me", json={"language": "klingon"}).status_code == 422
    assert client.patch("/api/auth/me", json={"email": "new@example.org"}).status_code == 422  # not changeable here


# ---------------------------------------------------------------------- CSRF / cross-site

def test_state_changes_need_the_csrf_token():
    client, _, _ = sign_up()
    raw = Client(app, cookies=client.cookies)
    r = raw.request("POST", "/api/projects", json={"name": "X"}, headers={"X-CSRF-Token": "forged"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_failed"
    assert raw.post("/api/projects", json={"name": "X"}, headers={"X-CSRF-Token": ""}).status_code == 403
    assert client.post("/api/projects", json={"name": "X"}).status_code == 201  # the real app's request


@pytest.mark.parametrize("headers", [{"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"}, {"Origin": "null"}])
def test_cross_site_requests_are_refused(headers):
    client, _, _ = sign_up()
    r = client.post("/api/projects", json={"name": "X"}, headers=headers)
    assert r.status_code == 403 and r.json()["error"]["code"] == "cross_site_request"


def test_allowed_origin_is_accepted():
    client, _, _ = sign_up()
    assert client.post("/api/projects", json={"name": "Y"}, headers={"Origin": "http://localhost:5173"}).status_code == 201


def test_browser_same_origin_requests_are_accepted_behind_a_proxy():
    """Behind a proxy Host is the API's own address; the browser's Sec-Fetch-Site still says same-origin."""
    client, _, _ = sign_up()
    page = {"Origin": "https://researchmind.vercel.app", "Sec-Fetch-Site": "same-origin"}
    assert client.post("/api/projects", json={"name": "Z"}, headers=page).status_code == 201
    sibling = {"Origin": "https://evil.example", "Sec-Fetch-Site": "same-site"}
    assert client.post("/api/projects", json={"name": "Z"}, headers=sibling).status_code == 403


# ---------------------------------------------------------------------- tenant isolation

def test_everything_requires_sign_in(fake_data):
    _, _, pid = sign_up()
    anonymous = new_client()
    for method, url in [("GET", "/api/projects"), ("GET", f"/api/projects/{pid}/papers"),
                        ("GET", f"/api/projects/{pid}/graph/overview"), ("GET", f"/api/projects/{pid}/investigations"),
                        ("POST", f"/api/projects/{pid}/investigations"), ("GET", f"/api/projects/{pid}/papers/{P1}/file"),
                        ("GET", "/api/health"), ("GET", "/api/auth/sessions")]:
        r = anonymous.request(method, url, json={"question": QUESTION, "paper_id": P1} if method == "POST" else None)
        assert r.status_code == 401, (method, url, r.status_code)


def test_accounts_cannot_see_each_others_data(fake_data):
    alice, _, alice_pid = sign_up(email="alice@example.org", name="Alice Ball")
    bob, _, bob_pid = sign_up(email="bob@example.org", name="Bob Kahn")
    assert alice_pid != bob_pid
    inv = alice.post(f"/api/projects/{alice_pid}/investigations",
                     json={"question": QUESTION, "paper_id": P1, "wait": True}).json()
    assert inv["status"] == "completed"

    assert [p["id"] for p in bob.get("/api/projects").json()["projects"]] == [bob_pid]
    for method, url in [("GET", f"/api/projects/{alice_pid}"), ("GET", f"/api/projects/{alice_pid}/papers"),
                        ("GET", f"/api/projects/{alice_pid}/papers/{P1}"), ("GET", f"/api/projects/{alice_pid}/graph/stats"),
                        ("GET", f"/api/projects/{alice_pid}/investigations"),
                        ("GET", f"/api/projects/{alice_pid}/investigations/{inv['id']}"),
                        ("PATCH", f"/api/projects/{alice_pid}"), ("DELETE", f"/api/projects/{alice_pid}"),
                        ("DELETE", f"/api/projects/{alice_pid}/investigations/{inv['id']}")]:
        body = {"name": "pwned"} if method == "PATCH" else {"confirm_name": "My research"} if method == "DELETE" else None
        r = bob.request(method, url, json=body)
        assert r.status_code == 404, (method, url, r.status_code)
        assert "Alice" not in r.text and QUESTION not in r.text
    # Bob's own project URL with Alice's investigation id does not reach it either.
    assert bob.get(f"/api/projects/{bob_pid}/investigations/{inv['id']}").status_code == 404
    assert alice.get(f"/api/projects/{alice_pid}/investigations/{inv['id']}").status_code == 200


def test_delete_account_removes_all_data(fake_data, memory_accounts, memory_registry):
    client, user, pid = sign_up()
    client.post(f"/api/projects/{pid}/investigations", json={"question": QUESTION, "paper_id": P1, "wait": True})
    assert client.request("DELETE", "/api/auth/me", json={"password": "wrong-password-1"}).status_code == 403
    assert client.request("DELETE", "/api/auth/me", json={"password": PASSWORD}).status_code == 204
    assert memory_accounts.get_user(user["id"]) is None and memory_accounts.list_sessions(user["id"]) == []
    assert memory_registry.list_projects(user["id"]) == [] and memory_registry.investigations == {}
    assert client.get("/api/auth/me").status_code == 401
    assert new_client().post("/api/auth/login", json={"email": "ada@example.org", "password": PASSWORD}).status_code == 401


# ---------------------------------------------------------------------- hardening

def test_security_headers_on_api_responses():
    r = new_client().get("/api/health/live")
    h = r.headers
    assert h["X-Content-Type-Options"] == "nosniff" and h["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in h["Content-Security-Policy"] and "frame-ancestors 'none'" in h["Content-Security-Policy"]
    assert h["Referrer-Policy"] == "no-referrer" and "no-store" in h["Cache-Control"]
    assert h["Cross-Origin-Opener-Policy"] == "same-origin"


def test_oversized_json_bodies_are_refused():
    client, _, _ = sign_up()
    r = client.post("/api/projects", content=b"{" + b" " * (300 * 1024) + b"}",
                    headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_global_rate_limit(monkeypatch):
    from app.ratelimit import SlidingWindow, get_limiters
    monkeypatch.setattr(get_limiters(), "api", SlidingWindow(5, 60))
    c = new_client()
    codes = [c.get("/api/auth/me").status_code for _ in range(8)]
    assert codes[:4] == [401] * 4 and codes[-1] == 429


def test_investigations_per_hour_limit(fake_data, monkeypatch):
    from app.ratelimit import SlidingWindow, get_limiters
    monkeypatch.setattr(get_limiters(), "investigations", SlidingWindow(2, 3600))
    client, _, pid = sign_up()
    url = f"/api/projects/{pid}/investigations"
    codes = [client.post(url, json={"question": QUESTION, "paper_id": P1, "wait": True}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---------------------------------------------------------------------- spam protection, contact, analytics

def test_signup_needs_a_valid_form_challenge_and_empty_honeypot():
    c = new_client()
    body = {"email": "bot@example.org", "name": "Bot Builder", "password": PASSWORD}
    assert c.post("/api/auth/signup", json=body).status_code == 400            # no challenge (direct POST)
    assert c.post("/api/auth/signup", json={**body, "challenge": "1.2.forged"}).status_code == 400
    assert signup(c, {**body, "website": "http://spam.example"}).status_code == 400  # honeypot filled
    assert signup(c, body).status_code == 201


def test_form_challenge_is_signed_and_time_bound(monkeypatch):
    from app import security
    token = security.issue_form_challenge(now=1_000_000)
    monkeypatch.setattr(security, "FORM_MIN_SECONDS", 3)
    assert not security.check_form_challenge(token, now=1_000_001)          # too fast
    assert security.check_form_challenge(token, now=1_000_010)
    assert not security.check_form_challenge(token, now=1_000_000 + 3 * 3600)  # expired
    ts, nonce, sig = token.split(".")
    assert not security.check_form_challenge(f"{int(ts) - 60}.{nonce}.{sig}", now=1_000_010)  # tampered time


def test_contact_form(memory_accounts):
    from app import auth
    from app.main import app
    site = app.dependency_overrides[auth.get_site]()
    c = new_client()
    ch = c.get("/api/forms/challenge").json()["challenge"]
    ok = {"name": "Rosalind Franklin", "email": "rf@example.org", "topic": "feedback", "message": "The citations are very useful.",
          "challenge": ch}
    assert c.post("/api/contact", json={**ok, "message": "short"}).status_code == 422
    assert c.post("/api/contact", json={**ok, "email": "nope"}).status_code == 422
    assert c.post("/api/contact", json={**ok, "challenge": ""}).status_code == 400
    assert c.post("/api/contact", json=ok).status_code == 202
    assert c.post("/api/contact", json={**ok, "website": "spam"}).status_code == 202  # silently dropped
    assert [m.message for m in site.messages] == ["The citations are very useful."]


def test_analytics_store_only_aggregates(memory_accounts):
    from app import auth
    from app.main import app
    site = app.dependency_overrides[auth.get_site]()
    c = new_client()
    for _ in range(2):
        assert c.post("/api/analytics/event", json={"name": "page_view", "path": "/papers/p_0123456789ab",
                                                    "utm_source": "Newsletter"}).status_code == 204
    assert c.post("/api/analytics/event", json={"name": "page_view", "path": "javascript:alert(1)"}).status_code == 422
    assert c.post("/api/analytics/event", json={"name": "login_secret", "path": "/"}).status_code == 422
    assert c.post("/api/analytics/event", json={"name": "page_view", "path": "/", "ip": "1.2.3.4"}).status_code == 422
    rows = list(site.metrics.values())
    assert len(rows) == 1 and rows[0]["count"] == 2 and rows[0]["path"] == "/papers/:p" and rows[0]["utm_source"] == "newsletter"
    assert set(rows[0]) == {"day", "name", "path", "utm_source", "utm_medium", "utm_campaign", "count"}  # nothing personal


def test_admin_views_are_hidden_from_non_admins(monkeypatch, memory_accounts):
    from dataclasses import replace
    from app import auth as auth_mod
    from app.config import get_api_settings
    client, user, _ = sign_up()
    assert user["is_admin"] is False
    assert client.get("/api/admin/analytics").status_code == 404
    assert client.get("/api/admin/messages").status_code == 404
    assert new_client().get("/api/admin/analytics").status_code == 401
    admin_settings = replace(get_api_settings(), admin_emails=frozenset({"ada@example.org"}))
    monkeypatch.setattr(auth_mod, "get_api_settings", lambda: admin_settings)
    assert client.get("/api/auth/me").json()["is_admin"] is True
    stats = client.get("/api/admin/analytics?days=7").json()
    assert len(stats["series"]) == 7 and set(stats["totals"]) == {"page_view", "signup", "upload", "investigation"}
    assert client.get("/api/admin/messages").json() == {"messages": []}


# ---------------------------------------------------------------------- front proxy (Vercel)

@pytest.fixture
def behind_proxy(monkeypatch):
    """ORIGIN_SECRET set: the API only answers requests that carry it (Vercel adds it on every rewrite)."""
    from dataclasses import replace
    from app import middleware, ratelimit
    from app.config import get_api_settings
    proxied = replace(get_api_settings(), origin_secret="front-proxy-secret")
    monkeypatch.setattr(middleware, "get_api_settings", lambda: proxied)
    monkeypatch.setattr(ratelimit, "get_api_settings", lambda: proxied)
    return {"x-origin-secret": "front-proxy-secret"}


def test_requests_that_bypass_the_proxy_are_refused(behind_proxy):
    c = Client(app)
    assert c.get("/api/auth/me").status_code == 404
    assert c.get("/api/auth/me", headers={"x-origin-secret": "guess"}).status_code == 404
    assert c.get("/api/auth/me", headers=behind_proxy).status_code == 401
    assert c.get("/api/health/live").status_code == 200  # the platform's health check calls the API directly


def test_rate_limits_use_the_visitor_address_from_the_proxy(behind_proxy, monkeypatch):
    from app.ratelimit import SlidingWindow, get_limiters
    monkeypatch.setattr(get_limiters(), "api", SlidingWindow(3, 60))
    c = Client(app)
    one, two = {**behind_proxy, "x-real-ip": "203.0.113.1"}, {**behind_proxy, "x-real-ip": "203.0.113.2"}
    assert [c.get("/api/auth/me", headers=one).status_code for _ in range(4)] == [401, 401, 401, 429]
    assert c.get("/api/auth/me", headers=two).status_code == 401


def test_same_site_requests_through_the_proxy_are_accepted(behind_proxy):
    """Host is the API's own address behind Vercel; the visitor's address comes in x-forwarded-host."""
    c = Client(app)
    c.get("/api/auth/csrf", headers=behind_proxy)
    site = {**behind_proxy, "x-forwarded-host": "researchmind.vercel.app", "sec-fetch-site": "same-origin"}
    ok = c.post("/api/auth/logout", headers={**site, "origin": "https://researchmind.vercel.app"})
    assert ok.status_code == 204
    other = c.post("/api/auth/logout", headers={**site, "origin": "https://attacker.example"})
    assert other.status_code == 403 and other.json()["error"]["code"] == "cross_site_request"
