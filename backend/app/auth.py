"""Authentication: session cookies, the current user, and CSRF tokens.

Session cookie: httpOnly, SameSite=Lax, Secure and `__Host-` prefixed when served over HTTPS
(COOKIE_SECURE / ENVIRONMENT=production). It holds an opaque random token; the server stores only
its SHA-256 and checks absolute expiry and inactivity on every request.

CSRF: double-submit token. A random token is set in a readable cookie; every state-changing
request must echo it in the `X-CSRF-Token` header (enforced in middleware.py). Cross-site pages
cannot read the cookie, so they cannot forge the header.
"""

from __future__ import annotations

import time

from fastapi import Depends, Request, Response

from researchmind.accounts import BaseAccounts, Session, User

from .config import get_api_settings
from .security import new_token, token_hash

TOUCH_EVERY_S = 300  # write last_seen_at at most this often


class AuthRequired(Exception):
    """No valid session. Mapped to HTTP 401."""


def session_cookie_name() -> str:
    return "__Host-rm_session" if get_api_settings().cookie_secure else "rm_session"


def csrf_cookie_name() -> str:
    return "__Host-rm_csrf" if get_api_settings().cookie_secure else "rm_csrf"


def set_session_cookie(response: Response, token: str, remember: bool) -> None:
    s = get_api_settings()
    response.set_cookie(session_cookie_name(), token, max_age=s.session_ttl_hours * 3600 if remember else None,
                        httponly=True, secure=s.cookie_secure, samesite="lax", path="/")


def clear_session_cookie(response: Response) -> None:
    s = get_api_settings()
    response.delete_cookie(session_cookie_name(), httponly=True, secure=s.cookie_secure, samesite="lax", path="/")


def set_csrf_cookie(response: Response, token: str | None = None) -> str:
    s = get_api_settings()
    token = token or new_token()
    # Readable by the page's JavaScript on purpose (double-submit); it grants nothing on its own.
    response.set_cookie(csrf_cookie_name(), token, max_age=s.session_ttl_hours * 3600, httponly=False,
                        secure=s.cookie_secure, samesite="strict", path="/")
    return token


def get_accounts() -> BaseAccounts:
    from .database import get_account_store
    return get_account_store()


def start_session(accounts: BaseAccounts, user: User, request: Request, response: Response, remember: bool) -> str:
    """Create a session for `user`, set its cookie and rotate the CSRF token. Returns the session id."""
    s = get_api_settings()
    token, now = new_token(), time.time()
    sid = token_hash(token)
    accounts.create_session(Session(id=sid, user_id=user.id, created_at=now, expires_at=now + s.session_ttl_hours * 3600,
                                    last_seen_at=now, user_agent=(request.headers.get("user-agent") or "")[:200]))
    set_session_cookie(response, token, remember)
    set_csrf_cookie(response)
    return sid


def current_session_id(request: Request) -> str | None:
    token = request.cookies.get(session_cookie_name())
    return token_hash(token) if token and len(token) <= 128 else None


def get_site():
    from .database import get_site_store
    return get_site_store()


def is_admin(user: User) -> bool:
    return user.email_lower in get_api_settings().admin_emails


def user_out(user: User) -> dict:
    """The signed-in user as the API returns it (never the password hash or lockout state)."""
    return {**user.public(), "is_admin": is_admin(user)}


def get_optional_user(request: Request, accounts: BaseAccounts = Depends(get_accounts)) -> User | None:
    """The signed-in user, or None for visitors (public forms work for both)."""
    try:
        return get_current_user(request, accounts)
    except AuthRequired:
        return None


def require_admin(request: Request, accounts: BaseAccounts = Depends(get_accounts)) -> User:
    """Admins only; everyone else gets the same 404 as for a route that does not exist."""
    from fastapi import HTTPException
    user = get_current_user(request, accounts)
    if not is_admin(user):
        raise HTTPException(404, "Not Found")
    return user


def get_current_user(request: Request, accounts: BaseAccounts = Depends(get_accounts)) -> User:
    """The signed-in user, or AuthRequired (401)."""
    cached = getattr(request.state, "user", None)
    if cached is not None:
        return cached
    sid = current_session_id(request)
    if not sid:
        raise AuthRequired()
    session = accounts.get_session(sid)
    now = time.time()
    s = get_api_settings()
    if session is None:
        raise AuthRequired()
    if session.expires_at <= now or session.last_seen_at + s.session_idle_hours * 3600 <= now:
        accounts.delete_session(sid)
        raise AuthRequired()
    user = accounts.get_user(session.user_id)
    if user is None:
        accounts.delete_session(sid)
        raise AuthRequired()
    if now - session.last_seen_at >= TOUCH_EVERY_S:
        accounts.touch_session(sid, now)
    request.state.user, request.state.session_id = user, sid
    return user
