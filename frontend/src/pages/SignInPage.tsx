import { useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { safeNext, setPostAuthRedirect } from '../auth/redirect'
import { AuthShell } from '../components/AuthShell'
import { PasswordInput } from '../components/PasswordField'
import { Alert, Button, Field, Input } from '../components/ui'
import { useI18n } from '../i18n/I18nProvider'
import { toApiError } from '../services/api'
import { errorText } from '../services/errors'
import { usePageMeta } from '../hooks/usePageMeta'

export function SignInPage() {
  const { t } = useI18n()
  const { signIn } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  usePageMeta(t('auth.signin.title'), t('meta.signin.description'))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      // Back to the page the user was sent away from (PublicOnly redirects once the session exists).
      setPostAuthRedirect(safeNext(location.search))
      await signIn(email.trim(), password, remember)
    } catch (err) {
      const apiErr = toApiError(err)
      setError(apiErr.status === 401 ? t('auth.signin.failed') : errorText(t, apiErr))
      setPassword('')
      setBusy(false)
    }
  }

  return (
    <AuthShell title={t('auth.signin.title')} subtitle={t('auth.signin.subtitle')}
      footer={<>{t('auth.signin.noAccount')} <Link to="/signup" className="font-medium text-brand hover:text-brand-hover">{t('auth.signup.cta')}</Link></>}>
      <form onSubmit={submit} className="space-y-5" noValidate>
        {error && <Alert tone="error">{error}</Alert>}
        <Field label={t('auth.email')} htmlFor="email">
          <Input id="email" type="email" autoComplete="email" inputMode="email" required autoFocus value={email}
            onChange={(e) => setEmail(e.target.value)} placeholder="name@university.edu" maxLength={254} />
        </Field>
        <Field label={t('auth.password')} htmlFor="password">
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="current-password" />
        </Field>
        <label className="flex cursor-pointer items-center gap-2 text-sm text-fg-muted">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)}
            className="h-4 w-4 rounded border-line-strong accent-[var(--brand)]" />
          {t('auth.remember')}
        </label>
        <Button type="submit" size="lg" className="w-full" loading={busy} disabled={!email.trim() || !password}>
          {t('auth.signin.submit')} {!busy && <ArrowRight className="h-4 w-4 rtl:rotate-180" />}
        </Button>
      </form>
    </AuthShell>
  )
}
