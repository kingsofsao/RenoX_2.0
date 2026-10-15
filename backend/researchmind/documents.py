"""Page-level document store on disk.

Full page text is kept out of the graph: FalkorDB holds the paper's metadata, the
evidence chunks used for retrieval, and a `document_key` pointing here. Each page is
its own file, so the API can serve one page range without loading the whole document.

    <data_dir>/documents/<paper_id>/meta.json
    <data_dir>/documents/<paper_id>/pages/0001.txt ...
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path

from .config import get_settings

_SAFE_ID = re.compile(r"^p_[0-9a-f]{12}$")


class DocumentStore:
    def __init__(self, root: Path | None = None):
        self.root = root or (get_settings().data_dir / "documents")

    def _dir(self, paper_id: str) -> Path:
        if not _SAFE_ID.match(paper_id):  # ids come from URLs: never let them escape the store
            raise ValueError("invalid paper id")
        return self.root / paper_id

    def save(self, paper_id: str, pages: list[str], meta: dict) -> str:
        """Write pages + metadata atomically (temp dir, then swap). Returns the document key."""
        target = self._dir(paper_id)
        tmp = self.root / f".tmp-{paper_id}-{uuid.uuid4().hex[:8]}"
        (tmp / "pages").mkdir(parents=True)
        for i, text in enumerate(pages, start=1):
            (tmp / "pages" / f"{i:04d}.txt").write_text(text, encoding="utf-8")
        (tmp / "meta.json").write_text(json.dumps({**meta, "page_count": len(pages)}, indent=2), encoding="utf-8")
        if target.exists():
            shutil.rmtree(target)
        tmp.rename(target)
        return paper_id

    def exists(self, paper_id: str) -> bool:
        try:
            return (self._dir(paper_id) / "meta.json").exists()
        except ValueError:
            return False

    def meta(self, paper_id: str) -> dict | None:
        path = self._dir(paper_id) / "meta.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def pages(self, paper_id: str, start: int = 1, count: int = 5) -> list[dict]:
        """Return pages [start, start+count) as {"page": n, "text": ..., "chars": ...}."""
        meta = self.meta(paper_id)
        if not meta:
            return []
        end = min(meta["page_count"], start + count - 1)
        out = []
        for n in range(max(1, start), end + 1):
            path = self._dir(paper_id) / "pages" / f"{n:04d}.txt"
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            out.append({"page": n, "text": text, "chars": len(text)})
        return out

    def delete(self, paper_id: str) -> None:
        target = self._dir(paper_id)
        if target.exists():
            shutil.rmtree(target)
