"""Public site endpoints (form challenge, contact, consented usage statistics) and the admin view of them."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from researchmind.accounts import User
from researchmind.site import EVENTS, TOPICS, BaseSiteStore, new_message, summarize, today

from ..auth import get_optional_user, get_site, require_admin
from ..ratelimit import client_ip, get_limiters
from ..security import check_form_challenge, clean_name, issue_form_challenge, normalize_email

log = logging.getLogger("researchmind.api.site")
router = APIRouter(tags=["site"])

PATH = r"^/[A-Za-z0-9/_\-.:]{0,199}$"
UTM = r"^[A-Za-z0-9_\-. ]{0,80}$"
IDS = re.compile(r"/(p_[0-9a-f]{12}|inv_[0-9a-f]{12}|prj_[0-9a-f]{10})")


class ContactRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=80)
    email: str = Field(..., min_length=3, max_length=254)
    topic: Literal[TOPICS] = "question"  # type: ignore[valid-type]
    message: str = Field(..., min_length=10, max_length=3000)
    challenge: str = Field("", max_length=120)
    website: str = Field("", max_length=200)  # honeypot


class AnalyticsEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal[EVENTS]  # type: ignore[valid-type]
    path: str = Field("/", pattern=PATH)
    utm_source: str = Field("", pattern=UTM)
    utm_medium: str = Field("", pattern=UTM)
    utm_campaign: str = Field("", pattern=UTM)


@router.get("/forms/challenge")
def form_challenge() -> dict:
    """A signed, timestamped token that public forms send back (spam protection without third-party CAPTCHAs)."""
    return {"challenge": issue_form_challenge()}


@router.post("/contact", status_code=202)
def contact(body: ContactRequest, request: Request, user: User | None = Depends(get_optional_user),
            site: BaseSiteStore = Depends(get_site)) -> dict:
    get_limiters().contact.hit(client_ip(request))
    if body.website:
        return {"status": "received"}  # honeypot filled: answer like a success, store nothing
    if not check_form_challenge(body.challenge):
        raise HTTPException(400, "The form expired or was sent too quickly. Please try again.")
    try:
        email = normalize_email(body.email)
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    name, message = clean_name(body.name), body.message.strip()
    if not name or len(message) < 10:
        raise HTTPException(422, "Please enter your name and a message of at least 10 characters.")
    site.add_message(new_message(name, email, body.topic, message, user.id if user else None))
    log.info("Contact message received (%s)", body.topic)
    return {"status": "received"}


@router.post("/analytics/event", status_code=204)
def record_event(body: AnalyticsEvent, site: BaseSiteStore = Depends(get_site)) -> None:
    """Count one consented event. No IP, user id, cookie or fingerprint is stored: only daily aggregates."""
    path = IDS.sub(lambda m: "/:" + m.group(1).split("_")[0], body.path)
    site.increment(today(), body.name, path, body.utm_source.strip().lower(), body.utm_medium.strip().lower(),
                   body.utm_campaign.strip().lower())


@router.get("/admin/analytics")
def admin_analytics(days: Annotated[int, Query(ge=1, le=90)] = 30, _: User = Depends(require_admin),
                    site: BaseSiteStore = Depends(get_site)) -> dict:
    since = (datetime.now(timezone.utc).date() - timedelta(days=days - 1)).isoformat()
    return summarize(site.metrics_since(since), days)


@router.get("/admin/messages")
def admin_messages(limit: Annotated[int, Query(ge=1, le=500)] = 100, _: User = Depends(require_admin),
                   site: BaseSiteStore = Depends(get_site)) -> dict:
    return {"messages": [m.__dict__ for m in site.list_messages(limit)]}
