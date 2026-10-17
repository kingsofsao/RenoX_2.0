import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type {
  ApiErrorBody,
  GraphOverview,
  GraphStats,
  HealthResponse,
  Investigation,
  InvestigationSummary,
  PaperDetailResponse,
  Project,
  PaperListResponse,
  PaperStatus,
  SessionInfo,
  ThemeSetting,
  UploadResponse,
  User,
} from '../types/api'

// Empty base URL = same origin; the Vite dev/preview server (or the production reverse proxy) serves /api.
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''

// withCredentials: the session lives in an httpOnly cookie the page can never read.
export const http = axios.create({ baseURL: API_BASE_URL, timeout: 30_000, withCredentials: true })

const SAFE_METHODS = new Set(['get', 'head', 'options'])
const CSRF_COOKIES = ['__Host-rm_csrf', 'rm_csrf']

/** The double-submit CSRF token the API set in a readable cookie. */
export function csrfToken(): string | null {
  if (typeof document === 'undefined') return null
  for (const part of document.cookie.split(';')) {
    const [k, ...v] = part.trim().split('=')
    if (CSRF_COOKIES.includes(k)) return decodeURIComponent(v.join('='))
  }
  return null
}

http.interceptors.request.use((config) => {
  if (!SAFE_METHODS.has((config.method ?? 'get').toLowerCase())) {
    const token = csrfToken()
    if (token) config.headers.set('X-CSRF-Token', token)
  }
  return config
})

/** Fired when the server says the session is gone; the auth provider signs the UI out. */
export const UNAUTHORIZED_EVENT = 'researchmind:unauthorized'

http.interceptors.response.use(undefined, async (error: AxiosError<ApiErrorBody>) => {
  const code = error.response?.data?.error?.code
  const config = error.config as (InternalAxiosRequestConfig & { _csrfRetry?: boolean }) | undefined
  // A missing/expired CSRF cookie: fetch a fresh one and retry the request once.
  if (error.response?.status === 403 && code === 'csrf_failed' && config && !config._csrfRetry) {
    config._csrfRetry = true
    await http.get('/api/auth/csrf')
    return http.request(config)
  }
  if (error.response?.status === 401 && code === 'auth_required' && typeof window !== 'undefined') {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
  }
  return Promise.reject(error)
})

// Active project. Every paper, graph and investigation call is scoped to it via the URL; the
// backend checks that the signed-in user owns it and resolves the project's own graph.
let activeProjectId = ''
export function setActiveProject(id: string) { activeProjectId = id }
export function getActiveProject(): string { return activeProjectId }
const scoped = (path: string) => `/api/projects/${encodeURIComponent(activeProjectId)}${path}`

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
    return new ApiError('Cannot reach the ResearchMind service. Check your connection and try again.', null, 'network_error')
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
  // ---- account ----
  csrf: () => call(() => http.get<void>('/api/auth/csrf')),
  me: () => call(() => http.get<User>('/api/auth/me')),
  signIn: (email: string, password: string, remember: boolean) =>
    call(() => http.post<User>('/api/auth/login', { email, password, remember })),
  signUp: (body: { email: string; password: string; name: string; language: string; theme: ThemeSetting }) =>
    call(() => http.post<User>('/api/auth/signup', body)),
  signOut: () => call(() => http.post<void>('/api/auth/logout')),
  updateProfile: (body: { name?: string; language?: string; theme?: ThemeSetting }) =>
    call(() => http.patch<User>('/api/auth/me', body)),
  changePassword: (currentPassword: string, newPassword: string) =>
    call(() => http.post<void>('/api/auth/password', { current_password: currentPassword, new_password: newPassword })),
  listSessions: () => call(() => http.get<{ sessions: SessionInfo[] }>('/api/auth/sessions')),
  signOutOtherSessions: () => call(() => http.delete<void>('/api/auth/sessions')),
  deleteAccount: (password: string) => call(() => http.delete<void>('/api/auth/me', { data: { password } })),

  // ---- service ----
  health: () => call(() => http.get<HealthResponse>('/api/health', { timeout: 20_000 })),

  // ---- papers ----
  listPapers: (params: { status?: PaperStatus; search?: string; limit?: number; offset?: number } = {}) =>
    call(() => http.get<PaperListResponse>(scoped('/papers'), { params })),

  getPaper: (id: string, page = 1, pageSize = 1) =>
    call(() => http.get<PaperDetailResponse>(scoped(`/papers/${encodeURIComponent(id)}`), { params: { page, page_size: pageSize } })),

  deletePaper: (id: string) => call(() => http.delete<void>(scoped(`/papers/${encodeURIComponent(id)}`))),

  paperFileUrl: (id: string) => `${API_BASE_URL}${scoped(`/papers/${encodeURIComponent(id)}/file`)}`,

  /** Upload PDFs. `onProgress` reports the byte transfer (0-100); server processing follows. */
  uploadPapers: (files: File[], onProgress?: (percent: number) => void) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f, f.name))
    return call(() =>
      http.post<UploadResponse>(scoped('/papers/upload'), form, {
        timeout: 10 * 60_000, // parsing + graph writes for large PDFs can take a while
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
        },
      }),
    )
  },

  graphStats: () => call(() => http.get<GraphStats>(scoped('/graph/stats'))),
  graphOverview: (limit = 60) => call(() => http.get<GraphOverview>(scoped('/graph/overview'), { params: { limit } })),

  // ---- investigations: always exactly one paper ----
  /** Start an AI investigation of one paper in the background (202); poll `getInvestigation` for progress. */
  startInvestigation: (question: string, paperId: string, opts: { requirements?: string; language?: string } = {}) =>
    call(() => http.post<Investigation>(scoped('/investigations'), {
      question, paper_id: paperId, wait: false, requirements: opts.requirements || null, language: opts.language || null,
    })),
  getInvestigation: (id: string) =>
    call(() => http.get<Investigation>(scoped(`/investigations/${encodeURIComponent(id)}`), { timeout: 30_000 })),
  listInvestigations: (limit = 10, offset = 0) =>
    call(() => http.get<{ investigations: InvestigationSummary[]; total: number }>(scoped('/investigations'), { params: { limit, offset } })),
  deleteInvestigation: (id: string) => call(() => http.delete<void>(scoped(`/investigations/${encodeURIComponent(id)}`))),

  // ---- projects ----
  listProjects: () => call(() => http.get<{ projects: Project[] }>('/api/projects')),
  createProject: (name: string, description = '') => call(() => http.post<Project>('/api/projects', { name, description })),
  updateProject: (id: string, body: { name?: string; description?: string }) =>
    call(() => http.patch<Project>(`/api/projects/${encodeURIComponent(id)}`, body)),
  deleteProject: (id: string, confirmName: string) =>
    call(() => http.delete<void>(`/api/projects/${encodeURIComponent(id)}`, { data: { confirm_name: confirmName } })),
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('Aborted', 'AbortError')) }, { once: true })
  })

/**
 * Poll an investigation until it completes or fails, reporting every snapshot.
 * Timeouts and network errors are retried (a local LLM can keep the backend busy for a while);
 * `onStall` reports consecutive failures so the UI can say it is still waiting.
 */
export async function pollInvestigation(
  id: string,
  onUpdate: (inv: Investigation) => void,
  { intervalMs = 1500, signal, maxErrors = 40, onStall }:
    { intervalMs?: number; signal?: AbortSignal; maxErrors?: number; onStall?: (failures: number) => void } = {},
): Promise<Investigation> {
  let errors = 0
  for (;;) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    try {
      const inv = await api.getInvestigation(id)
      errors = 0
      onStall?.(0)
      onUpdate(inv)
      if (inv.status === 'completed' || inv.status === 'failed') return inv
    } catch (err) {
      const e = toApiError(err)
      if (e.status === 404 || e.status === 401 || ++errors >= maxErrors) throw e
      onStall?.(errors)
    }
    await sleep(intervalMs, signal)
  }
}
