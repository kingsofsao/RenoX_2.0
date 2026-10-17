// User-facing error text in the UI language, from the API's stable error codes.
import type { MessageKey } from '../i18n/en'
import { ApiError, toApiError } from './api'

const BY_CODE: Record<string, MessageKey> = {
  network_error: 'error.network',
  timeout: 'error.timeout',
  rate_limited: 'error.rateLimited',
  auth_required: 'error.authRequired',
  csrf_failed: 'error.csrf',
  cross_site_request: 'error.csrf',
  database_unavailable: 'error.unavailable',
  ai_unavailable: 'error.ai',
  busy: 'error.busy',
  paper_not_found: 'error.paperNotFound',
  project_not_found: 'error.projectNotFound',
  internal_error: 'error.internal',
  investigation_failed: 'error.internal',
  interrupted: 'error.interrupted',
  too_large: 'error.tooLarge',
}

/**
 * Translate an error. Codes the UI knows are shown in the user's language; anything else
 * (for example a validation message about a specific field) falls back to the server's text.
 */
export function errorText(t: (k: MessageKey) => string, err: unknown): string {
  const e: ApiError = toApiError(err)
  const key = BY_CODE[e.code]
  return key ? t(key) : e.message
}
