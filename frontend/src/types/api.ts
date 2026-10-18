// Types mirroring the FastAPI response schemas (backend/app/schemas).

export type PaperStatus = 'processed' | 'failed'
export type UploadStatus = 'processed' | 'duplicate' | 'failed' | 'rejected'

export interface PaperSummary {
  id: string
  title: string | null
  display_title: string
  filename: string | null
  status: PaperStatus
  page_count: number | null
  authors: string[]
  year: number | null
  file_size: number | null
  error: string | null
  error_code: string | null
  updated_at: string | null
}

export interface PaperCounts {
  total: number
  processed: number
  failed: number
}

export interface PaperListResponse {
  papers: PaperSummary[]
  counts: PaperCounts
  total_matching: number
  limit: number
  offset: number
}

export interface EntityRef {
  name: string
  page: number | null
}

export interface KnowledgeSummary {
  extractor: string | null
  methods: EntityRef[]
  datasets: EntityRef[]
  claims: number
  findings: number
  limitations: number
  chunks: number
  sections: string[]
}

export interface PaperDetail extends PaperSummary {
  sha256: string | null
  abstract: string | null
  title_detected: boolean | null
  ingested_at: string | null
  pdf_metadata: Record<string, string>
  knowledge: KnowledgeSummary | null
}

export interface PageText {
  page: number
  text: string
  chars: number
}

export interface PaperDetailResponse {
  paper: PaperDetail
  pages: PageText[]
  pagination: { page: number; page_size: number; total_pages: number }
  text_available: boolean
}

export interface UploadResult {
  filename: string
  status: UploadStatus
  paper_id: string | null
  title: string | null
  page_count: number | null
  message: string
  error_code: string | null
}

export interface UploadResponse {
  results: UploadResult[]
  summary: { received: number; processed: number; duplicate: number; failed: number; rejected: number }
}

export type DatabaseStatus = 'connected' | 'unavailable' | 'not_configured'

export interface LLMStatus {
  provider: 'ollama' | 'anthropic' | 'none' | string
  model: string | null
  status: 'ready' | 'configured' | 'model_missing' | 'unreachable' | 'not_configured' | 'error'
  reachable: boolean | null
  model_available: boolean | null
  message: string
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  backend: { status: 'ok'; version: string; uptime_seconds: number }
  database: { status: DatabaseStatus; latency_ms: number | null; message: string | null }
  config: {
    max_upload_mb: number; max_files_per_upload: number; llm_configured: boolean; ai_required: boolean
    embedding_model: string | null; llm: LLMStatus
  }
  timestamp: string
}

// ---- Accounts (backend/app/schemas/auth.py) ----

export type ThemeSetting = 'system' | 'light' | 'dark'

export interface User {
  id: string
  email: string
  name: string
  theme: ThemeSetting
  language: string
  created_at: string
  is_admin: boolean
}

// ---- Site (backend/app/routes/site.py) ----

export type MetricEvent = 'page_view' | 'signup' | 'upload' | 'investigation'

export interface AdminAnalytics {
  days: number
  totals: Record<MetricEvent, number>
  series: ({ day: string } & Record<MetricEvent, number>)[]
  top_paths: { path: string; views: number }[]
  campaigns: ({ campaign: string } & Record<MetricEvent, number>)[]
}

export interface ContactMessage {
  id: string
  created_at: string
  name: string
  email: string
  topic: string
  message: string
  user_id: string
}

export interface SessionInfo {
  id: string
  created_at: string
  last_seen_at: string
  expires_at: string
  user_agent: string
  current: boolean
}

export interface GraphStats {
  nodes: Record<string, number>
  relationships: number
}

export interface GraphOverview {
  nodes: { id: string; type: 'paper' | 'method' | 'dataset'; label: string }[]
  edges: { id: string; source: string; target: string; type: string; score: number | null }[]
}

export interface Project {
  id: string
  name: string
  description: string
  owner_id: string
  created_at: string
  updated_at: string
  is_default: boolean
  paper_count: number | null
  investigation_count: number | null
}

export interface ApiErrorBody {
  error: { code: string; message: string }
}

// ---- Investigations (backend/app/schemas/investigation.py) ----

export type InvestigationStatus = 'queued' | 'running' | 'completed' | 'failed'
export type InvestigationMode = 'llm' | 'offline'

export interface InvestigationSource {
  n: number
  chunk_id: string
  paper_id: string
  paper_title: string | null
  year: number | null
  page: number | null
  section: string | null
  quote: string
  cited_in_report: boolean
}

export interface InvestigationFinding {
  type: string
  text: string
  paper_id: string
  paper_title: string | null
  year: number | null
  page: number | null
  relevance: number | null
  citations: number[]
}

export interface ComparisonSide {
  text: string
  paper_id: string
  paper_title: string | null
  page: number | null
  citation: number
}

export interface InvestigationComparison {
  kind: 'contradiction' | 'related'
  score: number
  a: ComparisonSide
  b: ComparisonSide
  note: string
}

export interface EntityComparison {
  entity: string
  type: 'method' | 'dataset'
  papers: { paper_id: string; paper_title: string | null; citation: number }[]
}

export interface InvestigationGap {
  id: string
  title: string
  type: string
  rationale: string
  score: number | null
  status: 'candidate'
  evidence: { citation: number; paper_id: string; paper_title: string | null; page: number | null; quote: string }[]
  citations: number[]
  note: string
  support_papers: number
}

export interface InvestigationLimitation {
  text: string
  kind: 'limitation' | 'future_work'
  paper_id: string
  paper_title: string | null
  page: number | null
  citations: number[]
}

export interface InvestigationConfidence {
  level: 'low' | 'moderate' | 'high'
  reasons: string[]
  uncertainties: string[]
  narrative: string | null
}

export interface InvestigationStep {
  tool: string
  args: Record<string, unknown>
  summary: string
  source: string
  ok: boolean
}

export interface InvestigationResultBody {
  mode: InvestigationMode
  /** False when no stored evidence reached the relevance threshold. */
  evidence_found: boolean
  summary: string
  report_markdown: string
  findings: InvestigationFinding[]
  comparisons: InvestigationComparison[]
  method_comparison: EntityComparison[]
  gaps: InvestigationGap[]
  inferences: { text: string; citations: number[] }[]
  open_questions: string[]
  limitations: InvestigationLimitation[]
  confidence: InvestigationConfidence
  sources: InvestigationSource[]
  papers: { paper_id: string; title: string | null; year: number | null; sources: number }[]
  steps: InvestigationStep[]
  warnings: string[]
}

export interface ProgressEvent {
  type: string
  message: string
  tool: string | null
  at: number
}

export interface Investigation {
  id: string
  project_id: string
  question: string
  status: InvestigationStatus
  mode: InvestigationMode | null
  llm_configured: boolean
  provider: string | null
  model: string | null
  requirements: string | null
  /** The one paper the investigation analysed. */
  paper_ids: string[] | null
  paper_title: string | null
  language: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_seconds: number | null
  progress: ProgressEvent[]
  result: InvestigationResultBody | null
  error: { code: string; message: string } | null
}

export interface InvestigationSummary {
  id: string
  project_id: string
  question: string
  status: InvestigationStatus
  mode: InvestigationMode | null
  paper_title: string | null
  created_at: string
  duration_seconds: number | null
}
