# ResearchMind AI

Research discovery over a **FalkorDB knowledge graph**. Upload scientific PDFs through a React workspace. A FastAPI backend extracts them page by page with pdfplumber and stores each paper, its evidence passages, and its methods, datasets, claims, findings and limitations as a connected graph.

```
React + Vite + Tailwind (frontend/)            FastAPI (backend/app/)                  FalkorDB Cloud
┌─────────────────────────────┐  /api/*   ┌──────────────────────────────┐   Cypher   ┌──────────────────┐
│ Overview · Library · Upload │ ────────► │ routes/  health, papers,     │ ─────────► │ Paper, Chunk,    │
│ Paper details · Graph view  │  (Vite    │          graph               │ (params)   │ Method, Dataset, │
│ Investigate (placeholder)   │   proxy)  │ services/ pdf_service,       │            │ Claim, Finding,  │
└─────────────────────────────┘           │           graph_service      │            │ Limitation, ...  │
                                          └──────────────┬───────────────┘            └──────────────────┘
                                                         │ uses
                                          ┌──────────────▼───────────────┐    page text   ┌──────────────────┐
                                          │ researchmind/ (domain core)  │ ─────────────► │ data/documents/  │
                                          │ ingest · extract · graph ·   │                │ data/uploads/    │
                                          │ embeddings · tools · agent · │                └──────────────────┘
                                          │ mcp_server · documents       │
                                          └──────────────────────────────┘
```

## Project structure

```
researchmind-ai/
├── frontend/                     React + TypeScript + Vite + Tailwind
│   ├── src/
│   │   ├── components/           Layout, sidebar health indicator, upload dropzone, paper table, UI kit
│   │   ├── pages/                Dashboard, Library, Upload, PaperDetail, Graph (React Flow), Investigate
│   │   ├── services/             api.ts (Axios client + error normalization), format.ts
│   │   ├── hooks/                HealthContext (polls /api/health), useAsync
│   │   ├── types/api.ts          Types mirroring the API schemas
│   │   ├── App.tsx · main.tsx · index.css
│   ├── package.json · vite.config.ts · tsconfig*.json
├── backend/
│   ├── app/                      FastAPI layer
│   │   ├── main.py               App, CORS, error handlers (no stack traces to clients)
│   │   ├── config.py             API settings from env
│   │   ├── database.py           Shared FalkorDB connection, health probe, reconnects
│   │   ├── routes/               health.py · papers.py · graph.py
│   │   ├── services/             pdf_service.py (streamed uploads) · graph_service.py (read models)
│   │   └── schemas/              paper.py · health.py (Pydantic response models)
│   ├── researchmind/             Domain core: PDF parsing, extraction, graph store, embeddings,
│   │                             document store, research tools, MCP server, agent, CLI
│   ├── scripts/                  sample PDF generator, MCP smoke test, standalone connection test
│   ├── tests/                    pytest: mocked + integration
│   ├── requirements.txt · .env.example · pytest.ini
├── data/papers/                  3 synthetic sample PDFs (labelled as synthetic)
├── README.md · .gitignore
```

## Setup on Windows (PowerShell)

Requires Python 3.10+ and Node.js 20+.

```powershell
cd C:\Users\surya\OneDrive\Desktop\Files\Projects\researchmind-ai

# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env                        # set FALKORDB_URL (see "Configuring .env safely")

# Frontend (new terminal)
cd C:\Users\surya\OneDrive\Desktop\Files\Projects\researchmind-ai\frontend
npm install
```

## Running

Terminal 1, the API:

```powershell
cd C:\Users\surya\OneDrive\Desktop\Files\Projects\researchmind-ai\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Terminal 2, the web app:

```powershell
cd C:\Users\surya\OneDrive\Desktop\Files\Projects\researchmind-ai\frontend
npm run dev
```

Open **http://localhost:5173**. In development the React app calls relative `/api/...` URLs, and Vite proxies them to `http://127.0.0.1:8000`, so the browser never needs CORS. Interactive API docs are at http://localhost:8000/docs.

The first upload after startup can take a few seconds longer because the embedding model loads in the background; the first-ever run also downloads it (~90 MB).

## Configuring `.env` safely

- Put secrets only in `backend/.env`. It is git-ignored, and `.env.example` holds placeholders only.
- `FALKORDB_URL` comes from the FalkorDB Cloud console: `falkor://USER:PASSWORD@HOST:PORT`, or `falkors://` if TLS is required. Paste it into `backend/.env`, never into code or the frontend.
- The frontend has no secrets. `frontend/.env` is optional and only changes where API calls go (`VITE_API_BASE_URL`, `VITE_API_PROXY_TARGET`).
- The API never returns the connection URL, credentials or stack traces. Errors come back as `{"error": {"code", "message"}}`, and the details go to the server log only.
- If the URL is ever exposed, rotate the password in the FalkorDB console.

| Variable | Default | Purpose |
|---|---|---|
| `FALKORDB_URL` | — (required) | FalkorDB connection URL |
| `FALKORDB_GRAPH` | `researchmind` | Graph name |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | CORS origins for direct browser→API calls |
| `MAX_UPLOAD_MB` | `25` | Per-file size limit (enforced while streaming) |
| `MAX_FILES_PER_UPLOAD` | `10` | Files per request |
| `RESEARCHMIND_DATA_DIR` | `<repo>/data` | Uploads, page text, extraction dumps |
| `EMBEDDING_BACKEND` / `EMBEDDING_MODEL` | `auto` / MiniLM-L6-v2 | Semantic vectors |
| `ANTHROPIC_API_KEY` | empty | Optional: LLM extraction now, agent in the next phase |
| `FALKORDB_TEST_URL` | `FALKORDB_URL` | FalkorDB for integration tests |

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Always 200 while the API is up. `database.status` is `connected`, `unavailable` or `not_configured`, with latency |
| POST | `/api/papers/upload` | Multipart field `files` (one or more PDFs). Returns a result per file: `processed`, `duplicate`, `failed` or `rejected` |
| GET | `/api/papers` | `?status=processed\|failed&search=&limit=&offset=`. Returns papers plus real counts |
| GET | `/api/papers/{id}` | Metadata, extracted-knowledge summary and paginated page text (`?page=&page_size=`) |
| GET | `/api/papers/{id}/file` | The original PDF |
| DELETE | `/api/papers/{id}` | Removes the paper, its owned graph nodes, page text and stored PDF |
| GET | `/api/graph/stats` · `/api/graph/overview` | Node and relationship counts · papers, methods, datasets and contradictions for React Flow |

## How PDF ingestion works

1. **Validate while streaming.** The upload is written to disk in 1 MB chunks while it is hashed. Files without a `.pdf` name or without `%PDF-` magic bytes are rejected, as are empty files. Anything over `MAX_UPLOAD_MB` is cut off and its partial file deleted. Nothing holds a whole PDF in memory.
2. **Stable id from content.** `paper_id = "p_" + sha256[:12]`. The PDF is stored once as `data/uploads/<paper_id>.pdf`. Uploading identical bytes again under any name returns `duplicate` and skips processing entirely.
3. **Extract page by page.** pdfplumber reads each page (two-column layouts left column first) and frees each page's cache after use. It extracts page text, sections, page-anchored evidence chunks, and basic PDF metadata such as producer and dates.
4. **No invented metadata.** The title comes from PDF metadata or the largest-font block on page 1, and authors only from name-like lines below a detected title. If no title is found, the API returns `title: null` and the UI says "Title not detected". Authors are left empty rather than guessed.
5. **Graceful failures.** Each failure gets a specific code:
   - `encrypted`: password-protected PDF.
   - `corrupt`: unparseable file.
   - `no_text`: image-only scan; OCR is a later enhancement.
   - `empty`: no text at all.

   Failures are stored as `Paper {status: "failed", error, error_code}`, so the dashboard counts them and a fixed re-upload retries cleanly.
6. **Write to the graph idempotently.** Every write is a parameterized `MERGE` keyed on deterministic ids, so values are never concatenated into Cypher. Re-processing replaces the paper's own nodes, and shared Method/Dataset nodes are reused.

### Storage decision: page text on disk, knowledge in the graph

Full page text lives in `data/documents/<paper_id>/pages/0001.txt …` with a `meta.json`, written atomically. The `Paper` node stores `document_key`, the hash, page count, status and metadata. Reasons:

- Large raw text would bloat FalkorDB's in-memory store, especially on a Cloud free tier.
- One page per file lets `GET /api/papers/{id}?page=N` read only the requested pages.

The graph still holds everything needed for reasoning: page-anchored `Chunk` evidence passages with embeddings (native vector and full-text indexes) and the extracted entities. In production the document folder would move to object storage (S3/Blob) under the same key.

### Graph schema (current)

```
(:Paper {id, title, title_detected, authors, year, num_pages, sha256, status, error, error_code,
         source_file, file_size, document_key, extractor, ingested_at})
(:Author)-[:AUTHORED]->(:Paper)-[:HAS_CHUNK]->(:Chunk {page, section, text, embedding})
(:Paper)-[:USES_METHOD]->(:Method)   (:Paper)-[:USES_DATASET]->(:Dataset)        shared across papers
(:Paper)-[:MAKES_CLAIM|REPORTS_FINDING|HAS_LIMITATION]->(:Claim|:Finding|:Limitation)-[:SUPPORTED_BY]->(:Chunk)
(:Claim|Finding)-[:SIMILAR_TO|CONTRADICTS]->(:Claim|Finding)   (:Limitation)-[:ADDRESSED_BY]->(...)
```

## Upload a PDF and confirm it is in FalkorDB

1. Start both servers and open http://localhost:5173. The sidebar should show **API: Online** and **FalkorDB: Connected**.
2. Go to **Upload PDFs** and drag in one or more PDFs; `data\papers\*.pdf` holds three samples. Click **Upload**. Each file shows upload progress, then a result such as *Processed 2 pages: 6 evidence chunks, …*.
3. **Paper library** lists the paper with status and page count. Open it to see the metadata and page-by-page extracted text.
4. To confirm in the database itself:
   - **FalkorDB Cloud console → Graph `researchmind` → Query:** `MATCH (p:Paper) RETURN p.id, p.title, p.status, p.num_pages`
   - **Or from the CLI:** `cd backend` then `python -m researchmind.cli stats`
   - **Or via the API:** `curl http://localhost:8000/api/papers`
5. Upload the same file again. It is reported as **duplicate**, and node counts on the Overview page don't change.

## Tests

```powershell
cd backend
python -m pytest -q                              # all tests; integration tests skip without FalkorDB
python -m pytest -q -m "not integration"         # mocked/unit tests only
cd ..\frontend
npm run build                                    # TypeScript check + production build
npm test                                         # Vitest unit tests
```

- **Mocked tests** (`test_api_mocked.py`, `test_agent.py`, parts of `test_ingest_extract.py`, frontend `api.test.ts`) need no database. They cover:
  - health when FalkorDB is unconfigured or unreachable, with credentials never leaked;
  - 503 handling when the database is down;
  - invalid, empty and oversized uploads, and the file-count limit;
  - classification of encrypted, scanned and blank PDFs, and unknown-title handling;
  - the agent loop driven by a scripted fake LLM.
- **Integration tests** (`-m integration`) run the real HTTP stack against a real FalkorDB engine. They cover:
  - multi-file upload and the duplicate case, with node counts unchanged;
  - listing, search and Cypher-injection safety;
  - paginated page text, the PDF download and deletion;
  - the graph overview, the research tools and the MCP server over stdio.

  They write only to throwaway graphs (`researchmind_pytest*`). To run them without FalkorDB Cloud, use a local engine: `docker run -d -p 6379:6379 falkordb/falkordb:latest`, then `$env:FALKORDB_TEST_URL="falkor://localhost:6379"`.

## Next phase: already in `backend/researchmind/`

Implemented and tested in the domain core, not yet exposed in the React UI:

- **Knowledge extraction:** methods, datasets, claims, findings and limitations, with a heuristic extractor or an optional LLM extractor (structured output). Every item is verified against its evidence quote.
- **Cross-paper links:** `SIMILAR_TO`, `CONTRADICTS` and `ADDRESSED_BY`.
- **Semantic retrieval:** SentenceTransformers vectors in FalkorDB's native vector index. Qdrant can be added behind `embeddings.py` and `tools.search_evidence` if the corpus outgrows it.
- **MCP server:** `python -m researchmind.mcp_server`, with tools for evidence search, multi-hop traversal, claim comparison and gap candidates.
- **Investigation agent:** cited reports with candidate research gaps, which are labelled as hypotheses rather than claimed as novel. Run it with `python -m researchmind.cli ask "..."`.

The **Investigate** page is a placeholder until the agent gets an API endpoint.
