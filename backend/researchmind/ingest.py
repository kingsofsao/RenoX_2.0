"""PDF parsing with pdfplumber: text, metadata, sections and page-anchored chunks.

Everything here is deterministic: the same PDF bytes always produce the same
paper id, chunk ids and chunk text, which is what makes graph ingestion idempotent.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pdfplumber

CHUNK_TARGET_CHARS = 900

KNOWN_SECTIONS = {
    "abstract", "introduction", "background", "related work", "method", "methods",
    "methodology", "approach", "model", "experiments", "experimental setup", "evaluation",
    "results", "discussion", "analysis", "limitations", "limitations and future work",
    "future work", "conclusion", "conclusions", "acknowledgements", "acknowledgments",
    "references", "bibliography", "appendix", "data", "datasets",
}
STOP_SECTIONS = {"references", "bibliography", "acknowledgements", "acknowledgments"}

NUMBERED_HEADING = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*)\.?\s+([A-Z][A-Za-z0-9 ,:&/\-]{2,70})$")
YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
ARXIV_ID = re.compile(r"arXiv:\s?(\d{2})(\d{2})\.\d{4,5}")
VENUE_YEAR = re.compile(
    r"(?:Conference|Proceedings|Workshop|Symposium|Journal|NeurIPS|NIPS|ICML|ICLR|ACL|EMNLP|NAACL|CVPR|ICCV|ECCV|"
    r"AAAI|IJCAI|KDD|Preprint)[^\n]{0,60}?\b(19[5-9]\d|20[0-4]\d)\b")
X_TOLERANCE = 1.5  # pdfplumber's default (3) glues words together in many LaTeX PDFs
NAME_PARTICLES = {"de", "van", "von", "der", "da", "del", "la", "and"}
BAD_TITLES = {"untitled", "microsoft word", "title", "paper", "arxiv"}


class IngestionError(Exception):
    """Raised when a PDF cannot be parsed into usable text.

    `code` is machine-readable: not_found | not_pdf | encrypted | corrupt | empty | no_text
    """

    def __init__(self, message: str, code: str = "corrupt"):
        super().__init__(message)
        self.code = code


@dataclass
class Chunk:
    id: str
    paper_id: str
    page: int
    section: str
    text: str


@dataclass
class ParsedPaper:
    id: str
    sha256: str
    title: str              # detected title, or the file name stem when none was found
    authors: list[str]      # empty when unknown - never guessed
    year: int | None
    abstract: str
    source_file: str
    num_pages: int
    chunks: list[Chunk] = field(default_factory=list)
    title_detected: bool = True
    pages: list[str] = field(default_factory=list)      # cleaned text per page (index 0 = page 1)
    pdf_metadata: dict = field(default_factory=dict)    # basic document-info entries (Producer, dates, ...)

    def to_dict(self) -> dict:
        return asdict(self)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 16), b""):
            h.update(block)
    return h.hexdigest()


def _clean(text: str) -> str:
    text = text.replace("­", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join hyphenated line breaks
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    return text


def _page_text(page) -> str:
    """Extract page text, reading two-column layouts left column first."""
    words = page.extract_words(x_tolerance=X_TOLERANCE)
    mid = page.width / 2
    left = sum(1 for w in words if w["x1"] <= mid)
    right = sum(1 for w in words if w["x0"] >= mid)
    crossing = [w for w in words if w["x0"] < mid - 3 and w["x1"] > mid + 3]
    two_column = len(words) > 80 and len(crossing) < 0.02 * len(words) and min(left, right) > 0.25 * len(words)
    if not two_column:
        return page.extract_text(x_tolerance=X_TOLERANCE) or ""
    # A full-width header (title/authors) sits above the columns on the first page.
    header_bottom = max((w["bottom"] for w in crossing if w["bottom"] < page.height * 0.4), default=0)
    parts = []
    if header_bottom:
        parts.append(page.crop((0, 0, page.width, header_bottom)).extract_text(x_tolerance=X_TOLERANCE) or "")
    parts.append(page.crop((0, header_bottom, mid, page.height)).extract_text(x_tolerance=X_TOLERANCE) or "")
    parts.append(page.crop((mid, header_bottom, page.width, page.height)).extract_text(x_tolerance=X_TOLERANCE) or "")
    return "\n".join(parts)


def _heading_name(line: str) -> str | None:
    """Return a normalized section name if the line looks like a section heading."""
    stripped = line.strip().rstrip(":")
    if not stripped or len(stripped) > 80:
        return None
    lowered = re.sub(r"^\d{1,2}(\.\d{1,2})*\.?\s+", "", stripped).lower()
    if lowered in KNOWN_SECTIONS:
        return lowered.title()
    m = NUMBERED_HEADING.match(stripped)
    if m and not stripped.endswith(".") and len(m.group(2).split()) <= 8:
        return m.group(2).strip().title()
    return None


def _extract_title(pdf, first_page_lines: list[str]) -> str | None:
    meta_title = (pdf.metadata or {}).get("Title")
    if isinstance(meta_title, bytes):
        meta_title = meta_title.decode("utf-8", "ignore")
    if meta_title and len(meta_title.strip()) > 8 and meta_title.strip().lower() not in BAD_TITLES:
        return meta_title.strip()

    # Fall back to the largest-font block of text in the top part of page 1
    # (skipping single oversized glyphs such as drop caps or figure labels).
    try:
        page = pdf.pages[0]
        words = [w for w in page.extract_words(extra_attrs=["size"], x_tolerance=X_TOLERANCE) if w["top"] < page.height * 0.45]
    except Exception:
        words = []
    for size in sorted({round(w["size"], 1) for w in words}, reverse=True):
        group = [w for w in words if abs(w["size"] - size) <= 0.3]
        title = " ".join(w["text"] for w in sorted(group, key=lambda w: (round(w["top"] / 3), w["x0"])))
        if len(group) >= 2 and 8 < len(title) < 250:
            return title
    return None  # unknown is better than guessing from arbitrary first-page text


def _extract_authors(pdf, title: str, first_page_lines: list[str]) -> list[str]:
    meta_author = (pdf.metadata or {}).get("Author")
    if isinstance(meta_author, bytes):
        meta_author = meta_author.decode("utf-8", "ignore")
    candidates: list[str] = []
    if meta_author and meta_author.strip():
        candidates = re.split(r",|;| and ", meta_author)
    else:
        # Lines between the title and the abstract usually hold authors and affiliations.
        title_words = set(re.findall(r"\w+", title.lower()))
        start = 0
        for i, line in enumerate(first_page_lines[:25]):
            line_words = set(re.findall(r"\w+", line.lower()))
            if line_words and line_words <= title_words and len(line_words) >= 2:
                start = i + 1  # skip past the (possibly multi-line) title
        for line in first_page_lines[start:start + 12]:
            low = line.lower().strip()
            if not low or low.startswith("abstract"):
                break
            if any(k in low for k in ("university", "institute", "department", "@", "lab", "school", "inc.", "google", "research", "college")):
                continue
            cleaned = re.sub(r"[\*†‡∗§¶\d,]", " ", line)
            tokens = cleaned.split()
            caps = [t for t in tokens if t[:1].isupper() or t.lower() in NAME_PARTICLES]
            if not tokens or len(tokens) > 16 or len(caps) / len(tokens) < 0.9:
                continue  # not a line of names
            for part in re.split(r",| and |\s{2,}|[\*†‡∗]", line):
                words = [w for w in re.sub(r"\d", "", part).split() if w.lower() != "and"]
                if not words:
                    continue
                # Space-separated author lists ("Ashish Vaswani Noam Shazeer") -> pairs of words
                step = 2 if len(words) > 4 else len(words)
                candidates += [" ".join(words[j:j + step]) for j in range(0, len(words), step)]
            if len(candidates) >= 2:
                break
    authors = []
    for name in candidates:
        name = re.sub(r"[\*†‡\d]", "", name).strip()
        if name and 1 <= len(name.split()) <= 4 and name not in authors:
            authors.append(name)
    return authors[:12]


def _extract_year(pdf, first_page_text: str) -> int | None:
    m = ARXIV_ID.search(first_page_text)  # arXiv ids encode YYMM of first submission
    if m:
        return 2000 + int(m.group(1))
    m = VENUE_YEAR.search(first_page_text)
    if m:
        return int(m.group(1))
    m = YEAR.search(first_page_text[:3000])
    if m:
        return int(m.group(1))
    created = str((pdf.metadata or {}).get("CreationDate", ""))
    m = YEAR.search(created)
    return int(m.group(1)) if m else None


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\[])", text)
    return [p.strip() for p in parts if p.strip()]


def parse_pdf(path: str | Path) -> ParsedPaper:
    """Parse a PDF into metadata plus page-anchored, section-labelled chunks."""
    path = Path(path)
    if not path.exists():
        raise IngestionError(f"File not found: {path.name}", "not_found")
    with open(path, "rb") as f:
        if not f.read(1024).lstrip().startswith(b"%PDF-"):
            raise IngestionError(f"{path.name} is not a PDF file.", "not_pdf")

    sha = file_sha256(path)
    paper_id = "p_" + sha[:12]

    try:
        pdf = pdfplumber.open(path)
        num_pages = len(pdf.pages)
    except Exception as e:  # pdfminer raises several unrelated exception types
        raise _classify_open_error(path, e) from e

    with pdf:
        if num_pages == 0:
            raise IngestionError(f"{path.name} has no pages.", "empty")
        page_lines: list[tuple[int, str]] = []
        pages: list[str] = []
        has_images = False
        for page_no, page in enumerate(pdf.pages, start=1):
            try:
                text = _clean(_page_text(page))
                has_images = has_images or bool(page.images)
            except Exception:
                text = ""
            pages.append(text)
            for line in text.splitlines():
                if line.strip():
                    page_lines.append((page_no, line.rstrip()))
            if hasattr(page, "flush_cache"):
                page.flush_cache()  # keep memory flat on long documents

        if sum(len(line) for _, line in page_lines) < 200:
            if has_images:
                raise IngestionError(
                    f"{path.name} appears to be a scanned (image-only) PDF. Reading it needs OCR, "
                    "which is planned as a later enhancement.", "no_text")
            raise IngestionError(f"{path.name} contains no extractable text.", "empty")

        first_page_lines = [line for p, line in page_lines if p == 1]
        first_page_text = "\n".join(first_page_lines)
        detected_title = _extract_title(pdf, first_page_lines)
        title = detected_title or path.stem
        authors = _extract_authors(pdf, title, first_page_lines) if detected_title else []
        year = _extract_year(pdf, first_page_text)
        pdf_metadata = {k: str(v)[:300] for k, v in (pdf.metadata or {}).items()
                        if k in ("Title", "Author", "Subject", "Creator", "Producer", "CreationDate", "ModDate")
                        and isinstance(v, (str, int, float))}

    # Group lines into sections, remembering the page each paragraph starts on.
    sections: list[tuple[str, list[tuple[int, str]]]] = [("Front Matter", [])]
    for page_no, line in page_lines:
        name = _heading_name(line)
        if name:
            sections.append((name, []))
            continue
        # Inline "Abstract—text" / "Abstract. text" forms
        m = re.match(r"^\s*abstract\s*[\.:—\-]\s*(.+)$", line, re.I)
        if m:
            sections.append(("Abstract", [(page_no, m.group(1))]))
            continue
        sections[-1][1].append((page_no, line))

    abstract = ""
    chunks: list[Chunk] = []
    for name, lines in sections:
        if name.lower() in STOP_SECTIONS:
            break  # nothing after the references is useful evidence
        if not lines:
            continue
        text = " ".join(line.strip() for _, line in lines)
        text = re.sub(r"\s+", " ", text).strip()
        if name == "Abstract" and not abstract:
            abstract = text[:3000]
        if name == "Front Matter" and len(text) < 300:
            continue  # title/author block alone is not evidence

        # Map character offsets back to pages so each chunk knows where it came from.
        offsets: list[tuple[int, int]] = []
        pos = 0
        for page_no, line in lines:
            offsets.append((pos, page_no))
            pos += len(line.strip()) + 1

        def page_at(char_pos: int) -> int:
            page = offsets[0][1]
            for start, p in offsets:
                if start > char_pos:
                    break
                page = p
            return page

        buf, buf_start, cursor = "", 0, 0
        for sentence in _split_sentences(text):
            idx = text.find(sentence, cursor)
            if idx < 0:
                idx = cursor
            if not buf:
                buf_start = idx
            buf = f"{buf} {sentence}".strip()
            cursor = idx + len(sentence)
            if len(buf) >= CHUNK_TARGET_CHARS:
                chunks.append(Chunk(f"{paper_id}:c{len(chunks):03d}", paper_id, page_at(buf_start), name, buf))
                buf = ""
        if len(buf) > 40:
            chunks.append(Chunk(f"{paper_id}:c{len(chunks):03d}", paper_id, page_at(buf_start), name, buf))

    if not abstract and chunks:
        abstract = chunks[0].text[:1200]
    if not chunks:
        raise IngestionError(f"No usable text sections found in {path.name}.", "empty")

    return ParsedPaper(
        id=paper_id, sha256=sha, title=title, authors=authors, year=year, abstract=abstract,
        source_file=path.name, num_pages=num_pages, chunks=chunks,
        title_detected=detected_title is not None, pages=pages, pdf_metadata=pdf_metadata,
    )


def _classify_open_error(path: Path, e: Exception) -> IngestionError:
    # pdfplumber wraps pdfminer errors, e.g. PdfminerException(PDFPasswordIncorrect()) whose str() is empty
    text = f"{type(e).__name__} {e!r} {e.__cause__!r}".lower()
    if "password" in text or "encrypt" in text:
        return IngestionError(f"{path.name} is password-protected or encrypted and cannot be read.", "encrypted")
    return IngestionError(f"{path.name} could not be parsed; the file may be corrupt.", "corrupt")
