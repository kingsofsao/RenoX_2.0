import { useEffect, useState } from 'react'
import { Check, Copy } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import { cx } from './ui'

/** Copies text to the clipboard and confirms with a short "Copied" state (announced to screen readers). */
export function CopyButton({ text, label, className, compact }: { text: string | (() => string); label?: string; className?: string; compact?: boolean }) {
  const { t } = useI18n()
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle')
  useEffect(() => {
    if (state === 'idle') return
    const timer = window.setTimeout(() => setState('idle'), 1800)
    return () => window.clearTimeout(timer)
  }, [state])

  const copy = async () => {
    const value = typeof text === 'function' ? text() : text
    try {
      await navigator.clipboard.writeText(value)
      setState('copied')
    } catch {
      setState('failed')
    }
  }
  const caption = state === 'copied' ? t('copy.done') : state === 'failed' ? t('copy.failed') : (label ?? t('copy.label'))
  return (
    <button type="button" onClick={() => void copy()} title={caption} aria-label={caption}
      className={cx('inline-flex items-center gap-1.5 rounded-md text-xs font-medium transition-all duration-150 active:scale-95',
        compact ? 'p-1.5' : 'px-2 py-1.5', state === 'copied' ? 'text-ok-fg' : 'text-fg-muted hover:bg-surface-3 hover:text-fg', className)}>
      {state === 'copied' ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      {!compact && <span>{caption}</span>}
      <span className="sr-only" aria-live="polite">{state === 'copied' ? t('copy.done') : ''}</span>
    </button>
  )
}
