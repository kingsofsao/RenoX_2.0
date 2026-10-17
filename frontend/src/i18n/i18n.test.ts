// MOCKED unit tests: translation completeness, password rules and investigation progress (no network).
import { describe, expect, it } from 'vitest'
import { en, type Dict } from './en'
import { LANGUAGES } from './languages'
import ar from './locales/ar'
import de from './locales/de'
import es from './locales/es'
import fr from './locales/fr'
import hi from './locales/hi'
import ja from './locales/ja'
import ta from './locales/ta'
import zh from './locales/zh'
import { passwordChecks, passwordScore } from '../components/PasswordField'
import { estimateProgress } from '../pages/InvestigatePage'
import type { Investigation } from '../types/api'

const LOCALES: Record<string, Dict> = { es, fr, de, hi, ta, zh, ja, ar }
// Words that are genuinely spelled the same as in English.
const SAME_AS_ENGLISH: Record<string, string[]> = {
  fr: ['projects.investigations_one', 'projects.investigations_other', 'result.sources'],
}
const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()

describe('translations', () => {
  it('cover every supported language', () => {
    expect(Object.keys(LOCALES).sort()).toEqual(LANGUAGES.filter((l) => l.code !== 'en').map((l) => l.code).sort())
  })

  it.each(Object.entries(LOCALES))('%s has every key, with the same placeholders', (_, dict) => {
    expect(Object.keys(dict).sort()).toEqual(Object.keys(en).sort())
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(placeholders(dict[key]), key).toEqual(placeholders(en[key]))
      if (en[key]) expect(dict[key].trim().length, key).toBeGreaterThan(0)
    }
  })

  it.each(Object.entries(LOCALES))('%s is translated, not copied from English', (code, dict) => {
    const keys = Object.keys(en) as (keyof typeof en)[]
    const copied = keys.filter((k) => en[k].length > 14 && dict[k] === en[k] && !SAME_AS_ENGLISH[code]?.includes(k))
    expect(copied).toEqual([])
  })
})

describe('password rules', () => {
  it('mirror the server policy', () => {
    expect(passwordChecks('short').every((c) => c.ok)).toBe(false)
    expect(passwordChecks('password1234').find((c) => c.key === 'password.rule.common')?.ok).toBe(false)
    expect(passwordChecks('ada-lovelace-rocks', 'ada@example.org', 'Ada Lovelace').find((c) => c.key === 'password.rule.personal')?.ok).toBe(false)
    expect(passwordChecks('violet-harbour-lantern-42', 'ada@example.org', 'Ada Lovelace').every((c) => c.ok)).toBe(true)
    expect(passwordScore('')).toBe(0)
    expect(passwordScore('Violet-Harbour-Lantern-42')).toBe(4)
  })
})

describe('investigation progress', () => {
  const inv = (progress: Investigation['progress'], status: Investigation['status'] = 'running') => ({ status, progress }) as Investigation
  const ev = (type: string, message: string) => ({ type, message, tool: null, at: 0 })

  it('moves through retrieval, AI writing and verification, and only reaches 100% when done', () => {
    const retrieving = estimateProgress(inv([ev('status', 'Analysing one paper'), ev('tool_result', 'a'), ev('tool_result', 'b')]))
    expect(retrieving.stage).toBe(0)
    const writing = estimateProgress(inv([ev('tool_result', 'a'), ev('status', 'qwen3:8b is reading 9 sources and writing'),
      ev('status', 'qwen3:8b generating… 450 tokens')]))
    expect(writing.stage).toBe(1)
    expect(writing.pct).toBeGreaterThan(retrieving.pct)
    expect(writing.pct).toBeLessThan(100)
    const verifying = estimateProgress(inv([ev('status', 'Building structured report and verifying sources')]))
    expect(verifying.stage).toBe(2)
    expect(verifying.pct).toBeGreaterThanOrEqual(92)
    expect(estimateProgress(inv([], 'completed'))).toEqual({ stage: 4, pct: 100 })
  })
})
