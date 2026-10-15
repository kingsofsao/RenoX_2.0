// Small presentational building blocks shared across pages.
import type { ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, CopyCheck, Info, Loader2, XCircle } from 'lucide-react'
import type { PaperStatus, UploadStatus } from '../types/api'

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('rounded-xl border border-slate-200 bg-white shadow-sm', className)}>{children}</div>
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-slate-500">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}

export function Spinner({ label, className }: { label?: string; className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-2 text-sm text-slate-500', className)}>
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      {label}
    </span>
  )
}

export function LoadingBlock({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center justify-center py-16">
      <Spinner label={label} />
    </div>
  )
}

type Tone = 'error' | 'warning' | 'info' | 'success'
const toneStyles: Record<Tone, string> = {
  error: 'border-red-200 bg-red-50 text-red-800',
  warning: 'border-amber-200 bg-amber-50 text-amber-900',
  info: 'border-sky-200 bg-sky-50 text-sky-900',
  success: 'border-emerald-200 bg-emerald-50 text-emerald-900',
}
const toneIcons: Record<Tone, ReactNode> = {
  error: <XCircle className="h-4 w-4 shrink-0" />,
  warning: <AlertTriangle className="h-4 w-4 shrink-0" />,
  info: <Info className="h-4 w-4 shrink-0" />,
  success: <CheckCircle2 className="h-4 w-4 shrink-0" />,
}

export function Alert({ tone = 'info', title, children, action }: { tone?: Tone; title?: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div role={tone === 'error' ? 'alert' : 'status'} className={cx('flex gap-3 rounded-lg border px-4 py-3 text-sm', toneStyles[tone])}>
      <div className="mt-0.5">{toneIcons[tone]}</div>
      <div className="min-w-0 flex-1">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cx(title && 'mt-0.5', 'break-words opacity-90')}>{children}</div>}
      </div>
      {action}
    </div>
  )
}

export function EmptyState({ icon, title, description, action }: { icon: ReactNode; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      <div className="mb-3 rounded-full bg-indigo-50 p-3 text-indigo-600">{icon}</div>
      <p className="font-medium text-slate-900">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-slate-500">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

const statusStyles: Record<PaperStatus | UploadStatus, string> = {
  processed: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  duplicate: 'bg-sky-50 text-sky-700 ring-sky-600/20',
  failed: 'bg-red-50 text-red-700 ring-red-600/20',
  rejected: 'bg-amber-50 text-amber-800 ring-amber-600/20',
}
const statusIcons: Record<PaperStatus | UploadStatus, ReactNode> = {
  processed: <CheckCircle2 className="h-3.5 w-3.5" />,
  duplicate: <CopyCheck className="h-3.5 w-3.5" />,
  failed: <XCircle className="h-3.5 w-3.5" />,
  rejected: <AlertTriangle className="h-3.5 w-3.5" />,
}

export function StatusBadge({ status }: { status: PaperStatus | UploadStatus }) {
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-inset', statusStyles[status])}>
      {statusIcons[status]}
      {status}
    </span>
  )
}

export function Button({
  children, onClick, variant = 'primary', disabled, type = 'button', className, title,
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  disabled?: boolean
  type?: 'button' | 'submit'
  className?: string
  title?: string
}) {
  const styles = {
    primary: 'bg-indigo-600 text-white hover:bg-indigo-500 focus-visible:outline-indigo-600 disabled:bg-indigo-300',
    secondary: 'bg-white text-slate-700 ring-1 ring-inset ring-slate-300 hover:bg-slate-50 disabled:text-slate-400',
    danger: 'bg-white text-red-600 ring-1 ring-inset ring-red-200 hover:bg-red-50 disabled:text-red-300',
    ghost: 'text-slate-600 hover:bg-slate-100 disabled:text-slate-300',
  }[variant]
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors',
        'focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed',
        styles, className,
      )}
    >
      {children}
    </button>
  )
}
