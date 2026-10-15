import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { BookOpen, RefreshCw, Search, Upload } from 'lucide-react'
import { DatabaseNotice } from '../components/DatabaseNotice'
import { PaperTable } from '../components/PaperTable'
import { Alert, Button, Card, EmptyState, LoadingBlock, PageHeader, cx } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import type { PaperStatus } from '../types/api'

const PAGE_SIZE = 20
const FILTERS: { value: PaperStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'processed', label: 'Processed' },
  { value: 'failed', label: 'Failed' },
]

export function LibraryPage() {
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') as PaperStatus | null) ?? undefined
  const search = params.get('q') ?? ''
  const page = Math.max(1, Number(params.get('page') ?? 1))
  const [draft, setDraft] = useState(search)

  // Debounce the search box into the URL.
  useEffect(() => {
    const t = window.setTimeout(() => {
      if (draft !== search) {
        const next = new URLSearchParams(params)
        if (draft) next.set('q', draft)
        else next.delete('q')
        next.delete('page')
        setParams(next, { replace: true })
      }
    }, 300)
    return () => window.clearTimeout(t)
  }, [draft, search, params, setParams])

  const { data, error, loading, reload } = useAsync(
    () => api.listPapers({ status, search: search || undefined, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    [status, search, page],
  )

  const setFilter = (value: PaperStatus | 'all') => {
    const next = new URLSearchParams(params)
    if (value === 'all') next.delete('status')
    else next.set('status', value)
    next.delete('page')
    setParams(next)
  }
  const goToPage = (n: number) => {
    const next = new URLSearchParams(params)
    next.set('page', String(n))
    setParams(next)
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total_matching / PAGE_SIZE)) : 1
  const counts = data?.counts

  return (
    <>
      <PageHeader
        title="Paper library"
        description="All papers recorded in the knowledge graph, including uploads that could not be processed."
        actions={
          <>
            <Button variant="secondary" onClick={reload}><RefreshCw className="h-4 w-4" /> Refresh</Button>
            <Link to="/upload"><Button><Upload className="h-4 w-4" /> Upload</Button></Link>
          </>
        }
      />
      <div className="space-y-4">
        <DatabaseNotice />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="inline-flex rounded-lg bg-slate-100 p-1">
            {FILTERS.map((f) => {
              const active = (status ?? 'all') === f.value
              const n = counts ? (f.value === 'all' ? counts.total : counts[f.value]) : null
              return (
                <button key={f.value} onClick={() => setFilter(f.value)}
                  className={cx('rounded-md px-3 py-1.5 text-sm font-medium transition-colors', active ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900')}>
                  {f.label}{n != null && <span className="ml-1.5 text-xs text-slate-400">{n}</span>}
                </button>
              )
            })}
          </div>
          <label className="relative block sm:w-72">
            <span className="sr-only">Search papers</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Search title or filename…"
              className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20" />
          </label>
        </div>

        <Card>
          {loading && !data ? (
            <LoadingBlock label="Loading papers…" />
          ) : error ? (
            <div className="p-5"><Alert tone="error" title="Could not load the library" action={<Button variant="secondary" onClick={reload}>Retry</Button>}>{error.message}</Alert></div>
          ) : data && data.papers.length > 0 ? (
            <div className={cx(loading && 'opacity-60 transition-opacity')}>
              <PaperTable papers={data.papers} />
            </div>
          ) : (
            <EmptyState icon={<BookOpen className="h-6 w-6" />}
              title={search || status ? 'No matching papers' : 'Your library is empty'}
              description={search || status ? 'Try a different search or filter.' : 'Upload PDFs to add them to the knowledge graph.'}
              action={!search && !status ? <Link to="/upload"><Button>Upload PDFs</Button></Link> : undefined} />
          )}
          {data && data.total_matching > PAGE_SIZE && (
            <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-sm">
              <span className="text-slate-500">Page {page} of {totalPages} · {data.total_matching} papers</span>
              <div className="flex gap-2">
                <Button variant="secondary" disabled={page <= 1} onClick={() => goToPage(page - 1)}>Previous</Button>
                <Button variant="secondary" disabled={page >= totalPages} onClick={() => goToPage(page + 1)}>Next</Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </>
  )
}
