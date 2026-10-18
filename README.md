# ResearchMind AI

Evidence-grounded research analysis over a **FalkorDB knowledge graph**. Researchers create an account, upload
scientific PDFs and ask questions about one paper at a time. Each paper becomes its own knowledge graph (evidence
passages, methods, datasets, claims, findings, limitations), and an AI analyst answers from that graph through MCP
tools, citing every statement to a page. Every account is private, the interface is available in nine languages with
light and dark themes, and the stack is ready to deploy behind HTTPS.

```
React + Vite + Tailwind (frontend/)            FastAPI (backend/app/)                  FalkorDB Cloud
┌─────────────────────────────┐  /api/*   ┌──────────────────────────────┐   Cypher   ┌──────────────────┐
│ Sign in · Overview · Upload │ ────────► │ routes/  auth, projects,     │ ─────────► │ Paper, Chunk,    │
│ Library · Paper · Graph     │  (Vite    │   papers, graph, investig.   │ (params)   │ Method, Dataset, │
│ Investigate · Settings      │   proxy)  │ services/ pdf_service,       │            │ Claim, Finding,  │
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
│   │   ├── auth/                 AuthProvider (session, preferences), RequireAuth / PublicOnly guards, safe redirects
│   │   ├── i18n/                 Typed translations: en.ts (source) + locales/ (es fr de hi ta zh ja ar), RTL support
│   │   ├── theme/                Light / dark / system theme
│   │   ├── components/           Layout, auth shell, paper picker, investigation report, UI kit (theme tokens)
│   │   ├── pages/                Sign in/up, Overview, Investigate, Library, Upload, Paper, Graph, Projects, Settings
│   │   ├── services/             api.ts (session cookies, CSRF header), errors.ts, report.ts (export), format.ts
│   │   ├── hooks/                ProjectContext, HealthContext, useAsync
│   │   └── index.css             Design tokens for both themes, animations
│   ├── Dockerfile · nginx.conf   Production image: nginx with strict security headers, /api proxy
├── backend/
│   ├── app/                      FastAPI layer
│   │   ├── main.py               App, middleware, error handlers (no stack traces to clients)
│   │   ├── auth.py · security.py Sessions, CSRF cookies · Argon2id, password policy, tokens
│   │   ├── middleware.py         Rate limit, CSRF/origin checks, size limits, security headers
│   │   ├── ratelimit.py          Sliding-window limiters
│   │   ├── database.py           FalkorDB connections, account store, per-project graphs
│   │   ├── routes/               auth · projects · papers · graph · investigations · health
│   │   ├── services/             pdf_service (streamed uploads) · graph_service · investigation_service
│   │   └── schemas/              Pydantic request/response models
│   ├── researchmind/             Domain core: accounts, projects, PDF parsing, extraction, graph store, embeddings,
│   │                             research tools, MCP server, AI agent, CLI
│   ├── tests/                    pytest: mocked + integration (real FalkorDB) + live LLM
│   ├── Dockerfile · requirements.txt · requirements-dev.txt · .env.example
├── docker-compose.yml            Production stack: FalkorDB + API + web
├── data/papers/                  3 synthetic sample PDFs (labelled as synthetic)
```

## Setup on Windows (PowerShell)

Requires Python 3.10+ and Node.js 20+.

```powershell
cd C:\Users\surya\OneDrive\Desktop\Files\Projects\researchmind-ai

# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements-dev.txt   # runtime + test tools (production images use requirements.txt)
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

Open **http://localhost:5173** and **create an account** (there are no built-in or demo accounts). Your first project,
*My research*, is created automatically. In development the React app calls relative `/api/...` URLs and Vite proxies
them to `http://127.0.0.1:8000`, so cookies stay first-party and no CORS is needed. Interactive API docs are at
http://localhost:8000/docs in development only (they are switched off with `ENVIRONMENT=production`).

The first upload after startup can take a few seconds longer because the embedding model loads in the background; the first-ever run also downloads it (~90 MB).

## Configuring `.env` safely

- Put secrets only in `backend/.env`. It is git-ignored, and `.env.example` holds placeholders only.
- `FALKORDB_URL` comes from the FalkorDB Cloud console: `falkor://USER:PASSWORD@HOST:PORT`, or `falkors://` if TLS is required. Paste it into `backend/.env`, never into code or the frontend.
- The frontend has no secrets. `frontend/.env` is optional and only changes where API calls go (`VITE_API_BASE_URL`, `VITE_API_PROXY_TARGET`).
- The API never returns the connection URL, credentials or stack traces. Errors come back as `{"error": {"code", "message"}}`, and the details go to the server log only.
- If the URL is ever exposed, rotate the password in the FalkorDB console.

| Variable | Default | Purpose |
|---|---|---|
| `FALKORDB_URL` | required | FalkorDB connection URL |
| `ENVIRONMENT` | `development` | `production` turns on Secure `__Host-` cookies and HSTS, and turns off `/docs` |
| `COOKIE_SECURE` | `false` | Secure cookies outside production (only when served over HTTPS) |
| `SESSION_TTL_HOURS` / `SESSION_IDLE_HOURS` | `168` / `24` | Absolute session lifetime / sign-out after inactivity |
| `ALLOW_SIGNUP` | `true` | `false` stops new registrations; existing users can still sign in |
| `AI_REQUIRED` | `true` | Investigations always use the AI model and fail clearly when it is unavailable, instead of falling back to an extractive report |
| `INVESTIGATIONS_PER_USER` / `INVESTIGATIONS_PER_HOUR` / `UPLOADS_PER_HOUR` | `1` / `30` / `60` | Per-account concurrency and hourly quotas |
| `RATE_LIMIT_PER_MINUTE` / `AUTH_ATTEMPTS_PER_WINDOW` | `240` / `20` | Requests per IP per minute / sign-in and sign-up attempts per IP per 15 minutes |
| `FALKORDB_GRAPH` | `researchmind` | Graph name |
| `STORE_PAGES_IN_GRAPH` | `true` | Also store each page's full text as a `Page` node, so papers can be read in the FalkorDB browser. The PDF file itself stays in `data/uploads/` |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | CORS origins for direct browser→API calls |
| `MAX_UPLOAD_MB` | `25` | Per-file size limit (enforced while streaming) |
| `MAX_FILES_PER_UPLOAD` | `10` | Files per request |
| `RESEARCHMIND_DATA_DIR` | `<repo>/data` | Uploads, page text, extraction dumps |
| `EMBEDDING_BACKEND` / `EMBEDDING_MODEL` | `auto` / MiniLM-L6-v2 | Semantic vectors |
| `LLM_PROVIDER` | `auto` | Investigation LLM: `ollama`, `anthropic`, `none`. `auto` = anthropic if `ANTHROPIC_API_KEY` is set, else none. With `AI_REQUIRED=true` a provider must be configured |
| `LLM_MODEL` | none | Model name, e.g. `qwen3:8b` for Ollama (must be pulled first). For anthropic it overrides `ANTHROPIC_MODEL` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama API |
| `LLM_TIMEOUT_SECONDS` | `300` | Per model request. CPU-only machines need 600+ |
| `LLM_MAX_OUTPUT_TOKENS` / `LLM_CONTEXT_TOKENS` | `1024` / `8192` | Report length cap / model context window (Ollama `num_ctx`) |
| `LLM_MAX_CONTEXT_CHARS` / `LLM_MAX_TOOL_ROUNDS` | `9000` / `2` | Evidence pack size sent to the model / extra searches the model may request |
| `ANTHROPIC_API_KEY` | empty | Optional: LLM knowledge extraction at upload, and the Claude provider for investigations |
| `ANTHROPIC_MODEL` / `ANTHROPIC_TIMEOUT_SECONDS` | `claude-opus-5-5` / `120` | Model and per-request timeout |
| `AGENT_TOOL_TRANSPORT` | `mcp` | `mcp`: agent calls tools through the MCP server; `direct`: same tools without the protocol layer |
| `AGENT_MAX_TURNS` / `AGENT_EFFORT` | `14` / `high` | Claude tool-use rounds and effort per investigation |
| `INVESTIGATION_TIMEOUT_SECONDS` | `240` | Time budget; after it the agent stops calling tools and writes the report |
| `INVESTIGATION_MAX_CONCURRENT` | `2` | Investigations running at once across all users; more requests get HTTP 429 |
| `HF_HUB_OFFLINE` | unset | Set to `1` after the first run to skip HuggingFace network checks for the cached embedding model |
| `FALKORDB_TEST_URL` | `FALKORDB_URL` | FalkorDB for integration tests |

## API

Every route except `/api/health/live` and the sign-in/sign-up routes needs a signed-in session. State-changing requests
(POST/PATCH/DELETE) must send the CSRF token from the `rm_csrf` cookie in the `X-CSRF-Token` header (the web app does this
automatically). A project of another account always answers 404, so its existence is never revealed.

| Method | Path | Description |
|---|---|---|
| GET | `/api/health/live` | Public liveness probe: `{"status": "ok"}` only |
| GET | `/api/health` · `/api/llm/status` | Signed in: service, database and AI-model status, without URLs, graph names or other internals |
| GET | `/api/auth/csrf` | Issues the CSRF cookie |
| POST | `/api/auth/signup` · `/api/auth/login` · `/api/auth/logout` | `{email, password, name, language?, theme?}` · `{email, password, remember}` · ends the session server-side |
| GET / PATCH / DELETE | `/api/auth/me` | Profile · change `{name, language, theme}` · delete the account and all its data (body `{password}`) |
| POST | `/api/auth/password` | `{current_password, new_password}`; signs out every other session |
| GET / DELETE | `/api/auth/sessions` | Active sessions · sign out all other devices |
| GET | `/api/auth/session` | `{user}` for the signed-in account or `{user: null}` for a visitor (the app's start-up check) |
| GET | `/api/forms/challenge` | Signed time challenge for the sign-up and contact forms (spam protection) |
| POST | `/api/contact` | `{name, email, topic, message, challenge, website}`; 202 |
| POST | `/api/analytics/event` | `{event, path, utm_*}`; sent only after the visitor allows statistics; stores daily counts, never IPs or ids |
| GET | `/api/admin/analytics?days=` · `/api/admin/messages` | Site statistics and contact messages; accounts in `ADMIN_EMAILS` only (404 for everyone else) |
| GET / POST | `/api/projects` | The account's projects (with counts) · create `{name, description}` |
| GET / PATCH / DELETE | `/api/projects/{id}` | Read · rename/describe · delete with body `{confirm_name}` (exact name; 409 while an investigation runs) |
| POST | `/api/projects/{id}/papers/upload` | Multipart field `files`. A result per file: `processed`, `duplicate`, `failed` or `rejected` |
| GET | `/api/projects/{id}/papers` | `?status=processed\|failed&search=&limit=&offset=` |
| GET / DELETE | `/api/projects/{id}/papers/{paper}` | Metadata, knowledge summary and paginated page text · delete the paper and its graph |
| GET | `/api/projects/{id}/papers/{paper}/file` | The original PDF |
| GET | `/api/projects/{id}/graph/stats` · `/graph/overview` | Counts · papers with their own methods and datasets |
| POST | `/api/projects/{id}/investigations` | `{question, paper_id, requirements?, language?, wait=false}`. Exactly one paper. 202 with an id to poll; 404 unknown paper; 429 busy or over quota; 503 `ai_unavailable` / `database_unavailable` |
| GET / DELETE | `/api/projects/{id}/investigations[/{inv}]` | History (newest first) · one investigation with live progress and result · delete it |

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
(:Author {paper_id})-[:AUTHORED]->(:Paper)-[:HAS_CHUNK]->(:Chunk {paper_id, page, section, text, embedding})
(:Paper)-[:HAS_PAGE]->(:Page {number, text, chars})<-[:ON_PAGE]-(:Chunk)       full page text (STORE_PAGES_IN_GRAPH)
(:Paper)-[:USES_METHOD]->(:Method {paper_id})   (:Paper)-[:USES_DATASET]->(:Dataset {paper_id})
(:Paper)-[:MAKES_CLAIM|REPORTS_FINDING|HAS_LIMITATION]->(:Claim|:Finding|:Limitation)-[:SUPPORTED_BY]->(:Chunk)
(:Claim|Finding)-[:ABOUT_METHOD]->(:Method)   (:Finding)-[:EVALUATED_ON]->(:Dataset)
```

**Paper isolation.** Every node belongs to exactly one paper: methods, datasets and authors are per paper (ids
`<paper_id>:<slug>`) and no edges are ever created between papers. Re-uploading identical bytes replaces only that paper.

## Upload a PDF and confirm it is in FalkorDB

1. Start both servers, open http://localhost:5173 and sign in. The sidebar status should show **Service: Online**,
   **Database: Connected** and **AI model: Ready**.
2. Go to **Upload papers** and drag in one or more PDFs; `data\papers\*.pdf` holds three samples. Each file shows its
   upload progress, then a result such as *Processed 2 pages and built the knowledge graph*.
3. **Paper library** lists the paper with status and page count. Open it to see the metadata and the extracted text.
4. To confirm in the database itself: in the FalkorDB console, open the project's graph `<FALKORDB_GRAPH>__prj_…` and run
   `MATCH (p:Paper) RETURN p.id, p.title, p.status, p.num_pages`.
5. Upload the same file again. It is reported as **already added**, and the counts on the Overview page don't change.

## Deployment

The repository ships a production stack in `docker-compose.yml`:
**Caddy (HTTPS) → nginx serving the built React app → FastAPI → FalkorDB**. Only Caddy is published (ports 80 and 443);
the web server, the API and the database are reachable on the internal Docker network only.

1. **Domain.** Point your domain's DNS `A`/`AAAA` records (and `www`, optional) at the server.
2. **Settings.** On the server:
   ```bash
   cp .env.example .env                    # DOMAIN, ACME_EMAIL, FALKORDB_PASSWORD (openssl rand -hex 32), OPERATOR_NAME, CONTACT_EMAIL
   cp backend/.env.example backend/.env    # AI provider, ADMIN_EMAILS, limits
   ```
   In `backend/.env` set the AI provider (`LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`, or Ollama via `OLLAMA_BASE_URL`)
   and `ADMIN_EMAILS` (the accounts that may open *Site statistics*). `ENVIRONMENT=production` and
   `ALLOWED_ORIGINS=https://$DOMAIN` are set by the compose file.
3. **Start.** `docker compose up -d --build`. Caddy obtains and renews the Let's Encrypt certificate itself, redirects
   `http://` to `https://` and `www.` to the bare domain. The build bakes `https://$DOMAIN` into the canonical links,
   social previews, `sitemap.xml` and `robots.txt`.
4. **Operate.** Keep one API process (investigations and their progress are held in memory). Back up the
   `falkordb-data`, `app-data` and `caddy-data` volumes. Check dependencies with `pip-audit -r backend/requirements.txt`
   and `npm audit`.

`frontend/nginx.conf` (with `security-headers.conf` on every response) sets a strict Content-Security-Policy (no inline
or third-party scripts), HSTS, `frame-ancestors 'none'`, caches fingerprinted assets for a year and images for a week,
answers unknown paths with a real **404** status (the app's not-found page), never serves source maps or dotfiles, and
takes the visitor's address from `X-Forwarded-For` only when it comes from a private-network proxy, so client IPs used for
rate limiting cannot be spoofed. The API container runs as a non-root user with a read-only filesystem and no capabilities.

### Alternative: Vercel (web app) + Render (API) + FalkorDB Cloud

`frontend/vercel.json` serves the built app with the same headers as `nginx.conf` and proxies `/api/*` to the API on
Render, so the browser still talks to one origin (first-party cookies, no CORS). Vercel adds a secret
`x-origin-secret` header to every proxied request; with `ORIGIN_SECRET` set, the API answers anything without it with
404, and takes the visitor's address for rate limits from Vercel's `x-real-ip`. Uploads that take longer than Vercel's
120-second proxy limit are answered as a stream that keeps the connection open.

1. **Database.** Create a FalkorDB Cloud instance close to the Render region in `render.yaml` (Singapore) and build its
   connection URL from the console: `falkor://USERNAME:PASSWORD@HOST:PORT` (`falkors://` only if TLS is enabled).
2. **API on Render.** Push the repository to GitHub. Render dashboard -> **New -> Blueprint** -> pick the repository
   (`render.yaml`). Fill in `ALLOWED_ORIGINS` (your Vercel address, e.g. `https://researchmind.vercel.app`),
   `FALKORDB_URL`, `ADMIN_EMAILS` and `ANTHROPIC_API_KEY`. Note the service address (e.g.
   `https://researchmind-api.onrender.com`) and copy the generated `ORIGIN_SECRET` from the service's Environment tab.
3. **Web app on Vercel.** If the Render address differs from `https://researchmind-api.onrender.com`, change the
   `dest` of the `/api/(.*)` route in `frontend/vercel.json`. Vercel -> **Add New -> Project** -> import the repository,
   **Root Directory** `frontend`. Environment variables: `ORIGIN_SECRET` (the value from Render), `VITE_SITE_URL`
   (your Vercel address), `VITE_OPERATOR_NAME`, `VITE_CONTACT_EMAIL`. Deploy.
4. **Check.** `https://<render address>/api/health` must answer 404 (direct access refused), and the site must sign up,
   upload and investigate normally.

`render.yaml` uses Render's **free** plan: the image is built with `EMBEDDINGS=light` (no PyTorch; built-in hashing
embedder) to fit in 512 MB, the service sleeps after 15 minutes without traffic, and its disk is wiped on every
restart or deploy. Accounts, projects, knowledge graphs and investigations live in FalkorDB and are kept; uploaded PDFs
and their page text are not (the paper page then says the text is unavailable). For real users choose a paid plan,
add a persistent disk mounted at `/data`, and drop `EMBEDDINGS`/`EMBEDDING_BACKEND` to use the full embedding model
(about 1 GB of memory).

### Before launch

Things only you can do:

- [ ] Register the domain, point DNS at the server, fill in `.env` and start the stack (above).
- [ ] Put your real name or company and a monitored address in `OPERATOR_NAME` and `CONTACT_EMAIL`: they appear in the
      Privacy Policy, the Terms and the contact form.
- [ ] Have the Privacy Policy and Terms (`frontend/src/i18n/legal/en.ts`) reviewed for your jurisdiction. They describe
      exactly what this code does, but they are not legal advice. Translations say the English version prevails.
      Change `legalUpdated` in `frontend/src/config/site.ts` whenever you edit them.
- [ ] Sign up with an address listed in `ADMIN_EMAILS` to read contact messages and site statistics.
- [ ] After launch, submit `https://<domain>/sitemap.xml` in Google Search Console and check the social preview with a
      link-preview debugger.

## Public site and launch checklist

| Item | Where |
|---|---|
| Landing page with one call to action ("Create your account"), real product screenshots, expandable FAQ | `pages/LandingPage.tsx` |
| Privacy Policy and Terms (9 languages, last-updated date, table of contents) | `pages/LegalPage.tsx`, `i18n/legal/` |
| Custom 404 (real 404 status from nginx) | `pages/NotFoundPage.tsx`, `nginx.conf` |
| Meta title and description per page, canonical links, Open Graph / Twitter cards, 1200x630 social image | `hooks/usePageMeta.ts`, `index.html`, `public/og-image.png` |
| Favicon (SVG, ICO, Apple touch icon, maskable PWA icons, web manifest) | `public/` |
| `sitemap.xml` and `robots.txt` generated at build time from `VITE_SITE_URL` | `vite.config.ts` |
| Images: alt text on every image, WebP, 640px and 1200px variants with `srcset`, explicit sizes (no layout shift) | `public/images/` |
| Cookie banner (essential only / allow statistics), changeable later from the footer and Settings | `components/ConsentBanner.tsx` |
| Analytics: cookieless, consent-gated daily counts (page views, sign-ups, uploads, investigations), UTM campaign capture, admin view with chart and table | `services/analytics.ts`, `routes/site.py`, `pages/AdminPage.tsx` |
| Contact: floating button and footer link, form validation, success and error states | `components/ContactWidget.tsx` |
| Spam protection on sign-up and contact: signed time challenge, honeypot field, per-IP limits | `security.py`, `routes/site.py` |
| Site search (Ctrl/Cmd+K over pages, papers and investigations) | `components/CommandPalette.tsx` |
| Dark mode toggle, sticky headers, mobile menu, skip to content, back to top, scroll progress bar | `PublicLayout.tsx`, `Layout.tsx`, `ScrollAids.tsx` |
| Copy buttons (answer, quotes, Markdown report, paper id), confirmation dialogs for destructive actions | `CopyButton.tsx`, `Modal.tsx` |
| Password visibility toggle, form error and success states, loading animations and progress bars, hover states | `PasswordField.tsx`, `ui.tsx` |
| Print stylesheet (report only, black on white) | `index.css` |
| No secrets in the front end: API keys stay on the server; the build contains only the public site URL, operator name and contact address | `frontend/.env.example` |

Measured on the production build (Lighthouse 12, public pages): desktop 100 performance / 100 accessibility /
100 best practices / 100 SEO; mobile 90-94 performance and 100 for the rest. axe-core finds no WCAG 2.1 A/AA violations on
any public or signed-in page in either theme.

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
- `test_auth_security.py` (mocked): sign-up/sign-in/sign-out, Argon2id storage, cookie flags, password policy, email
  validation, identical responses for unknown emails, account lockout, rate limits, server-side session revocation,
  hashed session ids, idle expiry, session rotation, password change, CSRF and cross-site refusal, 401 on every data
  route, cross-account 404s, account deletion, security headers and request-size limits.
- `test_paper_scope.py`: an investigation reads exactly one paper; no whole-library mode; broad questions still reach
  the AI with the paper's own evidence; the report language reaches the model.
- Frontend `i18n.test.ts`: every language has every key with the same placeholders and is really translated; password
  rules mirror the server; the progress estimate. `api.test.ts`: CSRF header, single-paper requests, safe redirects.
- **Integration tests** (`-m integration`) run the real HTTP stack against a real FalkorDB engine, with real accounts. They cover:
  - multi-file upload and the duplicate case, with node counts unchanged;
  - listing, search and Cypher-injection safety;
  - paginated page text, the PDF download and deletion;
  - the graph overview, the research tools and the MCP server over stdio;
  - `test_investigation_integration.py`: the sample PDFs uploaded through the API, every MCP tool on the real graph, and an investigation whose every source is checked against stored chunks (paper id and page).

  - `test_projects_integration.py`: two accounts with unrelated papers can never see each other's projects, papers,
    PDFs, graph or investigations; every investigation cites only its own paper; Argon2id hashes and hashed session
    ids in the database; account deletion drops the account's graphs. `test_graph_tools.py`: no node is shared by two
    papers and no edge connects two papers.

  They write only to throwaway graphs (`researchmind_pytest*`). To run them without FalkorDB Cloud, use a local engine: `docker run -d -p 6379:6379 falkordb/falkordb:latest`, then `$env:FALKORDB_TEST_URL="falkor://localhost:6379"`.

## Accounts and security

- **Accounts.** Sign up with name, email and password; there are no demo or built-in accounts. Users are stored in the
  registry graph; passwords as **Argon2id** hashes (never logged or returned). Password policy: 12-128 characters,
  not a common password, not containing the user's name or email; the sign-up form shows the same rules live.
- **Sessions.** An opaque 256-bit token in an **httpOnly, SameSite=Lax** cookie (`__Host-` prefixed and **Secure** in
  production); only its SHA-256 is stored, so a database dump holds no usable sessions. Sessions expire after
  `SESSION_TTL_HOURS` and after `SESSION_IDLE_HOURS` of inactivity, sign-in always issues a new session (no fixation),
  sign-out deletes it server-side, a password change signs out every other device, and Settings lists sessions.
- **Brute force.** Sign-in and sign-up are rate limited per IP; an account locks for 15 minutes after 8 wrong passwords;
  the response for a wrong password, an unknown email and a locked account is identical and takes the same time.
- **CSRF and cross-site requests.** Double-submit token (`X-CSRF-Token` must equal the `rm_csrf` cookie) on every
  state-changing request, plus `Origin` / `Sec-Fetch-Site` checks against `ALLOWED_ORIGINS`.
- **Isolation between accounts.** Every project has an `owner_id`; every request resolves the project on the server and
  checks ownership (`projects.authorize`), answering 404 for other users' projects, papers, PDFs and investigations.
  Each project is its own FalkorDB graph and data folder. Deleting an account deletes all of its projects, graphs, files,
  investigations and sessions.
- **Isolation between papers.** An investigation analyses exactly **one** paper (`paper_id` is required). All tools are
  filtered to it, free-form `graph_query` is disabled, the evidence given to the AI is filtered again, and the knowledge
  graph never links papers (see *Graph schema*).
- **Hardening.** Per-IP request limits and per-account upload/investigation quotas; request-size limits checked before
  bodies are read; uploads validated by content (`%PDF-`), size and count; strict security headers on every response
  (deny-all CSP for the API, `nosniff`, `frame-ancestors 'none'`, no-referrer, HSTS over HTTPS, `Cache-Control: no-store`);
  generic error messages (details only in server logs); `/api/health` and `/api/llm/status` require sign-in and never
  expose URLs or configuration; Cypher is always parameterized.
- **Secrets.** Only in `backend/.env` (git-ignored). The git history was scanned and contains no secrets. The browser
  never receives API keys or database URLs.
- **Legacy data.** The pre-accounts *Default project* (graph `<FALKORDB_GRAPH>`) belongs to the command-line owner and is
  not reachable from any account; re-upload those papers into your account.

## Projects

Within an account, papers are organised into **projects** (sidebar switcher, **Projects** page). Each project is its
own FalkorDB graph (`<FALKORDB_GRAPH>__prj_…`) and data folder (`data/projects/<id>/`), with its own investigation
history. The registry graph `<FALKORDB_GRAPH>_registry` holds users, sessions, projects and saved investigations;
saved investigations survive restarts, and runs interrupted by a restart are marked `interrupted`.
FalkorDB Cloud's free tier has 100 MB; a paper uses about 2 MB (set `STORE_PAGES_IN_GRAPH=false` to save a third).

### Evidence rules
- An investigation reads only the chosen paper. Its passages are ranked by relevance to the question; because the user
  chose the paper, its own claims, findings and limitations are always given to the AI, so broad questions
  ("what limitations do the authors acknowledge?") are answered too.
- **Research gaps** are hypotheses from the paper's own limitations and open questions, each with its evidence.
- Reports separate **source-supported findings** (page citations), **AI inferences** (hypotheses) and **open questions**.

## Research investigations

The **Investigate** page turns a research question about one paper into an evidence-backed report written by the AI,
in the user's language, with a live progress bar (graph exploration → AI analysis → citation verification → report).

```
React Investigate page ──POST /api/projects/{id}/investigations──► InvestigationManager (worker pool, per-user limits)
        ▲   poll GET .../investigations/{inv} (progress events)                │
        │                                                                     ▼
        │                                     Investigator (researchmind/agent.py), scoped to one paper
        │                                       ├─ Ollama: retrieval-first grounded report (grounded.py)
        │                                       ├─ Claude: tool-use loop over the graph tools
        │                                       └─ every tool call ──► MCPToolClient ──► MCP server ──► ResearchTools ──► FalkorDB
        └── structured result ◄── build_structured (investigation.py): findings, gaps, limitations,
                                   confidence; every source re-verified in the graph
```

- **AI first.** With `AI_REQUIRED=true` (default) the AI writes every report. If no model is configured the request is
  refused (503 `ai_unavailable`); if the model fails mid-run the investigation fails with a clear, translated message
  instead of silently switching to an extractive report. The offline plan remains for the command line and tests.
- **Graph-grounded.** The AI only sees evidence retrieved from the paper's knowledge graph through the MCP tools
  (`search_evidence`, `get_paper`, `explore_entity`, `compare_claims`, `find_research_gaps`, `get_evidence`). Each `[n]`
  maps to a stored passage (paper id, page, quote); unknown citations are marked `[unverified]`, quotes found in no
  source are flagged, and an answer without a valid citation is rejected.
- **Languages.** Reports are written in the language chosen in Settings (English, Spanish, French, German, Hindi, Tamil,
  Simplified Chinese, Japanese, Arabic). Section headings and citation markers stay in English for verification and
  are shown translated in the UI.
- **Confidence is computed**, not asserted, from verified sources, unverified citations and the AI's own assessment.

### LLM reasoning with Ollama (local)

Investigations need a configured, reachable model (`AI_REQUIRED=true`). For production, `LLM_PROVIDER=anthropic`
with `ANTHROPIC_API_KEY` gives the strongest reports; for local use, Ollama works well with `qwen3:8b`.

Setup on Windows (PowerShell):

```powershell
winget install --id Ollama.Ollama --exact --source winget   # or download from https://ollama.com/download
ollama pull qwen3:8b              # ~5 GB; good multilingual reports. Smaller: qwen3:4b (less accurate)
ollama list                       # confirm the model is installed
```

Then in `backend\.env`:

```
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:8b
OLLAMA_BASE_URL=http://localhost:11434
LLM_TIMEOUT_SECONDS=600
INVESTIGATION_TIMEOUT_SECONDS=900
```

Restart the API. `GET /api/llm/status` (also inside `/api/health` → `config.llm`) reports `ready`, `model_missing` (run the `ollama pull` it suggests), `unreachable` (start the Ollama app) or `not_configured`.

How the Ollama path works (`researchmind/grounded.py`): evidence is retrieved first through the MCP tools from the one chosen paper; the model receives the question, your optional project requirements labelled **[R]** (never treated as evidence) and numbered source excerpts **[S1]…[Sn]** with page numbers; it may call `search_evidence` up to `LLM_MAX_TOOL_ROUNDS` times; every `[S#]` is mapped back to a stored evidence chunk and verified. Unknown source numbers become `[unverified]` and quotations that appear in no source are flagged. An answer with no valid citation, an unreachable server, a missing model or a timeout fail the investigation with a clear message (`AI_REQUIRED=true`).

A new provider is added in `researchmind/llm.py` by implementing `chat()` and `status()` like `OllamaLLM`.

### Demonstrate a complete investigation

1. Start the API and the web app (see **Running**) and **create an account**.
2. **Upload papers** → drop a PDF (samples in `data\papers\`) → Upload → **Analyse this paper**.
3. Pick an example question or type your own → **Investigate**. The progress bar moves through graph exploration,
   AI analysis and citation verification.
4. Review the answer, findings, methods and datasets, candidate gaps (expand *Supporting evidence*), limitations and
   confidence. Click any `[n]` chip for the quote, page, *Paper details* and *Open PDF at page N*.
5. **Export report** downloads the full report, in your language, with numbered page-level sources. Every investigation
   is also saved in **History**.

From the CLI the same agent runs with `python -m researchmind.cli ask "..."` (add `--offline` to skip the LLM).

### UI testing without FalkorDB (mock)

`backend\tests\mock_server.py` runs the real API on port 8001 with the graph, accounts and projects replaced by in-memory fakes (sign up with any address; accounts vanish when it stops). Use it only to exercise the UI:

```powershell
cd backend; .\.venv\Scripts\python.exe tests\mock_server.py
# second terminal
cd frontend; $env:VITE_API_PROXY_TARGET="http://127.0.0.1:8001"; npm run dev -- --port 5174
```
