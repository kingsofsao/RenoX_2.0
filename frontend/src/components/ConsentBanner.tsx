import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Cookie } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import { CONSENT_EVENT, getConsent, setConsent } from '../services/analytics'
import { Button } from './ui'

/** Re-open the banner (footer "Cookie settings" link and Settings page). */
export const OPEN_CONSENT_EVENT = 'researchmind:open-consent'
export function openCookieSettings(): void {
  window.dispatchEvent(new Event(OPEN_CONSENT_EVENT))
}

/**
 * Simple cookie notice. Essential cookies (sign-in session and security token) are always on and need no
 * consent; the only optional item is anonymous usage statistics, which stay off unless the visitor allows them.
 */
export function ConsentBanner() {
  const { t } = useI18n()
  const [open, setOpen] = useState(() => getConsent() === null)

  useEffect(() => {
    const show = () => setOpen(true)
    const hide = () => setOpen(false)
    window.addEventListener(OPEN_CONSENT_EVENT, show)
    window.addEventListener(CONSENT_EVENT, hide)
    return () => { window.removeEventListener(OPEN_CONSENT_EVENT, show); window.removeEventListener(CONSENT_EVENT, hide) }
  }, [])

  if (!open) return null
  return (
    <section role="region" aria-label={t('consent.title')}
      className="fixed inset-x-3 bottom-3 z-50 animate-fade-up rounded-xl border border-line bg-surface p-4 shadow-pop sm:inset-x-auto sm:start-4 sm:bottom-4 sm:max-w-md print:hidden">
      <div className="flex gap-3">
        <Cookie className="mt-0.5 h-5 w-5 shrink-0 text-brand" aria-hidden />
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-fg">{t('consent.title')}</h2>
          <p className="mt-1 text-sm leading-relaxed text-fg-muted">
            {t('consent.text')} <Link to="/privacy#cookies" className="font-medium text-brand underline-offset-2 hover:underline">{t('consent.more')}</Link>
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" onClick={() => setConsent('granted')}>{t('consent.allow')}</Button>
            <Button size="sm" variant="secondary" onClick={() => setConsent('denied')}>{t('consent.deny')}</Button>
          </div>
        </div>
      </div>
    </section>
  )
}
