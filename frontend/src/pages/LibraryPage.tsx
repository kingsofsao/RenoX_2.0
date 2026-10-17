import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BookOpen, RefreshCw, Search, Upload } from 'lucide-react'
import { DatabaseNotice } from '../components/DatabaseNotice'
import { PaperTable } from '../components/PaperTable'
import { Alert, Button, ButtonLink, Card, EmptyState, LoadingBlock, PageHeader, cx } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { api } from '../services/api'
import { errorText } from '../services/errors'
import type { PaperStatus } from '../types/api'

const PAGE_SIZE = 20
const FILTERS: { value: PaperStatus | 'all'; label: MessageKey }[] = [
  { value: 'all', label: 'library.filter.all' },
  { value: 'processed', label: 'status.processed' },
  { value: 'failed', label: 'status.failed' },
]

export function LibraryPage() {
  const { t, tn, formatNumber } = useI18n()
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') as PaperStatus | null) ?? undefined
  const search = params.get('q') ?? ''
  const page = Math.max(1, Number(params.get('page') ?? 1))
  const [draft, setDraft] = useState(search)

  // Debounce the search box into the URL.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (draft !== search) {
        const next = new URLSearchParams(params)
        if (draft) next.set('q', draft)
        else next.delete('q')
        next.delete('page')
        setParams(next, { replace: true })
      }
    }, 300)
    return () => window.clearTimeout(timer)
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
        title={t('library.title')}
        description={t('library.description')}
        actions={
          <>
            <Button variant="secondary" onClick={reload}><RefreshCw className="h-4 w-4" /> {t('common.refresh')}</Button>
            <ButtonLink to="/upload"><Upload className="h-4 w-4" /> {t('nav.upload')}</ButtonLink>
          </>
        }
      />
      <div className="space-y-4">
        <DatabaseNotice />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="inline-flex rounded-lg bg-surface-3 p-1" role="tablist">
            {FILTERS.map((f) => {
              const active = (status ?? 'all') === f.value
              const n = counts ? (f.value === 'all' ? counts.total : counts[f.value]) : null
              return (
                <button key={f.value} role="tab" aria-selected={active} onClick={() => setFilter(f.value)}
                  className={cx('rounded-md px-3 py-1.5 text-sm font-medium transition-all duration-150 active:scale-95',
                    active ? 'bg-surface text-fg shadow-sm' : 'text-fg-muted hover:text-fg')}>
                  {t(f.label)}{n != null && <span className="ms-1.5 text-xs text-fg-subtle">{formatNumber(n)}</span>}
                </button>
              )
            })}
          </div>
          <label className="relative block sm:w-72">
            <span className="sr-only">{t('library.search')}</span>
            <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-subtle" />
            <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder={t('library.search.placeholder')} maxLength={200}
              className="w-full rounded-lg border border-line-strong bg-surface py-2 ps-9 pe-3 text-sm text-fg placeholder:text-fg-subtle focus:border-brand focus:outline-none focus:ring-3 focus:ring-brand/20" />
          </label>
        </div>

        <Card>
          {loading && !data ? (
            <LoadingBlock rows={5} />
          ) : error ? (
            <div className="p-5"><Alert tone="error" title={t('library.loadFailed')} action={<Button variant="secondary" size="sm" onClick={reload}>{t('common.retry')}</Button>}>{errorText(t, error)}</Alert></div>
          ) : data && data.papers.length > 0 ? (
            <div className={cx('transition-opacity', loading && 'opacity-60')}>
              <PaperTable papers={data.papers} />
            </div>
          ) : (
            <EmptyState icon={<BookOpen className="h-6 w-6" />}
              title={search || status ? t('library.noMatch.title') : t('library.empty.title')}
              description={search || status ? t('library.noMatch.text') : t('library.empty.text')}
              action={!search && !status ? <ButtonLink to="/upload"><Upload className="h-4 w-4" />{t('nav.upload')}</ButtonLink> : undefined} />
          )}
          {data && data.total_matching > PAGE_SIZE && (
            <div className="flex items-center justify-between border-t border-line px-5 py-3 text-sm">
              <span className="text-fg-muted">{t('library.page', { page, total: totalPages })} · {tn('library.papers', data.total_matching)}</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => goToPage(page - 1)}>{t('common.previous')}</Button>
                <Button variant="secondary" size="sm" disabled={page >= totalPages} onClick={() => goToPage(page + 1)}>{t('common.next')}</Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </>
  )
}
