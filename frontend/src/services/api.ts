import axios, { AxiosError } from 'axios'
import type {
  ApiErrorBody,
  GraphOverview,
  GraphStats,
  HealthResponse,
  PaperDetailResponse,
  PaperListResponse,
  PaperStatus,
  UploadResponse,
} from '../types/api'

// Empty base URL = same origin; the Vite dev/preview server proxies /api to FastAPI.
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''

export const http = axios.create({ baseURL: API_BASE_URL, timeout: 30_000 })

/** Error with a user-presentable message, normalized from any axios failure. */
export class ApiError extends Error {
  readonly status: number | null
  readonly code: string

  constructor(message: string, status: number | null, code: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err
  if (axios.isAxiosError(err)) {
    const e = err as AxiosError<ApiErrorBody>
    const body = e.response?.data
    if (body && typeof body === 'object' && 'error' in body && body.error?.message) {
      return new ApiError(body.error.message, e.response?.status ?? null, body.error.code)
    }
    if (e.response) {
      return new ApiError(`Request failed (HTTP ${e.response.status}).`, e.response.status, 'http_error')
    }
    if (e.code === 'ECONNABORTED') return new ApiError('The request timed out.', null, 'timeout')
    return new ApiError('Cannot reach the ResearchMind API. Is the backend running on port 8000?', null, 'network_error')
  }
  return new ApiError(err instanceof Error ? err.message : 'Unexpected error.', null, 'unknown')
}

async function call<T>(fn: () => Promise<{ data: T }>): Promise<T> {
  try {
    return (await fn()).data
  } catch (err) {
    throw toApiError(err)
  }
}

export const api = {
  health: () => call(() => http.get<HealthResponse>('/api/health', { timeout: 10_000 })),

  listPapers: (params: { status?: PaperStatus; search?: string; limit?: number; offset?: number } = {}) =>
    call(() => http.get<PaperListResponse>('/api/papers', { params })),

  getPaper: (id: string, page = 1, pageSize = 1) =>
    call(() => http.get<PaperDetailResponse>(`/api/papers/${encodeURIComponent(id)}`, { params: { page, page_size: pageSize } })),

  deletePaper: (id: string) => call(() => http.delete<void>(`/api/papers/${encodeURIComponent(id)}`)),

  paperFileUrl: (id: string) => `${API_BASE_URL}/api/papers/${encodeURIComponent(id)}/file`,

  /** Upload PDFs. `onProgress` reports the byte transfer (0-100); server processing follows. */
  uploadPapers: (files: File[], onProgress?: (percent: number) => void) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f, f.name))
    return call(() =>
      http.post<UploadResponse>('/api/papers/upload', form, {
        timeout: 10 * 60_000, // parsing + graph writes for large PDFs can take a while
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
        },
      }),
    )
  },

  graphStats: () => call(() => http.get<GraphStats>('/api/graph/stats')),
  graphOverview: (limit = 60) => call(() => http.get<GraphOverview>('/api/graph/overview', { params: { limit } })),
}
