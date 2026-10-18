// Presentational building blocks shared across pages. Colours come only from the theme tokens in index.css.
import { forwardRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'
import { Link, type LinkProps } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, CopyCheck, Info, Loader2, XCircle } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import type { PaperStatus, UploadStatus } from '../types/api'

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

// ------------------------------------------------------------------ layout

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('rounded-xl border border-line bg-surface shadow-card', className)}>{children}</div>
}

export function CardHeader({ title, subtitle, action }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
      <div className="min-w-0">
        <h2 className="text-sm font-semibold text-fg">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-fg-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function PageHeader({ title, description, actions, eyebrow }: { title: string; description?: string; actions?: ReactNode; eyebrow?: string }) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-brand">{eyebrow}</p>}
        <h1 className="text-2xl font-semibold tracking-tight text-fg sm:text-[28px]">{title}</h1>
        {description && <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

// ------------------------------------------------------------------ feedback

export function LoadingBlock({ label, rows = 3 }: { label?: string; rows?: number }) {
  const { t } = useI18n()
  return (
    <div className="space-y-3 p-5" role="status" aria-label={label ?? t('common.loading')}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton h-4" style={{ width: `${92 - i * 14}%` }} />
      ))}
      <span className="sr-only">{label ?? t('common.loading')}</span>
    </div>
  )
}

type Tone = 'error' | 'warning' | 'info' | 'success'
const toneStyles: Record<Tone, string> = {
  error: 'border-bad/25 bg-bad-soft text-bad-fg',
  warning: 'border-warn/25 bg-warn-soft text-warn-fg',
  info: 'border-brand/20 bg-brand-soft text-brand-fg',
  success: 'border-ok/25 bg-ok-soft text-ok-fg',
}
const toneIcons: Record<Tone, ReactNode> = {
  error: <XCircle className="h-4 w-4 shrink-0" />,
  warning: <AlertTriangle className="h-4 w-4 shrink-0" />,
  info: <Info className="h-4 w-4 shrink-0" />,
  success: <CheckCircle2 className="h-4 w-4 shrink-0" />,
}

export function Alert({ tone = 'info', title, children, action, className }: {
  tone?: Tone; title?: string; children?: ReactNode; action?: ReactNode; className?: string
}) {
  return (
    <div role={tone === 'error' ? 'alert' : 'status'}
      className={cx('flex animate-fade-in gap-3 rounded-lg border px-4 py-3 text-sm', toneStyles[tone], className)}>
      <div className="mt-0.5">{toneIcons[tone]}</div>
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cx(title && 'mt-0.5', 'break-words opacity-90')}>{children}</div>}
      </div>
      {action && <div className="shrink-0 self-center">{action}</div>}
    </div>
  )
}

export function EmptyState({ icon, title, description, action }: { icon: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex animate-fade-up flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-4 rounded-2xl bg-brand-soft p-3.5 text-brand">{icon}</div>
      <p className="font-medium text-fg">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-fg-muted">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ProgressBar({ value, indeterminate, label, className }: { value?: number; indeterminate?: boolean; label?: string; className?: string }) {
  const pct = Math.max(0, Math.min(100, value ?? 0))
  return (
    <div className={cx('h-1.5 overflow-hidden rounded-full bg-surface-3', className)} role="progressbar"
      aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={indeterminate ? undefined : Math.round(pct)}>
      {indeterminate
        ? <div className="h-full w-1/3 animate-indeterminate rounded-full bg-brand" />
        : <div className="h-full rounded-full bg-brand transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />}
    </div>
  )
}

const statusStyles: Record<PaperStatus | UploadStatus, string> = {
  processed: 'bg-ok-soft text-ok-fg ring-ok/25',
  duplicate: 'bg-brand-soft text-brand-fg ring-brand/25',
  failed: 'bg-bad-soft text-bad-fg ring-bad/25',
  rejected: 'bg-warn-soft text-warn-fg ring-warn/25',
}
const statusIcons: Record<PaperStatus | UploadStatus, ReactNode> = {
  processed: <CheckCircle2 className="h-3.5 w-3.5" />,
  duplicate: <CopyCheck className="h-3.5 w-3.5" />,
  failed: <XCircle className="h-3.5 w-3.5" />,
  rejected: <AlertTriangle className="h-3.5 w-3.5" />,
}

export function StatusBadge({ status }: { status: PaperStatus | UploadStatus }) {
  const { t } = useI18n()
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset', statusStyles[status])}>
      {statusIcons[status]}
      {t(`status.${status}`)}
    </span>
  )
}

export function Badge({ children, tone = 'neutral', className, title }: {
  children: ReactNode; tone?: 'neutral' | 'brand' | 'ok' | 'warn' | 'bad' | 'accent'; className?: string; title?: string
}) {
  const tones = {
    neutral: 'bg-surface-3 text-fg-muted',
    brand: 'bg-brand-soft text-brand-fg',
    ok: 'bg-ok-soft text-ok-fg',
    warn: 'bg-warn-soft text-warn-fg',
    bad: 'bg-bad-soft text-bad-fg',
    accent: 'bg-accent-soft text-accent-fg',
  }
  return <span title={title} className={cx('inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium', tones[tone], className)}>{children}</span>
}

// ------------------------------------------------------------------ buttons

type Variant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'dark'
type Size = 'sm' | 'md' | 'lg'

const variantStyles: Record<Variant, string> = {
  primary: 'bg-brand-solid text-white shadow-sm hover:bg-brand-solid-hover hover:shadow-md hover:-translate-y-px disabled:bg-brand-solid/45 disabled:shadow-none disabled:translate-y-0',
  secondary: 'bg-surface text-fg ring-1 ring-inset ring-line-strong hover:bg-surface-2 hover:ring-fg-subtle disabled:text-fg-subtle',
  danger: 'bg-surface text-bad-fg ring-1 ring-inset ring-bad/35 hover:bg-bad-soft disabled:opacity-50',
  ghost: 'text-fg-muted hover:bg-surface-3 hover:text-fg disabled:opacity-40',
  dark: 'bg-fg text-canvas hover:opacity-90 hover:-translate-y-px disabled:opacity-40',
}
const sizeStyles: Record<Size, string> = {
  sm: 'gap-1.5 rounded-md px-2.5 py-1.5 text-xs',
  md: 'gap-2 rounded-lg px-3.5 py-2 text-sm',
  lg: 'gap-2 rounded-lg px-5 py-2.5 text-[15px]',
}

export function buttonClass(variant: Variant = 'primary', size: Size = 'md', className?: string): string {
  return cx(
    'inline-flex select-none items-center justify-center font-medium whitespace-nowrap',
    'transition-[background-color,color,box-shadow,transform,opacity] duration-150 ease-out active:scale-[0.97] active:translate-y-0',
    'focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:active:scale-100',
    variantStyles[variant], sizeStyles[size], className,
  )
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { children, variant = 'primary', size = 'md', loading, disabled, type = 'button', className, ...rest }, ref,
) {
  return (
    <button ref={ref} type={type} disabled={disabled || loading} aria-busy={loading || undefined}
      className={buttonClass(variant, size, className)} {...rest}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  )
})

/** A router link styled as a button. */
export function ButtonLink({ variant = 'primary', size = 'md', className, ...props }: LinkProps & { variant?: Variant; size?: Size }) {
  return <Link className={buttonClass(variant, size, className)} {...props} />
}

// ------------------------------------------------------------------ form controls

const control = cx(
  'w-full rounded-lg border border-line-strong bg-surface px-3 py-2 text-sm text-fg shadow-sm transition-colors',
  'placeholder:text-fg-subtle hover:border-fg-subtle focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/20',
  'disabled:cursor-not-allowed disabled:bg-surface-2 disabled:text-fg-subtle aria-invalid:border-bad aria-invalid:focus:ring-bad/20',
)

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cx(control, className)} {...props} />
})

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cx(control, 'resize-y leading-relaxed', className)} {...props} />
})

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, ...props }, ref) {
  return <select ref={ref} className={cx(control, 'cursor-pointer pe-8', className)} {...props} />
})

export function Field({ label, htmlFor, hint, error, children, action }: {
  label: string; htmlFor: string; hint?: ReactNode; error?: string | null; children: ReactNode; action?: ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={htmlFor} className="text-sm font-medium text-fg">{label}</label>
        {action}
      </div>
      {children}
      {error ? <p className="text-xs text-bad-fg" role="alert">{error}</p> : hint ? <p className="text-xs text-fg-subtle">{hint}</p> : null}
    </div>
  )
}

// ------------------------------------------------------------------ brand

/** ResearchMind mark: a knowledge-graph node cluster in the brand blue. */
export function Logo({ className, mono }: { className?: string; mono?: boolean }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill={mono ? 'currentColor' : '#1c69d4'} />
      <path d="M10.5 11.5 21.5 9.5M10.5 11.5l5.5 11M21.5 9.5l-5.5 13" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" opacity="0.9" />
      <circle cx="10.5" cy="11.5" r="3" fill="#fff" />
      <circle cx="21.5" cy="9.5" r="3" fill="#fff" />
      <circle cx="16" cy="22.5" r="3" fill="#0b0d11" stroke="#fff" strokeWidth="1.6" />
    </svg>
  )
}
