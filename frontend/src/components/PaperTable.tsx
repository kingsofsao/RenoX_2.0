import { Link } from 'react-router-dom'
import { FileText, FlaskConical } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import { formatBytes } from '../services/format'
import type { PaperSummary } from '../types/api'
import { StatusBadge } from './ui'

function TitleCell({ paper }: { paper: PaperSummary }) {
  const { t } = useI18n()
  return (
    <div className="min-w-0">
      <Link to={`/papers/${paper.id}`} className="font-medium text-fg transition-colors hover:text-brand">
        {paper.title ?? <span className="italic text-fg-muted">{t('paper.untitled')}</span>}
      </Link>
      {paper.status === 'failed' && paper.error && <p className="mt-0.5 line-clamp-2 text-xs text-bad-fg">{paper.error}</p>}
      {paper.status === 'processed' && paper.authors.length > 0 && (
        <p className="mt-0.5 truncate text-xs text-fg-subtle">{paper.authors.join(', ')}{paper.year ? ` · ${paper.year}` : ''}</p>
      )}
    </div>
  )
}

function AnalyseLink({ paper }: { paper: PaperSummary }) {
  const { t } = useI18n()
  if (paper.status !== 'processed') return null
  return (
    <Link to={`/investigate?paper=${encodeURIComponent(paper.id)}`} title={t('paper.analyse')}
      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-brand transition-colors hover:bg-brand-soft">
      <FlaskConical className="h-3.5 w-3.5" />{t('paper.analyse.short')}
    </Link>
  )
}

/** Responsive paper list: a table on wide screens, stacked cards on phones. */
export function PaperTable({ papers, compact = false }: { papers: PaperSummary[]; compact?: boolean }) {
  const { t, tn, formatDate } = useI18n()
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="min-w-full divide-y divide-line text-sm">
          <thead className="bg-surface-2 text-start text-xs font-medium uppercase tracking-wide text-fg-subtle">
            <tr>
              <th className="px-5 py-3 text-start">{t('paper.col.title')}</th>
              <th className="px-3 py-3 text-start">{t('paper.col.file')}</th>
              <th className="px-3 py-3 text-start">{t('paper.col.status')}</th>
              <th className="px-3 py-3 text-end">{t('paper.col.pages')}</th>
              {!compact && <th className="px-3 py-3 text-end">{t('paper.col.size')}</th>}
              {!compact && <th className="px-3 py-3 text-start">{t('paper.col.updated')}</th>}
              <th className="px-5 py-3"><span className="sr-only">{t('paper.analyse')}</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line bg-surface">
            {papers.map((p) => (
              <tr key={p.id} className="transition-colors hover:bg-surface-2">
                <td className="max-w-md px-5 py-3"><TitleCell paper={p} /></td>
                <td className="max-w-[14rem] truncate px-3 py-3 text-fg-muted" title={p.filename ?? ''}>{p.filename ?? '—'}</td>
                <td className="px-3 py-3"><StatusBadge status={p.status} /></td>
                <td className="px-3 py-3 text-end tabular-nums text-fg-muted">{p.page_count ?? '—'}</td>
                {!compact && <td className="px-3 py-3 text-end tabular-nums text-fg-muted">{formatBytes(p.file_size)}</td>}
                {!compact && <td className="whitespace-nowrap px-3 py-3 text-fg-subtle">{formatDate(p.updated_at)}</td>}
                <td className="px-5 py-3 text-end"><AnalyseLink paper={p} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-line md:hidden">
        {papers.map((p) => (
          <li key={p.id} className="flex gap-3 px-4 py-3">
            <FileText className="mt-0.5 h-4 w-4 shrink-0 text-fg-subtle" />
            <div className="min-w-0 flex-1">
              <TitleCell paper={p} />
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-fg-subtle">
                <StatusBadge status={p.status} />
                <span className="truncate">{p.filename}</span>
                {p.page_count != null && <span>· {tn('paper.pages', p.page_count)}</span>}
                <AnalyseLink paper={p} />
              </div>
            </div>
          </li>
        ))}
      </ul>
    </>
  )
}
