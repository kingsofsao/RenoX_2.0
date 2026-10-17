import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, setActiveProject } from '../services/api'
import type { Project } from '../types/api'

// Remembered per account, so a shared computer never opens another person's project id.
const storageKey = (userId: string) => `researchmind.activeProject.${userId}`

interface ProjectState {
  projects: Project[]
  active: Project | null
  activeId: string
  loading: boolean
  error: boolean
  select: (id: string) => void
  refresh: () => Promise<void>
}

const ProjectContext = createContext<ProjectState | null>(null)

function stored(userId: string): string {
  try { return localStorage.getItem(storageKey(userId)) || '' } catch { return '' }
}

/** Loads the signed-in user's projects and keeps one active; data routes are scoped to it. */
export function ProjectProvider({ userId, children }: { userId: string; children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [activeId, setActiveId] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  const select = useCallback((id: string) => {
    setActiveProject(id)
    setActiveId(id)
    try { localStorage.setItem(storageKey(userId), id) } catch { /* storage unavailable */ }
  }, [userId])

  const refresh = useCallback(async () => {
    try {
      const list = (await api.listProjects()).projects
      setProjects(list)
      setError(false)
      // The remembered project may have been deleted: fall back to the first one.
      const remembered = stored(userId)
      const current = list.find((p) => p.id === remembered) ?? list[0]
      if (current) select(current.id)
    } catch {
      setError(true)
    } finally {
      setLoading(false)
    }
  }, [select, userId])

  useEffect(() => {
    setActiveProject('')
    void refresh()
    return () => setActiveProject('')
  }, [refresh])

  const active = projects.find((p) => p.id === activeId) ?? null
  return (
    <ProjectContext.Provider value={{ projects, active, activeId, loading, error, select, refresh }}>{children}</ProjectContext.Provider>
  )
}

export function useProjects(): ProjectState {
  const ctx = useContext(ProjectContext)
  if (!ctx) throw new Error('useProjects must be used inside <ProjectProvider>')
  return ctx
}
