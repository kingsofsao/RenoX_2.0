// Privacy-first usage statistics. Nothing is sent until the visitor allows it in the cookie banner.
// Events go to our own API (no third parties), carry no user id, and the server stores daily counts only.
import { api } from './api'

export type Consent = 'granted' | 'denied' | null
export type AnalyticsEventName = 'page_view' | 'signup' | 'upload' | 'investigation'

const CONSENT_KEY = 'researchmind.consent'
const UTM_KEY = 'researchmind.utm'
export const CONSENT_EVENT = 'researchmind:consent'
const UTM_FIELDS = ['utm_source', 'utm_medium', 'utm_campaign'] as const
type Utm = Partial<Record<(typeof UTM_FIELDS)[number], string>>

export function getConsent(): Consent {
  try {
    const v = localStorage.getItem(CONSENT_KEY)
    return v === 'granted' || v === 'denied' ? v : null
  } catch {
    return null
  }
}

export function setConsent(value: 'granted' | 'denied'): void {
  try { localStorage.setItem(CONSENT_KEY, value) } catch { /* storage unavailable: ask again next visit */ }
  window.dispatchEvent(new CustomEvent(CONSENT_EVENT, { detail: value }))
}

const clean = (v: string | null) => (v ?? '').replace(/[^A-Za-z0-9_\-. ]/g, '').slice(0, 80)

/** Remember the campaign a visitor arrived from (first touch, for this browser tab only). */
export function captureUtm(search: string): void {
  const params = new URLSearchParams(search)
  if (!UTM_FIELDS.some((f) => params.get(f))) return
  try {
    if (sessionStorage.getItem(UTM_KEY)) return
    const utm: Utm = {}
    for (const f of UTM_FIELDS) if (params.get(f)) utm[f] = clean(params.get(f))
    sessionStorage.setItem(UTM_KEY, JSON.stringify(utm))
  } catch { /* storage unavailable */ }
}

function utm(): Utm {
  try { return JSON.parse(sessionStorage.getItem(UTM_KEY) ?? '{}') as Utm } catch { return {} }
}

/** Page paths without ids, so no counter can point at a specific paper, project or investigation. */
export function normalizePath(pathname: string): string {
  return pathname.replace(/\/(p_[0-9a-f]{12}|inv_[0-9a-f]{12}|prj_[0-9a-f]{10})/g, (_, id: string) => `/:${id.split('_')[0]}`).slice(0, 200) || '/'
}

export function track(name: AnalyticsEventName, pathname = window.location.pathname): void {
  if (getConsent() !== 'granted') return
  api.analyticsEvent({ name, path: normalizePath(pathname), ...utm() }).catch(() => { /* statistics never break the app */ })
}
