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

export interface HealthResponse {
  status: 'ok' | 'degraded'
  backend: { status: 'ok'; version: string; uptime_seconds: number }
  database: { status: DatabaseStatus; graph: string; latency_ms: number | null; message: string | null }
  config: { max_upload_mb: number; max_files_per_upload: number; llm_configured: boolean; embedding_model: string | null }
  timestamp: string
}

export interface GraphStats {
  nodes: Record<string, number>
  relationships: number
}

export interface GraphOverview {
  nodes: { id: string; type: 'paper' | 'method' | 'dataset'; label: string }[]
  edges: { id: string; source: string; target: string; type: string; score: number | null }[]
}

export interface ApiErrorBody {
  error: { code: string; message: string }
}
