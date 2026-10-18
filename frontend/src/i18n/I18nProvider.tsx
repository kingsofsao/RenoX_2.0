import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { en, type Dict, type MessageKey } from './en'
import { browserLanguage, isLang, langDir, type LangCode } from './languages'

type Vars = Record<string, string | number>
/** Keys that have plural forms: `<base>_one` / `<base>_other`. */
export type PluralKey = MessageKey extends infer K ? (K extends `${infer B}_other` ? B : never) : never

interface I18nState {
  lang: LangCode
  dir: 'ltr' | 'rtl'
  setLang: (lang: LangCode) => void
  t: (key: MessageKey, vars?: Vars) => string
  tn: (key: PluralKey, count: number, vars?: Vars) => string
  /** Locale-aware number / date formatting in the UI language. */
  formatNumber: (n: number) => string
  formatDate: (iso: string | null | undefined, opts?: Intl.DateTimeFormatOptions) => string
}

const STORAGE_KEY = 'researchmind.language'
// Translations are loaded on demand; English is bundled and is the fallback for every key.
const loaders: Record<Exclude<LangCode, 'en'>, () => Promise<{ default: Dict }>> = {
  es: () => import('./locales/es'),
  fr: () => import('./locales/fr'),
  de: () => import('./locales/de'),
  hi: () => import('./locales/hi'),
  ta: () => import('./locales/ta'),
  zh: () => import('./locales/zh'),
  ja: () => import('./locales/ja'),
  ar: () => import('./locales/ar'),
}

function storedLanguage(): LangCode {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    if (isLang(v)) return v
  } catch { /* storage unavailable */ }
  return browserLanguage()
}

function interpolate(text: string, vars?: Vars): string {
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m))
}

const I18nContext = createContext<I18nState | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<LangCode>(storedLanguage)
  const [dict, setDict] = useState<Dict>(en)

  useEffect(() => {
    let cancelled = false
    if (lang === 'en') {
      setDict(en)
    } else {
      loaders[lang]().then((m) => { if (!cancelled) setDict(m.default) }).catch(() => { if (!cancelled) setDict(en) })
    }
    document.documentElement.lang = lang
    document.documentElement.dir = langDir(lang)
    return () => { cancelled = true }
  }, [lang])

  const setLang = useCallback((next: LangCode) => {
    setLangState(next)
    try { localStorage.setItem(STORAGE_KEY, next) } catch { /* storage unavailable */ }
  }, [])

  const value = useMemo<I18nState>(() => {
    const plural = new Intl.PluralRules(lang)
    const num = new Intl.NumberFormat(lang)
    const t = (key: MessageKey, vars?: Vars) => interpolate(dict[key] ?? en[key] ?? key, vars)
    const tn = (key: PluralKey, count: number, vars?: Vars) => {
      const form = plural.select(count) === 'one' ? 'one' : 'other'
      return t(`${key}_${form}` as MessageKey, { count: num.format(count), ...vars })
    }
    const formatDate = (iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = { dateStyle: 'medium', timeStyle: 'short' }) => {
      if (!iso) return '-'
      const d = new Date(iso)
      return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(lang, opts)
    }
    return { lang, dir: langDir(lang), setLang, t, tn, formatNumber: (n) => num.format(n), formatDate }
  }, [lang, dict, setLang])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used inside <I18nProvider>')
  return ctx
}
