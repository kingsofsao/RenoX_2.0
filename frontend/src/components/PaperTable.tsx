import { Link } from 'react-router-dom'
import { FileText } from 'lucide-react'
import type { PaperSummary } from '../types/api'
import { formatBytes, formatDate } from '../services/format'
import { StatusBadge } from './ui'

function TitleCell({ paper }: { paper: PaperSummary }) {
  return (
    <div className="min-w-0">
      <Link to={`/papers/${paper.id}`} className="font-medium text-slate-900 hover:text-indigo-600">
        {paper.title ?? <span className="italic text-slate-600">Title not detected</span>}
      </Link>
      {paper.status === 'failed' && paper.error && <p className="mt-0.5 line-clamp-2 text-xs text-red-600">{paper.error}</p>}
      {paper.status === 'processed' && paper.authors.length > 0 && (
        <p className="mt-0.5 truncate text-xs text-slate-500">{paper.authors.join(', ')}{paper.year ? ` · ${paper.year}` : ''}</p>
      )}
    </div>
  )
}

/** Responsive paper list: a table on wide screens, stacked cards on phones. */
export function PaperTable({ papers, compact = false }: { papers: PaperSummary[]; compact?: boolean }) {
  return (
    <>
      <div className="hidden overflow-x-auto md:block">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3">Title</th>
              <th className="px-3 py-3">File</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3 text-right">Pages</th>
              {!compact && <th className="px-3 py-3 text-right">Size</th>}
              {!compact && <th className="px-5 py-3">Updated</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {papers.map((p) => (
              <tr key={p.id} className="hover:bg-slate-50/70">
                <td className="max-w-md px-5 py-3"><TitleCell paper={p} /></td>
                <td className="max-w-[14rem] truncate px-3 py-3 text-slate-600" title={p.filename ?? ''}>{p.filename ?? '—'}</td>
                <td className="px-3 py-3"><StatusBadge status={p.status} /></td>
                <td className="px-3 py-3 text-right tabular-nums text-slate-600">{p.page_count ?? '—'}</td>
                {!compact && <td className="px-3 py-3 text-right tabular-nums text-slate-600">{formatBytes(p.file_size)}</td>}
                {!compact && <td className="whitespace-nowrap px-5 py-3 text-slate-500">{formatDate(p.updated_at)}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className="divide-y divide-slate-100 md:hidden">
        {papers.map((p) => (
          <li key={p.id} className="flex gap-3 px-4 py-3">
            <FileText className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
            <div className="min-w-0 flex-1">
              <TitleCell paper={p} />
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <StatusBadge status={p.status} />
                <span className="truncate">{p.filename}</span>
                {p.page_count != null && <span>· {p.page_count} pages</span>}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </>
  )
}
