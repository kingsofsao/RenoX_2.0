import { useEffect, useState } from 'react'
import { ArrowUp } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import { cx } from './ui'

function useScroll() {
  const [state, setState] = useState({ y: 0, progress: 0, long: false })
  useEffect(() => {
    let frame = 0
    const measure = () => {
      frame = 0
      const doc = document.documentElement
      const max = doc.scrollHeight - window.innerHeight
      setState({ y: window.scrollY, progress: max > 0 ? Math.min(1, window.scrollY / max) : 0, long: max > window.innerHeight * 0.75 })
    }
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(measure) }
    measure()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    const observer = new ResizeObserver(onScroll)
    observer.observe(document.body)
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      observer.disconnect()
      if (frame) cancelAnimationFrame(frame)
    }
  }, [])
  return state
}

/** A 2px reading-progress line at the very top, only on pages long enough to need it. */
export function ScrollProgress() {
  const { long, progress } = useScroll()
  if (!long) return null
  return (
    <div className="pointer-events-none fixed inset-x-0 top-0 z-[70] h-0.5 print:hidden" aria-hidden>
      <div className="h-full origin-left bg-brand transition-transform duration-100 ease-out rtl:origin-right" style={{ transform: `scaleX(${progress})` }} />
    </div>
  )
}

/** Appears after scrolling down; sits above the contact button. */
export function BackToTop() {
  const { t } = useI18n()
  const { y } = useScroll()
  const visible = y > 700
  return (
    <button type="button" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label={t('common.backToTop')}
      title={t('common.backToTop')} tabIndex={visible ? 0 : -1} aria-hidden={!visible}
      className={cx('fixed bottom-20 end-4 z-40 flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-surface text-fg-muted shadow-pop transition-all duration-200 hover:text-fg active:scale-95 sm:end-6 print:hidden',
        visible ? 'translate-y-0 opacity-100' : 'pointer-events-none translate-y-2 opacity-0')}>
      <ArrowUp className="h-4 w-4" />
    </button>
  )
}
