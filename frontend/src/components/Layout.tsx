import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { BookOpen, ChevronsUpDown, FlaskConical, FolderKanban, LayoutDashboard, LogOut, Menu, Network, Settings, Upload, X } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { useProjects } from '../hooks/ProjectContext'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { HealthIndicator } from './HealthIndicator'
import { LanguageSelect, ThemeToggle } from './Preferences'
import { Logo, cx } from './ui'

const NAV: { to: string; label: MessageKey; icon: ReactNode }[] = [
  { to: '/', label: 'nav.overview', icon: <LayoutDashboard className="h-4 w-4" /> },
  { to: '/investigate', label: 'nav.investigate', icon: <FlaskConical className="h-4 w-4" /> },
  { to: '/library', label: 'nav.library', icon: <BookOpen className="h-4 w-4" /> },
  { to: '/upload', label: 'nav.upload', icon: <Upload className="h-4 w-4" /> },
  { to: '/graph', label: 'nav.graph', icon: <Network className="h-4 w-4" /> },
  { to: '/projects', label: 'nav.projects', icon: <FolderKanban className="h-4 w-4" /> },
]

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase() || '?'
}

function ProjectSwitcher({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n()
  const { projects, activeId, select } = useProjects()
  return (
    <div className="px-2">
      <label htmlFor="project" className="mb-1.5 block text-[11px] font-medium uppercase tracking-[0.12em] text-white/40">{t('nav.project')}</label>
      <div className="relative">
        <select id="project" value={activeId} onChange={(e) => { select(e.target.value); onNavigate?.() }}
          className="w-full cursor-pointer appearance-none rounded-lg border border-sidebar-line bg-sidebar-2 py-2 ps-3 pe-8 text-sm text-white transition-colors hover:border-white/20 focus:border-brand focus:outline-none">
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}{p.paper_count != null ? ` (${p.paper_count})` : ''}</option>)}
        </select>
        <ChevronsUpDown className="pointer-events-none absolute end-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
      </div>
    </div>
  )
}

function UserMenu({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n()
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc) }
  }, [open])
  if (!user) return null
  return (
    <div ref={ref} className="relative">
      {open && (
        <div className="absolute bottom-full start-0 end-0 mb-2 animate-scale-in overflow-hidden rounded-xl border border-sidebar-line bg-sidebar-2 shadow-pop" role="menu">
          <div className="space-y-3 border-b border-sidebar-line p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-white/50">{t('settings.theme')}</span>
              <ThemeToggle tone="dark" />
            </div>
            <LanguageSelect tone="dark" className="w-full [&>select]:w-full" />
          </div>
          <button type="button" role="menuitem" onClick={() => { setOpen(false); onNavigate?.(); navigate('/settings') }}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white">
            <Settings className="h-4 w-4" /> {t('nav.settings')}
          </button>
          <button type="button" role="menuitem" onClick={() => { setOpen(false); void signOut().then(() => navigate('/signin', { replace: true })) }}
            className="flex w-full items-center gap-2.5 px-3 py-2.5 text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white">
            <LogOut className="h-4 w-4 rtl:rotate-180" /> {t('nav.signOut')}
          </button>
        </div>
      )}
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} aria-haspopup="menu"
        className="flex w-full items-center gap-3 rounded-xl p-2 text-start transition-colors hover:bg-white/5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand text-xs font-semibold text-white">{initials(user.name)}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-white">{user.name}</span>
          <span className="block truncate text-xs text-white/45">{user.email}</span>
        </span>
        <ChevronsUpDown className="h-4 w-4 shrink-0 text-white/40" />
      </button>
    </div>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <Logo className="h-8 w-8" />
      <div className="leading-tight">
        <p className="text-sm font-semibold tracking-tight text-white">ResearchMind <span className="text-[#5ea2ff]">AI</span></p>
      </div>
    </div>
  )
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n()
  return (
    <div className="flex h-full flex-col gap-6 px-3 py-5">
      <Brand />
      <ProjectSwitcher onNavigate={onNavigate} />
      <nav className="flex-1 space-y-0.5" aria-label={t('nav.main')}>
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'} onClick={onNavigate}
            className={({ isActive }) => cx(
              'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-150',
              isActive ? 'bg-white/[0.08] text-white' : 'text-white/60 hover:bg-white/[0.04] hover:text-white',
            )}>
            {({ isActive }) => (
              <>
                <span className={cx('absolute inset-y-1.5 start-0 w-[3px] rounded-full bg-brand transition-opacity', isActive ? 'opacity-100' : 'opacity-0')} />
                <span className={cx('transition-colors', isActive ? 'text-[#5ea2ff]' : 'text-white/50 group-hover:text-white')}>{item.icon}</span>
                <span className="flex-1">{t(item.label)}</span>
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <HealthIndicator />
      <UserMenu onNavigate={onNavigate} />
    </div>
  )
}

export function Layout() {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const { activeId } = useProjects()

  return (
    <div className="min-h-screen bg-canvas">
      <a href="#content" className="sr-only focus:not-sr-only focus:fixed focus:start-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-brand focus:px-3 focus:py-2 focus:text-white">
        {t('nav.skip')}
      </a>
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 start-0 hidden w-64 border-e border-sidebar-line bg-sidebar lg:block">
        <SidebarContent />
      </aside>

      {/* Mobile top bar + drawer */}
      <div className="sticky top-0 z-30 flex items-center justify-between border-b border-sidebar-line bg-sidebar px-4 py-3 lg:hidden">
        <Brand />
        <button onClick={() => setOpen(true)} className="rounded-md p-2 text-white/70 transition-colors hover:bg-white/10 hover:text-white" aria-label={t('nav.open')}>
          <Menu className="h-5 w-5" />
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 animate-fade-in bg-black/60 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 start-0 w-72 animate-fade-in bg-sidebar shadow-pop">
            <button onClick={() => setOpen(false)} className="absolute end-3 top-4 rounded-md p-1.5 text-white/60 hover:bg-white/10" aria-label={t('nav.close')}>
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <main id="content" className="lg:ps-64">
        {/* Remount pages when the project changes so every view reloads that project's data. */}
        <div key={`${activeId}:${location.pathname}`} className="mx-auto max-w-7xl animate-fade-up px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
