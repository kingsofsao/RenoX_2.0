// Site search (Ctrl/Cmd+K): pages, the active project's papers and saved investigations.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { BookOpen, CornerDownLeft, FileText, FlaskConical, FolderKanban, History, LayoutDashboard, Network, Search, Settings, Upload } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { api } from '../services/api'
import type { InvestigationSummary, PaperSummary } from '../types/api'
import { cx } from './ui'

export const OPEN_SEARCH_EVENT = 'researchmind:open-search'
export function openSearch(): void {
  window.dispatchEvent(new Event(OPEN_SEARCH_EVENT))
}

interface Item { id: string; group: MessageKey; label: string; hint?: string; icon: ReactNode; to: string }

const PAGES: { to: string; label: MessageKey; icon: ReactNode }[] = [
  { to: '/', label: 'nav.overview', icon: <LayoutDashboard className="h-4 w-4" /> },
  { to: '/investigate', label: 'nav.investigate', icon: <FlaskConical className="h-4 w-4" /> },
  { to: '/library', label: 'nav.library', icon: <BookOpen className="h-4 w-4" /> },
  { to: '/upload', label: 'nav.upload', icon: <Upload className="h-4 w-4" /> },
  { to: '/graph', label: 'nav.graph', icon: <Network className="h-4 w-4" /> },
  { to: '/projects', label: 'nav.projects', icon: <FolderKanban className="h-4 w-4" /> },
  { to: '/settings', label: 'nav.settings', icon: <Settings className="h-4 w-4" /> },
]

export function CommandPalette() {
  const { t, formatDate } = useI18n()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [papers, setPapers] = useState<PaperSummary[]>([])
  const [history, setHistory] = useState<InvestigationSummary[]>([])
  const [active, setActive] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const previous = useRef<HTMLElement | null>(null)

  const show = useCallback(() => {
    previous.current = document.activeElement as HTMLElement | null
    setQuery('')
    setActive(0)
    setOpen(true)
    api.listInvestigations(50).then((r) => setHistory(r.investigations)).catch(() => setHistory([]))
  }, [])
  const close = useCallback(() => { setOpen(false); previous.current?.focus?.() }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); show() }
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener(OPEN_SEARCH_EVENT, show)
    return () => { window.removeEventListener('keydown', onKey); window.removeEventListener(OPEN_SEARCH_EVENT, show) }
  }, [show])

  // Papers are searched on the server (title, file name); debounced while typing.
  useEffect(() => {
    if (!open) return
    const timer = window.setTimeout(() => {
      api.listPapers({ search: query.trim() || undefined, limit: 8 }).then((r) => setPapers(r.papers)).catch(() => setPapers([]))
    }, 180)
    return () => window.clearTimeout(timer)
  }, [open, query])

  useEffect(() => { if (open) requestAnimationFrame(() => input.current?.focus()) }, [open])

  const items = useMemo<Item[]>(() => {
    const q = query.trim().toLowerCase()
    const pages = PAGES.filter((p) => !q || t(p.label).toLowerCase().includes(q))
      .map((p) => ({ id: `page:${p.to}`, group: 'search.pages' as MessageKey, label: t(p.label), icon: p.icon, to: p.to }))
    const paperItems = papers.map((p) => ({ id: `paper:${p.id}`, group: 'search.papers' as MessageKey, label: p.display_title,
      hint: p.authors.slice(0, 2).join(', '), icon: <FileText className="h-4 w-4" />, to: `/papers/${p.id}` }))
    const historyItems = history.filter((h) => !q || h.question.toLowerCase().includes(q) || (h.paper_title ?? '').toLowerCase().includes(q))
      .slice(0, 6).map((h) => ({ id: `inv:${h.id}`, group: 'search.history' as MessageKey, label: h.question,
        hint: `${h.paper_title ?? ''} · ${formatDate(h.created_at, { dateStyle: 'medium' })}`, icon: <History className="h-4 w-4" />, to: `/investigate?open=${h.id}` }))
    return [...pages, ...paperItems, ...historyItems]
  }, [query, papers, history, t, formatDate])

  useEffect(() => { setActive((a) => Math.min(a, Math.max(0, items.length - 1))) }, [items.length])

  const go = (item: Item | undefined) => {
    if (!item) return
    setOpen(false)
    navigate(item.to)
  }
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { e.preventDefault(); close() }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(items.length - 1, a + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(0, a - 1)) }
    else if (e.key === 'Enter') { e.preventDefault(); go(items[active]) }
    else if (e.key === 'Tab') e.preventDefault()  // keep focus in the search box
  }

  useEffect(() => { document.getElementById(`search-item-${active}`)?.scrollIntoView({ block: 'nearest' }) }, [active])

  if (!open) return null
  let lastGroup: MessageKey | null = null
  return createPortal(
    <div className="fixed inset-0 z-[60] flex items-start justify-center p-4 pt-[12vh] print:hidden" onKeyDown={onKeyDown}>
      <div className="absolute inset-0 animate-fade-in bg-black/50 backdrop-blur-[2px]" onClick={close} aria-hidden />
      <div role="dialog" aria-modal="true" aria-label={t('search.title')}
        className="relative w-full max-w-xl animate-scale-in overflow-hidden rounded-2xl border border-line bg-surface shadow-pop">
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search className="h-4 w-4 shrink-0 text-fg-subtle" aria-hidden />
          <input ref={input} value={query} onChange={(e) => { setQuery(e.target.value); setActive(0) }}
            placeholder={t('search.placeholder')} aria-label={t('search.title')} role="combobox" aria-expanded="true"
            aria-controls="search-results" aria-activedescendant={items.length ? `search-item-${active}` : undefined}
            className="h-12 w-full bg-transparent text-[15px] text-fg placeholder:text-fg-subtle focus:outline-none" />
          <kbd className="hidden rounded border border-line px-1.5 py-0.5 text-[10px] text-fg-subtle sm:inline">Esc</kbd>
        </div>
        <ul id="search-results" role="listbox" className="max-h-[50vh] overflow-y-auto p-2">
          {items.length === 0 && <li className="px-3 py-6 text-center text-sm text-fg-subtle">{t('search.empty')}</li>}
          {items.map((item, i) => {
            const header = item.group !== lastGroup
            lastGroup = item.group
            return (
              <li key={item.id} role="presentation">
                {header && <p className="px-3 pb-1 pt-3 text-[11px] font-semibold uppercase tracking-[0.12em] text-fg-subtle">{t(item.group)}</p>}
                <div id={`search-item-${i}`} role="option" aria-selected={i === active} onMouseMove={() => setActive(i)} onClick={() => go(item)}
                  className={cx('flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                    i === active ? 'bg-brand-soft text-brand-fg' : 'text-fg')}>
                  <span className={cx('shrink-0', i === active ? 'text-brand' : 'text-fg-subtle')}>{item.icon}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{item.label}</span>
                    {item.hint && <span className="block truncate text-xs text-fg-subtle">{item.hint}</span>}
                  </span>
                  {i === active && <CornerDownLeft className="h-3.5 w-3.5 shrink-0 rtl:-scale-x-100" aria-hidden />}
                </div>
              </li>
            )
          })}
        </ul>
        <div className="flex items-center gap-4 border-t border-line px-4 py-2 text-[11px] text-fg-subtle">
          <span><kbd className="font-sans">↑ ↓</kbd> {t('search.move')}</span>
          <span><kbd className="font-sans">Enter</kbd> {t('search.open')}</span>
        </div>
      </div>
    </div>,
    document.body,
  )
}
