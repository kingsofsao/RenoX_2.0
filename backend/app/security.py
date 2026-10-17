"""Password hashing, password policy, session tokens and input normalization.

- Passwords: Argon2id (argon2-cffi, OWASP-recommended parameters), with transparent re-hashing
  when the parameters change. Plain passwords are never logged or stored.
- Session tokens: 256-bit random values from `secrets`; only their SHA-256 is stored.
- Password policy (NIST SP 800-63B style): 12-128 characters, not a common password and not
  derived from the account's email or name. No arbitrary composition rules.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD = 12
MAX_PASSWORD = 128
MAX_EMAIL = 254

_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2, hash_len=32, salt_len=16)
# Verified against when the account does not exist, so response time does not reveal which emails are registered.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(24))

EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
                   r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")

COMMON_PASSWORDS = frozenset("""
123456789012 1234567890123 password1234 password12345 passwordpassword qwertyuiop12 qwertyuiopas
1q2w3e4r5t6y 1qaz2wsx3edc iloveyou1234 letmein12345 welcome12345 administrator changeme1234
abc123456789 aaaaaaaaaaaa 111111111111 000000000000 123123123123 qwerty123456 football1234
baseball1234 monkey123456 dragon123456 sunshine1234 princess1234 trustno11234 superman1234
starwars1234 whatever1234 passw0rd1234 p@ssw0rd1234 p@ssword1234 correcthorsebatterystaple
researchmind researchmind1 researchmind123 qwertyqwerty asdfghjklzxc zxcvbnm12345
""".split())


class PasswordRejected(ValueError):
    """The password does not meet the policy. The message is safe to show to the user."""


def normalize_email(email: str) -> str:
    """Trimmed email; raises ValueError if it is not a plausible address."""
    email = unicodedata.normalize("NFKC", (email or "").strip())
    if len(email) > MAX_EMAIL or not EMAIL.match(email):
        raise ValueError("Enter a valid email address.")
    local, _, domain = email.rpartition("@")
    return f"{local}@{domain.lower()}"


def clean_name(name: str, max_len: int = 80) -> str:
    """Display name with control characters removed and whitespace collapsed."""
    name = unicodedata.normalize("NFKC", name or "")
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    return " ".join(name.split())[:max_len]


def check_password(password: str, email: str = "", name: str = "") -> None:
    """Raise PasswordRejected unless the password meets the policy."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise PasswordRejected(f"Use at least {MIN_PASSWORD} characters.")
    if len(password) > MAX_PASSWORD:
        raise PasswordRejected(f"Use at most {MAX_PASSWORD} characters.")
    low = password.lower()
    if low in COMMON_PASSWORDS or len(set(low)) < 4:
        raise PasswordRejected("This password is too common or too simple. Choose something harder to guess.")
    local = (email or "").split("@")[0].lower()
    parts = [p for p in [local, *(name or "").lower().split()] if len(p) >= 4]
    if any(p in low for p in parts):
        raise PasswordRejected("Do not use your email address or name in the password.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Constant-work check: hashes against a dummy value when there is no stored hash."""
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return True


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def same(a: str | None, b: str | None) -> bool:
    """Timing-safe string comparison."""
    return bool(a) and bool(b) and hmac.compare_digest(a.encode(), b.encode())
