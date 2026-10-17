import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import type { ThemeSetting } from '../types/api'

interface ThemeState {
  setting: ThemeSetting
  resolved: 'light' | 'dark'
  setSetting: (s: ThemeSetting) => void
}

// Read by public/theme-init.js before the first paint, so a dark-theme user never sees a white flash.
const STORAGE_KEY = 'researchmind.theme'
const ThemeContext = createContext<ThemeState | null>(null)

function storedSetting(): ThemeSetting {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch { /* storage unavailable */ }
  return 'system'
}

function systemDark(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [setting, setSettingState] = useState<ThemeSetting>(storedSetting)
  const [osDark, setOsDark] = useState(systemDark)

  useEffect(() => {
    const mq = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!mq) return
    const onChange = (e: MediaQueryListEvent) => setOsDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  const resolved = setting === 'system' ? (osDark ? 'dark' : 'light') : setting

  useEffect(() => {
    document.documentElement.classList.toggle('dark', resolved === 'dark')
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', resolved === 'dark' ? '#000000' : '#ffffff')
  }, [resolved])

  const setSetting = useCallback((s: ThemeSetting) => {
    setSettingState(s)
    try { localStorage.setItem(STORAGE_KEY, s) } catch { /* storage unavailable */ }
  }, [])

  return <ThemeContext.Provider value={{ setting, resolved, setSetting }}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used inside <ThemeProvider>')
  return ctx
}
