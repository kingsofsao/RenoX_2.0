"""Security middleware for every request.

0. Front proxy: with ORIGIN_SECRET set (the API sits behind Vercel), any request without the matching
   `x-origin-secret` header bypassed the proxy and is answered 404 (the liveness probe excepted).
1. Rate limit: requests per client IP per minute across /api (429 with Retry-After).
2. CSRF: state-changing requests (POST/PUT/PATCH/DELETE) must
   - not come from another site (Sec-Fetch-Site / Origin checked against ALLOWED_ORIGINS), and
   - carry the double-submit token: header X-CSRF-Token equal to the CSRF cookie.
3. Security headers on every response: no sniffing, no framing, strict referrer and permissions
   policies, a deny-all Content-Security-Policy for API responses, HSTS over HTTPS, and
   `Cache-Control: no-store` so private research data is never cached by browsers or proxies.
4. A CSRF cookie is issued on any response to a client that does not have one yet.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .auth import csrf_cookie_name, set_csrf_cookie
from .config import get_api_settings
from .ratelimit import RateLimited, client_ip, get_limiters
from .security import same

log = logging.getLogger("researchmind.api.security")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
MAX_JSON_BODY = 256 * 1024  # every non-upload request body is small JSON
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# The original PDF is shown by the browser's own viewer, which a deny-all policy would break.
PDF_CSP = "default-src 'none'; object-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
LIVE_PATH = "/api/health/live"  # the platform's health check calls the API directly, not via the proxy


def _error(status: int, code: str, message: str, headers: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}}, headers=headers)


def _origin_allowed(request: Request) -> bool:
    site = request.headers.get("sec-fetch-site")
    if site and site not in ("same-origin", "same-site", "none"):
        return False
    if site == "same-origin":
        # Set by the browser and not forgeable by page scripts: the request comes from this site's own pages,
        # whatever address a proxy in front of the API puts in Host. (The CSRF token is still required.)
        return True
    origin = request.headers.get("origin")
    if not origin or origin == "null":
        return origin is None  # non-browser clients send no Origin; "null" (sandboxed/opaque) is refused
    settings = get_api_settings()
    origin = origin.rstrip("/").lower()
    if origin in settings.allowed_origins:
        return True
    hosts = {request.headers.get("host", "").lower()}
    if settings.origin_secret:
        # Behind Vercel (the secret was checked already) Host is the API's own address; the address the
        # visitor used is in x-forwarded-host, which Vercel sets itself.
        hosts.add(request.headers.get("x-forwarded-host", "").lower())
    if urlsplit(origin).netloc in hosts - {""}:
        return True
    log.warning("Refused cross-site request from origin %s (ALLOWED_ORIGINS: %s)", origin, settings.allowed_origins)
    return False


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_api_settings()
        path = request.url.path
        is_api = path.startswith("/api/")

        if settings.origin_secret and path != LIVE_PATH and not same(request.headers.get("x-origin-secret"),
                                                                     settings.origin_secret):
            return self._secure(_error(404, "not_found", "Not found."), path, settings)

        if is_api and path != LIVE_PATH:
            try:
                get_limiters().api.hit(client_ip(request))
            except RateLimited as e:
                return self._secure(_error(429, "rate_limited", str(e), {"Retry-After": str(e.retry_after)}), path, settings)

        if is_api and request.method not in SAFE_METHODS:
            too_big = self._body_too_large(request, path, settings)
            if too_big:
                return self._secure(too_big, path, settings)
            if not _origin_allowed(request):
                return self._secure(_error(403, "cross_site_request", "Cross-site requests are not allowed."), path, settings)
            cookie = request.cookies.get(csrf_cookie_name())
            if not same(request.headers.get("x-csrf-token"), cookie):
                resp = _error(403, "csrf_failed", "Your session security token is missing or expired. Reload the page and try again.")
                if not cookie:
                    set_csrf_cookie(resp)
                return self._secure(resp, path, settings)

        response = await call_next(request)
        if is_api and not request.cookies.get(csrf_cookie_name()) and not _sets_cookie(response, csrf_cookie_name()):
            set_csrf_cookie(response)
        return self._secure(response, path, settings)

    @staticmethod
    def _body_too_large(request: Request, path: str, settings) -> JSONResponse | None:
        """Refuse oversized bodies from the Content-Length header, before anything is read."""
        length = request.headers.get("content-length")
        if length is None:
            if "chunked" in request.headers.get("transfer-encoding", "").lower():
                return _error(411, "length_required", "Requests must declare their size (Content-Length).")
            return None
        try:
            size = int(length)
        except ValueError:
            return _error(400, "bad_request", "Invalid Content-Length header.")
        upload = path.endswith("/papers/upload")
        limit = settings.max_upload_bytes * settings.max_files_per_upload + 1024 * 1024 if upload else MAX_JSON_BODY
        if size > limit:
            msg = (f"The upload is too large: at most {settings.max_files_per_upload} files of {settings.max_upload_mb} MB each."
                   if upload else "The request is too large.")
            return _error(413, "too_large", msg)
        return None

    @staticmethod
    def _secure(response: Response, path: str, settings) -> Response:
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "SAMEORIGIN" if path.endswith("/file") else "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()")
        h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        h.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        if not path.startswith(DOCS_PATHS):
            h.setdefault("Content-Security-Policy", PDF_CSP if path.endswith("/file") else API_CSP)
        if path.startswith("/api/"):
            h["Cache-Control"] = "no-store, private"
            h.setdefault("Pragma", "no-cache")
        if settings.cookie_secure:
            h.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response


def _sets_cookie(response: Response, name: str) -> bool:
    return any(k.lower() == b"set-cookie" and v.decode("latin-1").startswith(name + "=") for k, v in response.raw_headers)
