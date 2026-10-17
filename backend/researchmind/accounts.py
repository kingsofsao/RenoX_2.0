"""User accounts and sign-in sessions.

Stored in the registry graph (`<FALKORDB_GRAPH>_registry`) next to projects:
  (:User {id, email, email_lower, name, password_hash, theme, language, created_at, updated_at,
          password_changed_at, failed_logins, locked_until})
  (:Session {id, user_id, created_at, expires_at, last_seen_at, user_agent})

Sessions are opaque random tokens held in an httpOnly cookie. Only the SHA-256 of a token is
stored (`Session.id`), so a database dump does not contain usable sessions. Passwords are stored
as Argon2id hashes (see app/security.py); this module never sees a plain password.

Every project, paper graph and investigation is owned by a User id (Project.owner_id), and
`projects.authorize` checks it on every request.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone

USER_ID = re.compile(r"^usr_[0-9a-f]{16}$")
THEMES = ("system", "light", "dark")
# UI and report languages. Keep in sync with frontend/src/i18n/languages.ts.
LANGUAGES = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "hi": "Hindi", "ta": "Tamil",
             "zh": "Simplified Chinese", "ja": "Japanese", "ar": "Arabic"}
# Native names, so the model is told the language in that language too ("German (Deutsch)").
NATIVE_NAMES = {"en": "English", "es": "Español", "fr": "Français", "de": "Deutsch", "hi": "हिन्दी", "ta": "தமிழ்",
                "zh": "简体中文", "ja": "日本語", "ar": "العربية"}
MAX_NAME = 80


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class User:
    id: str
    email: str
    email_lower: str
    name: str
    password_hash: str
    created_at: str
    updated_at: str
    password_changed_at: str
    theme: str = "system"
    language: str = "en"
    failed_logins: int = 0
    locked_until: float = 0.0  # epoch seconds; sign-in refused until then

    def public(self) -> dict:
        """API view: never includes the password hash or lockout counters."""
        return {"id": self.id, "email": self.email, "name": self.name, "theme": self.theme,
                "language": self.language, "created_at": self.created_at}


@dataclass
class Session:
    id: str            # sha256(token) hex
    user_id: str
    created_at: float
    expires_at: float
    last_seen_at: float
    user_agent: str = ""

    def public(self, current_id: str | None = None) -> dict:
        def iso(t: float) -> str:
            return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")
        return {"id": self.id[:12], "created_at": iso(self.created_at), "last_seen_at": iso(self.last_seen_at),
                "expires_at": iso(self.expires_at), "user_agent": self.user_agent, "current": self.id == current_id}


def _from_props(cls, props: dict):
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in props.items() if k in names})


def new_user(email: str, name: str, password_hash: str, language: str = "en", theme: str = "system") -> User:
    now = _iso()
    return User(id="usr_" + uuid.uuid4().hex[:16], email=email, email_lower=email.lower(), name=name,
                password_hash=password_hash, created_at=now, updated_at=now, password_changed_at=now,
                language=language if language in LANGUAGES else "en", theme=theme if theme in THEMES else "system")


class BaseAccounts:
    """Storage interface for users and sessions."""

    def create_user(self, user: User) -> bool: ...        # False if the email is taken
    def get_user(self, user_id: str) -> User | None: ...
    def get_user_by_email(self, email: str) -> User | None: ...
    def save_user(self, user: User) -> None: ...
    def delete_user(self, user_id: str) -> None: ...      # also removes the user's sessions
    def create_session(self, s: Session) -> None: ...
    def get_session(self, session_id: str) -> Session | None: ...
    def touch_session(self, session_id: str, now: float) -> None: ...
    def delete_session(self, session_id: str) -> None: ...
    def delete_sessions(self, user_id: str, keep: str | None = None) -> int: ...
    def list_sessions(self, user_id: str) -> list[Session]: ...
    def purge_expired(self, now: float) -> int: ...


class MemoryAccounts(BaseAccounts):
    """In-process store for tests."""

    def __init__(self):
        self.users: dict[str, User] = {}
        self.sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create_user(self, user):
        with self._lock:
            if any(u.email_lower == user.email_lower for u in self.users.values()):
                return False
            self.users[user.id] = User(**asdict(user))
            return True

    def get_user(self, user_id):
        u = self.users.get(user_id)
        return User(**asdict(u)) if u else None

    def get_user_by_email(self, email):
        u = next((u for u in self.users.values() if u.email_lower == email.lower()), None)
        return User(**asdict(u)) if u else None

    def save_user(self, user):
        self.users[user.id] = User(**asdict(user))

    def delete_user(self, user_id):
        self.users.pop(user_id, None)
        self.delete_sessions(user_id)

    def create_session(self, s):
        self.sessions[s.id] = Session(**asdict(s))

    def get_session(self, session_id):
        s = self.sessions.get(session_id)
        return Session(**asdict(s)) if s else None

    def touch_session(self, session_id, now):
        if session_id in self.sessions:
            self.sessions[session_id].last_seen_at = now

    def delete_session(self, session_id):
        self.sessions.pop(session_id, None)

    def delete_sessions(self, user_id, keep=None):
        ids = [k for k, s in self.sessions.items() if s.user_id == user_id and k != keep]
        for k in ids:
            del self.sessions[k]
        return len(ids)

    def list_sessions(self, user_id):
        return sorted((Session(**asdict(s)) for s in self.sessions.values() if s.user_id == user_id),
                      key=lambda s: -s.last_seen_at)

    def purge_expired(self, now):
        ids = [k for k, s in self.sessions.items() if s.expires_at <= now]
        for k in ids:
            del self.sessions[k]
        return len(ids)


class FalkorAccounts(BaseAccounts):
    """Users and sessions in the registry graph. All queries are parameterized."""

    def __init__(self, db, graph_name: str):
        self.graph = db.select_graph(graph_name)
        for label, prop in (("User", "id"), ("User", "email_lower"), ("Session", "id"), ("Session", "user_id")):
            try:
                self.graph.create_node_range_index(label, prop)
            except Exception as e:  # already indexed
                if "already indexed" not in str(e).lower():
                    raise

    def _q(self, cypher: str, params: dict | None = None, read_only: bool = False) -> list[dict]:
        fn = self.graph.ro_query if read_only else self.graph.query
        r = fn(cypher, params or {})
        cols = [h[1] if isinstance(h, (list, tuple)) else h for h in (r.header or [])]
        cols = [c.decode() if isinstance(c, bytes) else c for c in cols]
        return [dict(zip(cols, row)) for row in r.result_set]

    def create_user(self, user):
        # MERGE on the normalized email is atomic in FalkorDB (writes to a graph are serialized),
        # so two concurrent sign-ups with the same email cannot both succeed.
        rows = self._q("MERGE (u:User {email_lower: $email}) ON CREATE SET u += $props RETURN u.id AS id",
                       {"email": user.email_lower, "props": asdict(user)})
        return bool(rows) and rows[0]["id"] == user.id

    def _user(self, cypher: str, params: dict) -> User | None:
        rows = self._q(cypher, params, read_only=True)
        return _from_props(User, rows[0]["u"].properties) if rows else None

    def get_user(self, user_id):
        return self._user("MATCH (u:User {id: $id}) RETURN u", {"id": user_id})

    def get_user_by_email(self, email):
        return self._user("MATCH (u:User {email_lower: $e}) RETURN u", {"e": email.lower()})

    def save_user(self, user):
        props = {k: v for k, v in asdict(user).items() if k not in ("id", "email_lower")}
        self._q("MATCH (u:User {id: $id}) SET u += $props", {"id": user.id, "props": props})

    def delete_user(self, user_id):
        self._q("MATCH (s:Session {user_id: $id}) DELETE s", {"id": user_id})
        self._q("MATCH (u:User {id: $id}) DELETE u", {"id": user_id})

    def create_session(self, s):
        self._q("CREATE (x:Session) SET x += $props", {"props": asdict(s)})

    def get_session(self, session_id):
        rows = self._q("MATCH (x:Session {id: $id}) RETURN x", {"id": session_id}, read_only=True)
        return _from_props(Session, rows[0]["x"].properties) if rows else None

    def touch_session(self, session_id, now):
        self._q("MATCH (x:Session {id: $id}) SET x.last_seen_at = $now", {"id": session_id, "now": now})

    def delete_session(self, session_id):
        self._q("MATCH (x:Session {id: $id}) DELETE x", {"id": session_id})

    def delete_sessions(self, user_id, keep=None):
        rows = self._q("MATCH (x:Session {user_id: $uid}) WHERE $keep IS NULL OR x.id <> $keep "
                       "WITH x, x.id AS sid DELETE x RETURN count(sid) AS n", {"uid": user_id, "keep": keep})
        return rows[0]["n"] if rows else 0

    def list_sessions(self, user_id):
        rows = self._q("MATCH (x:Session {user_id: $uid}) RETURN x ORDER BY x.last_seen_at DESC", {"uid": user_id},
                       read_only=True)
        return [_from_props(Session, r["x"].properties) for r in rows]

    def purge_expired(self, now):
        rows = self._q("MATCH (x:Session) WHERE x.expires_at <= $now WITH x, x.id AS sid DELETE x RETURN count(sid) AS n",
                       {"now": now})
        return rows[0]["n"] if rows else 0


@dataclass
class LoginThrottle:
    """Per-account lockout policy: after `max_failures` wrong passwords, refuse sign-in for `lock_seconds`."""
    max_failures: int = 8
    lock_seconds: int = 15 * 60
    clock: callable = field(default=time.time)

    def locked(self, user: User) -> bool:
        return (user.locked_until or 0) > self.clock()

    def failed(self, user: User) -> None:
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= self.max_failures:
            user.locked_until = self.clock() + self.lock_seconds
            user.failed_logins = 0

    def succeeded(self, user: User) -> None:
        user.failed_logins, user.locked_until = 0, 0.0
