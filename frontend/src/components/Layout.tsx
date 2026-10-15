import { useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { BookOpen, FlaskConical, FolderKanban, LayoutDashboard, Menu, Network, Upload, X } from 'lucide-react'
import { useProjects } from '../hooks/ProjectContext'
import { HealthIndicator } from './HealthIndicator'
import { cx } from './ui'

const NAV: { to: string; label: string; icon: ReactNode; badge?: string }[] = [
  { to: '/', label: 'Overview', icon: <LayoutDashboard className="h-4 w-4" /> },
  { to: '/library', label: 'Paper library', icon: <BookOpen className="h-4 w-4" /> },
  { to: '/upload', label: 'Upload PDFs', icon: <Upload className="h-4 w-4" /> },
  { to: '/graph', label: 'Knowledge graph', icon: <Network className="h-4 w-4" /> },
  { to: '/investigate', label: 'Investigate', icon: <FlaskConical className="h-4 w-4" /> },
  { to: '/projects', label: 'Projects', icon: <FolderKanban className="h-4 w-4" /> },
]

function ProjectSwitcher({ onNavigate }: { onNavigate?: () => void }) {
  const { projects, activeId, select } = useProjects()
  return (
    <div className="px-2">
      <label htmlFor="project" className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-slate-400">Project</label>
      <select id="project" value={activeId} onChange={(e) => { select(e.target.value); onNavigate?.() }}
        className="w-full rounded-lg border border-slate-700 bg-slate-800 px-2.5 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none">
        {projects.length === 0 && <option value={activeId}>Loading…</option>}
        {projects.map((p) => <option key={p.id} value={p.id}>{p.name}{p.paper_count != null ? ` (${p.paper_count})` : ''}</option>)}
      </select>
    </div>
  )
}

function Brand() {
  return (
    <div className="flex items-center gap-2.5 px-2">
      <img src="/favicon.svg" alt="" className="h-8 w-8" />
      <div>
        <p className="text-sm font-semibold text-white">ResearchMind AI</p>
        <p className="text-[11px] text-slate-400">Research discovery workspace</p>
      </div>
    </div>
  )
}

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 px-3 py-5">
      <Brand />
      <ProjectSwitcher onNavigate={onNavigate} />
      <nav className="flex-1 space-y-1" aria-label="Main">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            onClick={onNavigate}
            className={({ isActive }) =>
              cx(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white',
              )
            }
          >
            {item.icon}
            <span className="flex-1">{item.label}</span>
            {item.badge && <span className="rounded bg-slate-700 px-1.5 py-0.5 text-[10px] uppercase text-slate-300">{item.badge}</span>}
          </NavLink>
        ))}
      </nav>
      <HealthIndicator />
    </div>
  )
}

export function Layout() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const { activeId } = useProjects()

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 bg-slate-900 lg:block">
        <SidebarContent />
      </aside>

      {/* Mobile top bar + drawer */}
      <div className="sticky top-0 z-30 flex items-center justify-between bg-slate-900 px-4 py-3 lg:hidden">
        <Brand />
        <button onClick={() => setOpen(true)} className="rounded-md p-2 text-slate-300 hover:bg-slate-800" aria-label="Open navigation">
          <Menu className="h-5 w-5" />
        </button>
      </div>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true">
          <div className="absolute inset-0 bg-slate-900/60" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 bg-slate-900 shadow-xl">
            <button onClick={() => setOpen(false)} className="absolute right-3 top-4 rounded-md p-1.5 text-slate-400 hover:bg-slate-800" aria-label="Close navigation">
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <main className="lg:pl-64">
        {/* Remount pages when the project changes so every view reloads that project's data. */}
        <div key={`${activeId}:${location.pathname}`} className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
