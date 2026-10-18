import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { setPostAuthRedirect } from '../auth/redirect'
import { AuthShell } from '../components/AuthShell'
import { PasswordInput, PasswordStrength, passwordChecks } from '../components/PasswordField'
import { Alert, Button, Field, Input } from '../components/ui'
import { useI18n } from '../i18n/I18nProvider'
import { api, toApiError } from '../services/api'
import { track } from '../services/analytics'
import { errorText } from '../services/errors'
import { usePageMeta } from '../hooks/usePageMeta'

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function SignUpPage() {
  const { t } = useI18n()
  const { signUp } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [touched, setTouched] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [challenge, setChallenge] = useState('')
  const [website, setWebsite] = useState('')  // honeypot, invisible to people
  const newChallenge = () => api.formChallenge().then((r) => setChallenge(r.challenge)).catch(() => undefined)
  useEffect(() => { void newChallenge() }, [])
  usePageMeta(t('auth.signup.title'), t('meta.signup.description'))

  const emailOk = EMAIL.test(email.trim())
  const rulesOk = passwordChecks(password, email, name).every((c) => c.ok)
  const matches = password === confirm
  const valid = name.trim().length > 0 && emailOk && rulesOk && matches

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (!valid || busy) return
    setBusy(true)
    setError(null)
    try {
      setPostAuthRedirect('/upload')  // a new account starts by adding its first paper
      await signUp({ email: email.trim(), password, name: name.trim(), challenge, website })
      track('signup', '/signup')
    } catch (err) {
      const apiErr = toApiError(err)
      if (apiErr.status === 400) void newChallenge()
      setError(apiErr.status === 409 ? t('auth.signup.exists') : apiErr.status === 403 ? t('auth.signup.closed')
        : apiErr.status === 400 ? t('form.expired') : errorText(t, apiErr))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title={t('auth.signup.title')} subtitle={t('auth.signup.subtitle')}
      footer={<>{t('auth.signup.haveAccount')} <Link to="/signin" className="font-medium text-brand hover:text-brand-hover">{t('auth.signin.cta')}</Link></>}>
      <form onSubmit={submit} className="space-y-5" noValidate>
        {error && <Alert tone="error">{error}</Alert>}
        <Field label={t('auth.name')} htmlFor="name" error={touched && !name.trim() ? t('auth.name.required') : null}>
          <Input id="name" autoComplete="name" required autoFocus value={name} maxLength={80}
            onChange={(e) => setName(e.target.value)} aria-invalid={(touched && !name.trim()) || undefined} />
        </Field>
        <Field label={t('auth.email')} htmlFor="email" error={touched && !emailOk ? t('auth.email.invalid') : null}>
          <Input id="email" type="email" autoComplete="email" inputMode="email" required value={email} maxLength={254}
            onChange={(e) => setEmail(e.target.value)} placeholder="name@university.edu" aria-invalid={(touched && !emailOk) || undefined} />
        </Field>
        <Field label={t('auth.password')} htmlFor="password">
          <PasswordInput id="password" value={password} onChange={setPassword} autoComplete="new-password" invalid={touched && !rulesOk} />
          <div className="pt-1"><PasswordStrength password={password} email={email} name={name} /></div>
        </Field>
        <Field label={t('auth.password.confirm')} htmlFor="confirm" error={touched && confirm && !matches ? t('auth.password.mismatch') : null}>
          <PasswordInput id="confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" invalid={touched && !matches} />
        </Field>
        {/* Honeypot: hidden from people and assistive technology; bots that fill it are refused. */}
        <div aria-hidden className="absolute -start-[10000px] h-px w-px overflow-hidden">
          <label htmlFor="website">Website</label>
          <input id="website" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
        </div>
        <Button type="submit" size="lg" className="w-full" loading={busy}>
          {t('auth.signup.submit')} {!busy && <ArrowRight className="h-4 w-4 rtl:rotate-180" />}
        </Button>
        <p className="text-center text-xs leading-relaxed text-fg-subtle">
          {t('auth.signup.agree.before')} <Link to="/terms" className="font-medium text-brand hover:underline">{t('legal.terms')}</Link> {t('auth.signup.agree.and')} <Link to="/privacy" className="font-medium text-brand hover:underline">{t('legal.privacy')}</Link>{t('auth.signup.agree.after')}
        </p>
      </form>
    </AuthShell>
  )
}
