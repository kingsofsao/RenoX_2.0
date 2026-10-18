"""Schemas for /api/auth. Passwords are length-bounded here and checked against the policy in security.py."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from researchmind.accounts import LANGUAGES

Language = Literal[tuple(LANGUAGES)]  # type: ignore[valid-type]
Theme = Literal["system", "light", "dark"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SignUpRequest(_Strict):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)
    name: str = Field(..., min_length=1, max_length=80)
    language: Language = "en"
    theme: Theme = "system"
    challenge: str = Field("", max_length=120, description="Signed form challenge from GET /api/forms/challenge")
    website: str = Field("", max_length=200, description="Honeypot: must stay empty (hidden from people)")


class SignInRequest(_Strict):
    email: str = Field(..., min_length=1, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)
    remember: bool = True


class ProfileUpdate(_Strict):
    name: str | None = Field(None, min_length=1, max_length=80)
    language: Language | None = None
    theme: Theme | None = None


class PasswordChange(_Strict):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


class AccountDelete(_Strict):
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    theme: Theme
    language: Language
    created_at: str
    is_admin: bool = False


class SessionState(BaseModel):
    """Who is signed in on this browser: the user, or null for a visitor."""
    user: UserOut | None = None


class SessionOut(BaseModel):
    id: str
    created_at: str
    last_seen_at: str
    expires_at: str
    user_agent: str
    current: bool


class SessionList(BaseModel):
    sessions: list[SessionOut]
