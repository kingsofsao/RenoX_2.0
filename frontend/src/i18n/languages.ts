// UI and report languages. Keep in sync with LANGUAGES in backend/researchmind/accounts.py.
export const LANGUAGES = [
  { code: 'en', name: 'English', dir: 'ltr' },
  { code: 'es', name: 'Español', dir: 'ltr' },
  { code: 'fr', name: 'Français', dir: 'ltr' },
  { code: 'de', name: 'Deutsch', dir: 'ltr' },
  { code: 'hi', name: 'हिन्दी', dir: 'ltr' },
  { code: 'ta', name: 'தமிழ்', dir: 'ltr' },
  { code: 'zh', name: '简体中文', dir: 'ltr' },
  { code: 'ja', name: '日本語', dir: 'ltr' },
  { code: 'ar', name: 'العربية', dir: 'rtl' },
] as const

export type LangCode = (typeof LANGUAGES)[number]['code']

export function isLang(code: string | null | undefined): code is LangCode {
  return LANGUAGES.some((l) => l.code === code)
}

export function langDir(code: LangCode): 'ltr' | 'rtl' {
  return LANGUAGES.find((l) => l.code === code)?.dir ?? 'ltr'
}

/** Best match for the browser's preferred languages, or English. */
export function browserLanguage(): LangCode {
  const prefs = typeof navigator === 'undefined' ? [] : navigator.languages ?? [navigator.language]
  for (const p of prefs) {
    const base = p.toLowerCase().split('-')[0]
    if (isLang(base)) return base
  }
  return 'en'
}
