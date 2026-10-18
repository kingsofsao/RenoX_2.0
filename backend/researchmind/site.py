"""Site data: contact messages and privacy-first usage statistics.

Stored in the registry graph next to users and projects:
  (:ContactMessage {id, created_at, name, email, topic, message, user_id})
  (:Metric {key, day, name, path, utm_source, utm_medium, utm_campaign, count})

Statistics are aggregate counters only: one node per day + event + page path + campaign. They hold no
IP address, no user id, no cookie and no device fingerprint, so a counter can never be traced back to
a person. The web app records events only after the visitor allows it in the cookie banner.
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

EVENTS = ("page_view", "signup", "upload", "investigation")
TOPICS = ("question", "feedback", "bug", "privacy")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


@dataclass
class ContactMessage:
    id: str
    created_at: str
    name: str
    email: str
    topic: str
    message: str
    user_id: str = ""


def new_message(name: str, email: str, topic: str, message: str, user_id: str | None) -> ContactMessage:
    return ContactMessage(id="msg_" + uuid.uuid4().hex[:16], created_at=_now(), name=name, email=email, topic=topic,
                          message=message, user_id=user_id or "")


def metric_key(day: str, name: str, path: str, source: str, medium: str, campaign: str) -> str:
    return hashlib.sha256("\x1f".join((day, name, path, source, medium, campaign)).encode()).hexdigest()[:32]


def summarize(rows: list[dict], days: int) -> dict:
    """Aggregate metric rows into what the admin page shows."""
    by_day: dict[str, dict[str, int]] = defaultdict(lambda: {e: 0 for e in EVENTS})
    paths: dict[str, int] = defaultdict(int)
    sources: dict[str, dict[str, int]] = defaultdict(lambda: {e: 0 for e in EVENTS})
    totals = {e: 0 for e in EVENTS}
    for r in rows:
        n, name = int(r.get("count") or 0), r.get("name")
        if name not in totals:
            continue
        by_day[r["day"]][name] += n
        totals[name] += n
        if name == "page_view":
            paths[r.get("path") or "/"] += n
        src = r.get("utm_source") or ""
        if src:
            label = " / ".join(x for x in (src, r.get("utm_medium") or "", r.get("utm_campaign") or "") if x)
            sources[label][name] += n
    start = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    series = [{"day": (start + timedelta(days=i)).isoformat(), **by_day.get((start + timedelta(days=i)).isoformat(),
                                                                            {e: 0 for e in EVENTS})}
              for i in range(days)]
    return {
        "days": days,
        "totals": totals,
        "series": series,
        "top_paths": [{"path": p, "views": v} for p, v in sorted(paths.items(), key=lambda kv: -kv[1])[:10]],
        "campaigns": [{"campaign": c, **v} for c, v in sorted(sources.items(), key=lambda kv: -sum(kv[1].values()))[:10]],
    }


class BaseSiteStore:
    def add_message(self, m: ContactMessage) -> None: ...
    def list_messages(self, limit: int = 100) -> list[ContactMessage]: ...
    def increment(self, day: str, name: str, path: str, source: str, medium: str, campaign: str) -> None: ...
    def metrics_since(self, day: str) -> list[dict]: ...


class MemorySiteStore(BaseSiteStore):
    def __init__(self):
        self.messages: list[ContactMessage] = []
        self.metrics: dict[str, dict] = {}
        self._lock = threading.Lock()

    def add_message(self, m):
        self.messages.append(ContactMessage(**asdict(m)))

    def list_messages(self, limit=100):
        return sorted(self.messages, key=lambda m: m.created_at, reverse=True)[:limit]

    def increment(self, day, name, path, source, medium, campaign):
        key = metric_key(day, name, path, source, medium, campaign)
        with self._lock:
            row = self.metrics.setdefault(key, {"day": day, "name": name, "path": path, "utm_source": source,
                                                "utm_medium": medium, "utm_campaign": campaign, "count": 0})
            row["count"] += 1

    def metrics_since(self, day):
        return [dict(r) for r in self.metrics.values() if r["day"] >= day]


class FalkorSiteStore(BaseSiteStore):
    """Contact messages and counters in the registry graph. All queries are parameterized."""

    def __init__(self, db, graph_name: str):
        self.graph = db.select_graph(graph_name)
        for label, prop in (("ContactMessage", "created_at"), ("Metric", "key"), ("Metric", "day")):
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

    def add_message(self, m):
        self._q("CREATE (x:ContactMessage) SET x += $props", {"props": asdict(m)})

    def list_messages(self, limit=100):
        rows = self._q("MATCH (x:ContactMessage) RETURN x ORDER BY x.created_at DESC LIMIT $limit", {"limit": limit},
                       read_only=True)
        return [ContactMessage(**{k: r["x"].properties.get(k, "") for k in ContactMessage.__dataclass_fields__}) for r in rows]

    def increment(self, day, name, path, source, medium, campaign):
        self._q("""MERGE (m:Metric {key: $key})
                   ON CREATE SET m.day = $day, m.name = $name, m.path = $path, m.utm_source = $source,
                                 m.utm_medium = $medium, m.utm_campaign = $campaign, m.count = 0
                   SET m.count = m.count + 1""",
                {"key": metric_key(day, name, path, source, medium, campaign), "day": day, "name": name, "path": path,
                 "source": source, "medium": medium, "campaign": campaign})

    def metrics_since(self, day):
        return self._q("""MATCH (m:Metric) WHERE m.day >= $day
                          RETURN m.day AS day, m.name AS name, m.path AS path, m.utm_source AS utm_source,
                                 m.utm_medium AS utm_medium, m.utm_campaign AS utm_campaign, m.count AS count""",
                       {"day": day}, read_only=True)
