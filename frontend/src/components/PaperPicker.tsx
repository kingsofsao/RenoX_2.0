import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, FileText, Lock, Search } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import type { PaperSummary } from '../types/api'
import { cx } from './ui'

/**
 * Choose the ONE paper an investigation analyses. Each paper is analysed on its own: no other paper of
 * the account is ever read, compared or cited, so there is deliberately no "all papers" option.
 */
export function PaperPicker({ papers, selected, onSelect, disabled }: {
  papers: PaperSummary[]; selected: string | null; onSelect: (id: string) => void; disabled?: boolean
}) {
  const { t, formatDate } = useI18n()
  const [query, setQuery] = useState('')
  const [expanded, setExpanded] = useState(!selected)
  const current = papers.find((p) => p.id === selected) ?? null
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? papers.filter((p) => `${p.display_title} ${p.filename ?? ''} ${p.authors.join(' ')}`.toLowerCase().includes(q)) : papers
  }, [papers, query])

  if (!papers.length) return null

  if (current && !expanded) {
    return (
      <div className="flex items-center gap-3 rounded-xl border border-brand/30 bg-brand-soft/60 px-4 py-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-solid text-white"><FileText className="h-4 w-4" /></span>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-brand-fg">{t('picker.analysing')}</p>
          <p className="truncate font-medium text-fg">{current.display_title}</p>
        </div>
        <button type="button" disabled={disabled} onClick={() => setExpanded(true)}
          className="shrink-0 rounded-md px-2.5 py-1.5 text-sm font-medium text-brand-fg transition-colors hover:bg-brand-soft disabled:opacity-50">
          {t('picker.change')}
        </button>
      </div>
    )
  }

  return (
    <fieldset className="rounded-xl border border-line bg-surface-2 p-3" disabled={disabled}>
      <legend className="px-1 text-sm font-medium text-fg">{t('picker.title')}</legend>
      <p className="mb-2 flex items-center gap-1.5 px-1 text-xs text-fg-subtle"><Lock className="h-3.5 w-3.5" />{t('picker.isolation')}</p>
      {papers.length > 6 && (
        <label className="relative mb-2 block">
          <span className="sr-only">{t('picker.search')}</span>
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t('picker.search')}
            className="w-full rounded-lg border border-line-strong bg-surface py-1.5 ps-9 pe-3 text-sm text-fg placeholder:text-fg-subtle focus:border-brand focus:outline-none" />
        </label>
      )}
      <ul className="max-h-64 space-y-1 overflow-y-auto" role="radiogroup" aria-label={t('picker.title')}>
        {shown.map((p) => {
          const active = p.id === selected
          return (
            <li key={p.id}>
              <button type="button" role="radio" aria-checked={active} onClick={() => { onSelect(p.id); setExpanded(false); setQuery('') }}
                className={cx('flex w-full items-start gap-3 rounded-lg px-3 py-2 text-start transition-all duration-150 active:scale-[0.99]',
                  active ? 'bg-surface ring-2 ring-brand' : 'hover:bg-surface')}>
                <span className={cx('mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-colors',
                  active ? 'border-brand-solid bg-brand-solid text-white' : 'border-line-strong')}>
                  {active && <Check className="h-3 w-3" />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-1 text-sm text-fg">{p.display_title}</span>
                  <span className="text-xs text-fg-subtle">
                    {p.year ?? t('picker.yearUnknown')}{p.updated_at ? ` · ${t('picker.added', { date: formatDate(p.updated_at, { dateStyle: 'medium' }) })}` : ''}
                  </span>
                </span>
              </button>
            </li>
          )
        })}
        {!shown.length && <li className="px-3 py-2 text-sm text-fg-subtle">{t('library.noMatch.title')}</li>}
      </ul>
      <div className="mt-2 px-1 text-xs">
        <Link to="/upload" className="font-medium text-brand hover:text-brand-hover">{t('picker.upload')}</Link>
      </div>
    </fieldset>
  )
}
