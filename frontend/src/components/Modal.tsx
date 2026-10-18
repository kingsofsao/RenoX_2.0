// Accessible dialog: focus moves in and is trapped, Escape and the backdrop close it, focus returns afterwards.
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, X } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import { Button, cx } from './ui'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function Modal({ open, onClose, title, description, children, footer, size = 'md', closeLabel }: {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
  closeLabel?: string
}) {
  const { t } = useI18n()
  const panel = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const descId = useId()

  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    const node = panel.current
    const first = node?.querySelector<HTMLElement>('[data-autofocus]') ?? node?.querySelector<HTMLElement>(FOCUSABLE)
    first?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); return }
      if (e.key !== 'Tab' || !node) return
      const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null)
      if (!items.length) return
      const [head, tail] = [items[0], items[items.length - 1]]
      if (e.shiftKey && document.activeElement === head) { e.preventDefault(); tail.focus() }
      else if (!e.shiftKey && document.activeElement === tail) { e.preventDefault(); head.focus() }
    }
    document.addEventListener('keydown', onKey, true)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.body.style.overflow = overflow
      previous?.focus?.()
    }
  }, [open, onClose])

  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-end justify-center p-4 sm:items-center print:hidden">
      <div className="absolute inset-0 animate-fade-in bg-black/50 backdrop-blur-[2px]" onClick={onClose} aria-hidden />
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={description ? descId : undefined}
        className={cx('relative w-full animate-scale-in rounded-2xl border border-line bg-surface shadow-pop',
          size === 'sm' ? 'max-w-md' : size === 'lg' ? 'max-w-2xl' : 'max-w-lg')}>
        <div className="flex items-start justify-between gap-4 px-6 pt-5">
          <div className="min-w-0">
            <h2 id={titleId} className="text-base font-semibold text-fg">{title}</h2>
            {description && <p id={descId} className="mt-1 text-sm text-fg-muted">{description}</p>}
          </div>
          <button type="button" onClick={onClose} aria-label={closeLabel ?? t('common.close')}
            className="-me-2 rounded-md p-1.5 text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg">
            <X className="h-4 w-4" />
          </button>
        </div>
        {children && <div className="px-6 pt-4">{children}</div>}
        {footer ? <div className="flex flex-wrap justify-end gap-2 px-6 pb-5 pt-5">{footer}</div> : !children && <div className="pb-5" />}
      </div>
    </div>,
    document.body,
  )
}

/** "Are you sure?" for destructive actions. `children` can hold extra confirmation fields. */
export function ConfirmDialog({ open, onCancel, onConfirm, title, description, confirmLabel, busy, disabled, children, error }: {
  open: boolean
  onCancel: () => void
  onConfirm: () => void
  title: string
  description: ReactNode
  confirmLabel: string
  busy?: boolean
  disabled?: boolean
  children?: ReactNode
  error?: string | null
}) {
  const { t } = useI18n()
  return (
    <Modal open={open} onClose={busy ? () => {} : onCancel} size="sm"
      title={<span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-bad" />{title}</span>}
      description={description}
      footer={<>
        <Button variant="ghost" onClick={onCancel} disabled={busy}>{t('common.cancel')}</Button>
        <Button variant="danger" onClick={onConfirm} loading={busy} disabled={disabled} className="!bg-bad !text-white !ring-0 hover:!opacity-90">
          {confirmLabel}
        </Button>
      </>}>
      {(children || error) && (
        <div className="space-y-3">
          {children}
          {error && <p className="text-sm text-bad-fg" role="alert">{error}</p>}
        </div>
      )}
    </Modal>
  )
}
