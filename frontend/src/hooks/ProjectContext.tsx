import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, setActiveProject } from '../services/api'
import type { Project } from '../types/api'

const STORAGE_KEY = 'researchmind.activeProject'

interface ProjectState {
  projects: Project[]
  active: Project | null
  activeId: string
  loading: boolean
  select: (id: string) => void
  refresh: () => Promise<void>
}

const ProjectContext = createContext<ProjectState | null>(null)

function storedId(): string {
  try { return localStorage.getItem(STORAGE_KEY) || 'default' } catch { return 'default' }
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [activeId, setActiveId] = useState<string>(() => { const id = storedId(); setActiveProject(id); return id })
  const [loading, setLoading] = useState(true)

  const select = useCallback((id: string) => {
    setActiveProject(id)
    setActiveId(id)
    try { localStorage.setItem(STORAGE_KEY, id) } catch { /* storage unavailable */ }
  }, [])

  const refresh = useCallback(async () => {
    try {
      const list = (await api.listProjects()).projects
      setProjects(list)
      // The stored project may have been deleted: fall back to the Default project.
      if (!list.some((p) => p.id === storedId())) select('default')
    } catch { /* API or database down: keep the current selection */ } finally {
      setLoading(false)
    }
  }, [select])

  useEffect(() => { void refresh() }, [refresh])

  const active = projects.find((p) => p.id === activeId) ?? null
  return (
    <ProjectContext.Provider value={{ projects, active, activeId, loading, select, refresh }}>{children}</ProjectContext.Provider>
  )
}

export function useProjects(): ProjectState {
  const ctx = useContext(ProjectContext)
  if (!ctx) throw new Error('useProjects must be used inside <ProjectProvider>')
  return ctx
}
