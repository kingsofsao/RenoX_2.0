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
| `STORE_PAGES_IN_GRAPH` | `true` | Also store each page's full text as a `Page` node, so papers can be read in the FalkorDB browser. The PDF file itself stays in `data/uploads/` |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | CORS origins for direct browser→API calls |
| `MAX_UPLOAD_MB` | `25` | Per-file size limit (enforced while streaming) |
| `MAX_FILES_PER_UPLOAD` | `10` | Files per request |
| `RESEARCHMIND_DATA_DIR` | `<repo>/data` | Uploads, page text, extraction dumps |
| `EMBEDDING_BACKEND` / `EMBEDDING_MODEL` | `auto` / MiniLM-L6-v2 | Semantic vectors |
| `LLM_PROVIDER` | `auto` | Investigation LLM: `ollama`, `anthropic`, `none`. `auto` = anthropic if `ANTHROPIC_API_KEY` is set, else none (offline plan) |
| `LLM_MODEL` | — | Model name, e.g. `qwen2.5:1.5b` for Ollama (must be pulled first). For anthropic it overrides `ANTHROPIC_MODEL` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama API |
| `LLM_TIMEOUT_SECONDS` | `300` | Per model request. CPU-only machines need 600+ |
| `LLM_MAX_OUTPUT_TOKENS` / `LLM_CONTEXT_TOKENS` | `1024` / `8192` | Report length cap / model context window (Ollama `num_ctx`) |
| `LLM_MAX_CONTEXT_CHARS` / `LLM_MAX_TOOL_ROUNDS` | `9000` / `2` | Evidence pack size sent to the model / extra searches the model may request |
| `ANTHROPIC_API_KEY` | empty | Optional: LLM knowledge extraction at upload, and the Claude provider for investigations |
| `ANTHROPIC_MODEL` / `ANTHROPIC_TIMEOUT_SECONDS` | `claude-opus-5-5` / `120` | Model and per-request timeout |
| `AGENT_TOOL_TRANSPORT` | `mcp` | `mcp`: agent calls tools through the MCP server; `direct`: same tools without the protocol layer |
| `AGENT_MAX_TURNS` / `AGENT_EFFORT` | `14` / `high` | Claude tool-use rounds and effort per investigation |
| `INVESTIGATION_TIMEOUT_SECONDS` | `240` | Time budget; after it the agent stops calling tools and writes the report |
| `INVESTIGATION_MAX_CONCURRENT` | `2` | Investigations running at once; more requests get HTTP 429 |
| `HF_HUB_OFFLINE` | unset | Set to `1` after the first run to skip HuggingFace network checks for the cached embedding model |
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
| POST | `/api/investigations` | Body `{question, wait=true, use_llm=true}` (question 10-1000 chars). `wait=true`: 200 with the full result. `wait=false`: 202 with an id to poll. 409 no papers, 429 busy, 503 database down |
| GET | `/api/investigations/{id}` · `/api/investigations` | Status, live progress events and the result · recent investigations (in memory, cleared on restart) |

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
(:Paper)-[:HAS_PAGE]->(:Page {number, text, chars})<-[:ON_PAGE]-(:Chunk)       full page text (STORE_PAGES_IN_GRAPH)
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
  - the agent loop driven by a scripted fake LLM;
  - `test_investigation_mocked.py`: each MCP tool called independently through the MCP protocol, MCP/agent schema parity, the agent in offline and mocked-Claude modes, citation verification (fabricated ids flagged, unverifiable gaps dropped), missing/rejected credentials, Claude outage, tool failures, the time budget, and `POST/GET /api/investigations` (validation, 409/429/503/500, async polling, no secret leakage);
  - frontend `report.test.ts`: citation parsing, Markdown export and polling with retries.

  - `test_llm_providers.py` (mocked): Ollama client against a mock HTTP API (status ready / model missing / unreachable, streaming, tool calls, malformed output, timeouts), provider selection, and the grounded agent with a scripted model (citation mapping, extra searches and their limit, invented sources and quotes flagged, requirements labelled [R], fallbacks, no-evidence).

  No mocked test contacts a real model. **Live LLM tests** (`test_ollama_live.py`, marker `live_llm`) run real Ollama inference and are skipped unless Ollama and `LLM_MODEL` are available: `python -m pytest -q -m live_llm`.
- **Integration tests** (`-m integration`) run the real HTTP stack against a real FalkorDB engine. They cover:
  - multi-file upload and the duplicate case, with node counts unchanged;
  - listing, search and Cypher-injection safety;
  - paginated page text, the PDF download and deletion;
  - the graph overview, the research tools and the MCP server over stdio;
  - `test_investigation_integration.py`: the sample PDFs uploaded through the API, every MCP tool on the real graph, and an investigation whose every source is checked against stored chunks (paper id and page).

  They write only to throwaway graphs (`researchmind_pytest*`). To run them without FalkorDB Cloud, use a local engine: `docker run -d -p 6379:6379 falkordb/falkordb:latest`, then `$env:FALKORDB_TEST_URL="falkor://localhost:6379"`.

## Projects (workspaces)

Every paper, knowledge graph, evidence passage and investigation belongs to one **project**. Switch projects in the sidebar; manage them on the **Projects** page (create, rename, delete with name confirmation).

- **Isolation is enforced by the backend: one FalkorDB graph per project.** Project `prj_ab12…` lives in graph `<FALKORDB_GRAPH>__prj_ab12…` and in `data/projects/<id>/` (uploads, page text, extraction files). Every MCP tool, vector search and Cypher query - including the agent's free-form `graph_query` - runs against the project graph chosen on the server from the URL (`/api/projects/{id}/...`), so evidence cannot leak between projects.
- **Registry graph** `<FALKORDB_GRAPH>_registry` stores projects and saved investigations (question, requirements, status, report, citations, structured result, progress, timestamps). Saved investigations survive restarts; runs interrupted by a restart are marked `interrupted`.
- **Migration (automatic, no copying):** the existing graph `<FALKORDB_GRAPH>` and the existing `data/uploads`, `data/documents`, `data/processed` folders become the **Default project** (id `default`) on first start. The Default project cannot be deleted. To move papers into a new project, re-upload them there.
- **Legacy routes** `/api/papers`, `/api/graph/*`, `/api/investigations` still work and always mean the Default project.
- **Ownership:** projects carry an `owner_id` (currently `local`) and all access goes through `projects.authorize()`, ready for an authentication layer. **There is no login yet: anyone who can reach the API can read and change every project. Do not deploy publicly.**
- **Capacity:** FalkorDB Cloud free tier has 100 MB; about 2 MB per paper is used (embeddings + page text). Set `STORE_PAGES_IN_GRAPH=false` to save roughly a third.
- Cross-project questions are not supported (by design for now).

| Method | Path | Description |
|---|---|---|
| GET / POST | `/api/projects` | List (with paper and investigation counts) / create `{name, description}` |
| GET / PATCH / DELETE | `/api/projects/{id}` | Read / rename or describe / delete with body `{confirm_name}` (exact name; 409 while an investigation runs; Default project 403) |
| * | `/api/projects/{id}/papers…`, `/graph/…`, `/investigations…` | The data routes, scoped to the project |
| GET / DELETE | `/api/projects/{id}/investigations/{inv}` | Reopen a saved investigation / delete it |

### Evidence rules
- Retrieval, comparisons and gaps only use the active project's graph, and evidence must reach the relevance threshold (`MIN_EVIDENCE_RELEVANCE`, default 0.35) for the question.
- A **research gap** is shown only if it is concrete (generic sentences and review boilerplate are rejected) and supported by verified evidence from **at least two relevant papers** (recurring limitations, conflicting results, untested method x dataset combinations with valid entity names). Single-paper limitations are listed under Limitations instead.
- Reports separate **source-supported findings** (with paper + page citations), **model inferences** (hypotheses, LLM mode) and **open questions** (what the evidence does not answer). With no relevant evidence the report says so and the model is not asked.

## Research investigations

The **Investigate** page turns a research question into an evidence-backed report.

```
React Investigate page ──POST /api/investigations (wait=false)──► InvestigationManager (worker pool, time budget, 429 when busy)
        ▲   poll GET /api/investigations/{id} (progress events)                │
        │                                                                     ▼
        │                                     Investigator (researchmind/agent.py)
        │                                       ├─ Claude tool-use loop (ANTHROPIC_API_KEY set), or offline plan
        │                                       └─ every tool call ──► MCPToolClient (mcp_bridge.py)
        │                                                               └─► ResearchMind MCP server (mcp_server.py)
        │                                                                     └─► ResearchTools ──► FalkorDB
        └── structured result ◄── build_structured (investigation.py): findings, comparisons, gaps,
                                   limitations, confidence; every source re-verified in the graph
```

- **One tool surface.** The agent calls the same MCP server that Claude Desktop/Code use (`python -m researchmind.mcp_server`), in-process: `list_papers`, `search_evidence`, `get_paper`, `explore_entity` (multi-hop traversal), `find_related_papers`, `compare_claims`, `find_research_gaps`, `get_evidence`, `graph_query` (read-only).
- **Coverage.** Whatever path Claude takes, evidence search, claim comparison, gap finding and the top papers' records are always gathered, so every report has findings, comparisons, limitations and gaps grounded in the graph.
- **No invented sources.** Each `[n]` maps to a stored evidence chunk (paper id, page, quote). Cited ids that do not exist are marked `[unverified]` and reported; structured items whose evidence cannot be verified are dropped.
- **Gaps are candidates.** Every gap is labelled as a hypothesis from the ingested papers, with its supporting evidence, never as confirmed novelty.
- **Confidence is computed**, not asserted: coverage of papers and verified sources, detected conflicts, unverified citations, corpus size and mode, plus the agent's own assessment when Claude is used.
- **Failure handling.** Missing credentials → offline plan; rejected key or Claude API outage → offline plan with a warning; a failing tool is recorded and the investigation continues; database loss → 503 `database_unavailable`; other errors → 500 with a generic message (details only in server logs).

### LLM reasoning with Ollama (local)

Investigations use a real LLM when one is configured and reachable; otherwise they fall back to the offline plan. Reports always say which: *LLM report · ollama / qwen2.5:1.5b* or *Offline extractive report (no LLM)*.

Setup on Windows (PowerShell):

```powershell
winget install --id Ollama.Ollama --exact --source winget   # or download from https://ollama.com/download
ollama pull qwen2.5:1.5b          # ~1 GB; smallest model with usable tool calling. Larger: qwen2.5:3b / qwen2.5:7b (need more RAM)
ollama list                       # confirm the model is installed
```

Then in `backend\.env`:

```
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:1.5b
OLLAMA_BASE_URL=http://localhost:11434
LLM_TIMEOUT_SECONDS=600
INVESTIGATION_TIMEOUT_SECONDS=900
```

Restart the API. `GET /api/llm/status` (also inside `/api/health` → `config.llm`) reports `ready`, `model_missing` (run the `ollama pull` it suggests), `unreachable` (start the Ollama app) or `not_configured`.

How the Ollama path works (`researchmind/grounded.py`): evidence is retrieved first through the MCP tools and filtered by relevance; the model receives the question, your optional project requirements labelled **[R]** (never treated as evidence) and numbered source excerpts **[S1]…[Sn]** with paper and page; it may call `search_evidence` up to `LLM_MAX_TOOL_ROUNDS` times; every `[S#]` is mapped back to a stored evidence chunk and verified. Unknown source numbers become `[unverified]`, quotations that appear in no source are flagged, and an answer with no valid citation, an unreachable server, a missing model or a timeout all fall back to the offline report with a warning. If nothing relevant is stored, the model is not asked.

A new provider is added in `researchmind/llm.py` by implementing `chat()` and `status()` like `OllamaLLM`.

### Demonstrate a complete investigation

1. Start FalkorDB access (`FALKORDB_URL` in `backend/.env`), the API and the web app (see **Running**).
2. **Upload PDFs** → drop the three files from `data\papers\` → Upload. Wait for *Processed*.
3. **Investigate** → click the first example question (or type your own) → **Investigate**.
4. Watch the live trace of MCP tool calls. When it completes, review the summary, findings by paper, conflicting results, the methods/datasets table, candidate gaps (expand *Supporting evidence*), limitations and confidence.
5. Click any `[n]` chip to open that source: quote, page, *Paper details* and *Open PDF at page N*.
6. **Export Markdown** downloads the full report with numbered page-level sources.

From the CLI the same agent runs with `python -m researchmind.cli ask "..."` (add `--offline` to skip the LLM).

### UI testing without FalkorDB (mock)

`backend\tests\mock_server.py` runs the real API on port 8001 with the graph replaced by canned in-memory data (clearly labelled *MOCK* in the sidebar). Use it only to exercise the UI:

```powershell
cd backend; .\.venv\Scripts\python.exe tests\mock_server.py
# second terminal
cd frontend; $env:VITE_API_PROXY_TARGET="http://127.0.0.1:8001"; npm run dev -- --port 5174
```
