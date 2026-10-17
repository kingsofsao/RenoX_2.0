// Password input with show/hide, plus the strength checklist that mirrors the server's policy (app/security.py).
import { useId, useState } from 'react'
import { Check, Eye, EyeOff, X } from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { Input, cx } from './ui'

export const MIN_PASSWORD = 12
export const MAX_PASSWORD = 128
// Mirrors COMMON_PASSWORDS in backend/app/security.py (exact matches); the server stays the authority.
const COMMON = new Set([
  '123456789012', '1234567890123', 'password1234', 'password12345', 'passwordpassword', 'qwertyuiop12', 'qwertyuiopas',
  '1q2w3e4r5t6y', '1qaz2wsx3edc', 'iloveyou1234', 'letmein12345', 'welcome12345', 'administrator', 'changeme1234',
  'abc123456789', 'aaaaaaaaaaaa', '111111111111', '000000000000', '123123123123', 'qwerty123456', 'football1234',
  'baseball1234', 'monkey123456', 'dragon123456', 'sunshine1234', 'princess1234', 'trustno11234', 'superman1234',
  'starwars1234', 'whatever1234', 'passw0rd1234', 'p@ssw0rd1234', 'p@ssword1234', 'correcthorsebatterystaple',
  'researchmind', 'researchmind1', 'researchmind123', 'qwertyqwerty', 'asdfghjklzxc', 'zxcvbnm12345',
])

export interface PasswordCheck { key: MessageKey; ok: boolean }

export function passwordChecks(password: string, email = '', name = ''): PasswordCheck[] {
  const low = password.toLowerCase()
  const personal = [email.split('@')[0], ...name.split(/\s+/)].map((p) => p.toLowerCase()).filter((p) => p.length >= 4)
  return [
    { key: 'password.rule.length', ok: password.length >= MIN_PASSWORD && password.length <= MAX_PASSWORD },
    { key: 'password.rule.common', ok: password.length > 0 && !COMMON.has(low) && new Set(low).size >= 4 },
    { key: 'password.rule.personal', ok: password.length > 0 && !personal.some((p) => low.includes(p)) },
  ]
}

/** 0-4: length and character variety beyond the policy minimum. */
export function passwordScore(password: string): number {
  if (!password) return 0
  let score = password.length >= MIN_PASSWORD ? 1 : 0
  if (password.length >= 16) score++
  const classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter((r) => r.test(password)).length
  if (classes >= 3) score++
  if (password.length >= 20 && classes >= 2) score++
  return Math.min(4, score)
}

export function PasswordInput({ id, value, onChange, autoComplete, invalid, placeholder }: {
  id: string; value: string; onChange: (v: string) => void; autoComplete: string; invalid?: boolean; placeholder?: string
}) {
  const { t } = useI18n()
  const [visible, setVisible] = useState(false)
  return (
    <div className="relative">
      <Input id={id} type={visible ? 'text' : 'password'} value={value} onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete} maxLength={MAX_PASSWORD} aria-invalid={invalid || undefined} placeholder={placeholder}
        className="pe-10" spellCheck={false} autoCapitalize="off" />
      <button type="button" onClick={() => setVisible((v) => !v)}
        className="absolute inset-y-0 end-0 flex items-center px-3 text-fg-subtle transition-colors hover:text-fg"
        aria-label={visible ? t('password.hide') : t('password.show')} aria-pressed={visible}>
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}

export function PasswordStrength({ password, email, name }: { password: string; email?: string; name?: string }) {
  const { t } = useI18n()
  const listId = useId()
  const score = passwordScore(password)
  const checks = passwordChecks(password, email, name)
  const labels: MessageKey[] = ['password.strength.0', 'password.strength.1', 'password.strength.2', 'password.strength.3', 'password.strength.4']
  const colors = ['bg-surface-3', 'bg-bad', 'bg-warn', 'bg-brand', 'bg-ok']
  return (
    <div className="space-y-2" aria-describedby={listId}>
      <div className="flex items-center gap-2">
        <div className="flex flex-1 gap-1">
          {[1, 2, 3, 4].map((i) => (
            <span key={i} className={cx('h-1 flex-1 rounded-full transition-colors duration-300', i <= score ? colors[score] : 'bg-surface-3')} />
          ))}
        </div>
        <span className="w-20 text-end text-xs text-fg-muted">{password ? t(labels[score]) : ''}</span>
      </div>
      <ul id={listId} className="space-y-1">
        {checks.map((c) => (
          <li key={c.key} className={cx('flex items-center gap-1.5 text-xs transition-colors', c.ok ? 'text-ok-fg' : 'text-fg-subtle')}>
            {c.ok ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
            {t(c.key, { min: MIN_PASSWORD })}
          </li>
        ))}
      </ul>
    </div>
  )
}
