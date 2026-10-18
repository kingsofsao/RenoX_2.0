"""Sign up, sign in, sign out, profile settings, password change, sessions and account deletion."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from researchmind.accounts import BaseAccounts, LoginThrottle, User, new_user
from researchmind.projects import BaseRegistry

from ..auth import (clear_session_cookie, current_session_id, get_accounts, get_current_user, get_optional_user,
                    set_csrf_cookie, start_session, user_out)
from ..config import get_api_settings
from ..database import forget_project, get_registry
from ..ratelimit import client_ip, get_limiters
from ..schemas.auth import (AccountDelete, PasswordChange, ProfileUpdate, SessionList, SessionState, SignInRequest,
                            SignUpRequest, UserOut)
from ..security import (PasswordRejected, check_form_challenge, check_password, clean_name, hash_password, needs_rehash,
                        normalize_email, verify_password)
from ..services.investigation_service import InvestigationManager, get_manager

log = logging.getLogger("researchmind.api.auth")
router = APIRouter(prefix="/auth", tags=["auth"])
throttle = LoginThrottle()

BAD_CREDENTIALS = "Incorrect email or password. After repeated failures, sign-in is paused for 15 minutes."


def _limit_auth(request: Request) -> None:
    get_limiters().auth.hit(client_ip(request))


@router.get("/csrf", status_code=204)
def csrf(response: Response) -> None:
    """Issue a fresh CSRF token cookie (the middleware also sets one on any response that lacks it)."""
    set_csrf_cookie(response)


@router.post("/signup", response_model=UserOut, status_code=201)
def sign_up(body: SignUpRequest, request: Request, response: Response,
            accounts: BaseAccounts = Depends(get_accounts), registry: BaseRegistry = Depends(get_registry)) -> dict:
    _limit_auth(request)
    if not get_api_settings().allow_signup:
        raise HTTPException(403, "New accounts cannot be created on this server.")
    if body.website or not check_form_challenge(body.challenge):  # bot: honeypot filled, or no/too-fast challenge
        raise HTTPException(400, "The form expired or was sent too quickly. Please try again.")
    try:
        email = normalize_email(body.email)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    name = clean_name(body.name)
    if not name:
        raise HTTPException(422, "Enter your name.")
    try:
        check_password(body.password, email, name)
    except PasswordRejected as e:
        raise HTTPException(422, str(e)) from None
    user = new_user(email, name, hash_password(body.password), language=body.language, theme=body.theme)
    if not accounts.create_user(user):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    registry.ensure_workspace(user.id)
    start_session(accounts, user, request, response, remember=True)
    log.info("Account created: %s", user.id)  # ids only; emails and passwords are never logged
    return user_out(user)


@router.post("/login", response_model=UserOut)
def sign_in(body: SignInRequest, request: Request, response: Response,
            accounts: BaseAccounts = Depends(get_accounts), registry: BaseRegistry = Depends(get_registry)) -> dict:
    _limit_auth(request)
    try:
        email = normalize_email(body.email)
    except ValueError:
        email = None
    user = accounts.get_user_by_email(email) if email else None
    # Always run one password hash, so timing does not reveal whether the email is registered.
    ok = verify_password(user.password_hash if user else None, body.password)
    if user is None:
        raise HTTPException(401, BAD_CREDENTIALS)
    if throttle.locked(user):
        raise HTTPException(401, BAD_CREDENTIALS)
    if not ok:
        throttle.failed(user)
        accounts.save_user(user)
        raise HTTPException(401, BAD_CREDENTIALS)
    throttle.succeeded(user)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    accounts.save_user(user)
    old = current_session_id(request)
    if old:
        accounts.delete_session(old)  # no session fixation: a sign-in always gets a new session
    registry.ensure_workspace(user.id)
    start_session(accounts, user, request, response, remember=body.remember)
    accounts.purge_expired(time.time())
    return user_out(user)


@router.post("/logout", status_code=204)
def sign_out(request: Request, response: Response, accounts: BaseAccounts = Depends(get_accounts)) -> None:
    sid = current_session_id(request)
    if sid:
        accounts.delete_session(sid)
    clear_session_cookie(response)
    set_csrf_cookie(response)


@router.get("/session", response_model=SessionState)
def session_state(user: User | None = Depends(get_optional_user)) -> dict:
    """The app's start-up check: 200 for visitors too, so a signed-out page load logs no error."""
    return {"user": user_out(user) if user else None}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> dict:
    return user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user),
              accounts: BaseAccounts = Depends(get_accounts)) -> dict:
    if body.name is not None:
        name = clean_name(body.name)
        if not name:
            raise HTTPException(422, "Enter your name.")
        user.name = name
    if body.language is not None:
        user.language = body.language
    if body.theme is not None:
        user.theme = body.theme
    user.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    accounts.save_user(user)
    return user_out(user)


@router.post("/password", status_code=204)
def change_password(body: PasswordChange, request: Request, user: User = Depends(get_current_user),
                    accounts: BaseAccounts = Depends(get_accounts)) -> None:
    """Change the password; every other session of the account is signed out."""
    _limit_auth(request)
    if not verify_password(user.password_hash, body.current_password):
        raise HTTPException(403, "Your current password is incorrect.")
    if body.new_password == body.current_password:
        raise HTTPException(422, "Choose a password different from your current one.")
    try:
        check_password(body.new_password, user.email, user.name)
    except PasswordRejected as e:
        raise HTTPException(422, str(e)) from None
    user.password_hash = hash_password(body.new_password)
    user.password_changed_at = user.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    accounts.save_user(user)
    accounts.delete_sessions(user.id, keep=current_session_id(request))


@router.get("/sessions", response_model=SessionList)
def list_sessions(request: Request, user: User = Depends(get_current_user),
                  accounts: BaseAccounts = Depends(get_accounts)) -> dict:
    now, current = time.time(), current_session_id(request)
    return {"sessions": [s.public(current) for s in accounts.list_sessions(user.id) if s.expires_at > now]}


@router.delete("/sessions", status_code=204)
def sign_out_other_sessions(request: Request, user: User = Depends(get_current_user),
                            accounts: BaseAccounts = Depends(get_accounts)) -> None:
    accounts.delete_sessions(user.id, keep=current_session_id(request))


@router.delete("/me", status_code=204)
def delete_account(body: AccountDelete, request: Request, response: Response, user: User = Depends(get_current_user),
                   accounts: BaseAccounts = Depends(get_accounts), registry: BaseRegistry = Depends(get_registry),
                   manager: InvestigationManager = Depends(get_manager)) -> None:
    """Permanently delete the account with every project, paper, graph, file and investigation it owns."""
    _limit_auth(request)
    if not verify_password(user.password_hash, body.password):
        raise HTTPException(403, "Your password is incorrect.")
    projects = registry.list_projects(user.id)
    if any(manager.running(p.id) for p in projects):
        raise HTTPException(409, "An investigation is still running. Wait for it to finish, then delete your account.")
    registry.purge_owner(user.id)
    for p in projects:
        forget_project(p.id)
        manager.forget_project(p.id)
    accounts.delete_user(user.id)
    clear_session_cookie(response)
    set_csrf_cookie(response)
    log.info("Account deleted: %s (%d projects)", user.id, len(projects))
