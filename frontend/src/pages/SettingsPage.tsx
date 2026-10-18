import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Check, KeyRound, Laptop, LogOut, Monitor, Moon, Palette, Sun, Trash2, UserRound } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { ConfirmDialog } from '../components/Modal'
import { openCookieSettings } from '../components/ConsentBanner'
import { PasswordInput, PasswordStrength, passwordChecks } from '../components/PasswordField'
import { usePageMeta } from '../hooks/usePageMeta'
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Select, cx } from '../components/ui'
import { useI18n } from '../i18n/I18nProvider'
import { LANGUAGES, isLang } from '../i18n/languages'
import { api, toApiError } from '../services/api'
import { errorText } from '../services/errors'
import { useTheme } from '../theme/ThemeProvider'
import type { SessionInfo, ThemeSetting } from '../types/api'

function Section({ icon, title, subtitle, children }: { icon: ReactNode; title: string; subtitle?: string; children: ReactNode }) {
  return (
    <Card className="animate-fade-up">
      <CardHeader title={<span className="flex items-center gap-2"><span className="text-brand">{icon}</span>{title}</span>} subtitle={subtitle} />
      <div className="p-5">{children}</div>
    </Card>
  )
}

function ProfileSection() {
  const { t, formatDate } = useI18n()
  const { user, updateProfile } = useAuth()
  const [name, setName] = useState(user?.name ?? '')
  const [state, setState] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [error, setError] = useState<string | null>(null)
  if (!user) return null
  const save = async (e: FormEvent) => {
    e.preventDefault()
    setState('saving'); setError(null)
    try { await updateProfile({ name: name.trim() }); setState('saved') } catch (err) { setError(errorText(t, err)); setState('idle') }
  }
  return (
    <Section icon={<UserRound className="h-4 w-4" />} title={t('settings.profile')} subtitle={t('settings.profile.subtitle')}>
      <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
        <Field label={t('auth.name')} htmlFor="s-name">
          <Input id="s-name" value={name} maxLength={80} onChange={(e) => { setName(e.target.value); setState('idle') }} autoComplete="name" />
        </Field>
        <Field label={t('auth.email')} htmlFor="s-email" hint={t('settings.email.hint')}>
          <Input id="s-email" value={user.email} disabled readOnly />
        </Field>
        <div className="flex items-center gap-3 sm:col-span-2">
          <Button type="submit" loading={state === 'saving'} disabled={!name.trim() || name.trim() === user.name}>{t('common.save')}</Button>
          {state === 'saved' && <span className="inline-flex animate-fade-in items-center gap-1 text-sm text-ok-fg"><Check className="h-4 w-4" />{t('common.saved')}</span>}
          <span className="ms-auto text-xs text-fg-subtle">{t('settings.memberSince', { date: formatDate(user.created_at, { dateStyle: 'long' }) })}</span>
        </div>
        {error && <div className="sm:col-span-2"><Alert tone="error">{error}</Alert></div>}
      </form>
    </Section>
  )
}

function AppearanceSection() {
  const { t, lang } = useI18n()
  const { setting } = useTheme()
  const { setTheme, setLanguage } = useAuth()
  const options: { value: ThemeSetting; icon: ReactNode; preview: string }[] = [
    { value: 'light', icon: <Sun className="h-4 w-4" />, preview: 'bg-white border-[#e3e6eb]' },
    { value: 'dark', icon: <Moon className="h-4 w-4" />, preview: 'bg-[#101216] border-[#242831]' },
    { value: 'system', icon: <Monitor className="h-4 w-4" />, preview: 'bg-gradient-to-br from-white from-50% to-[#101216] to-50% border-[#cdd2da]' },
  ]
  return (
    <Section icon={<Palette className="h-4 w-4" />} title={t('settings.appearance')} subtitle={t('settings.appearance.subtitle')}>
      <div className="space-y-6">
        <div>
          <p className="mb-2 text-sm font-medium text-fg">{t('settings.theme')}</p>
          <div role="radiogroup" aria-label={t('settings.theme')} className="grid gap-3 sm:grid-cols-3">
            {options.map((o) => {
              const active = setting === o.value
              return (
                <button key={o.value} type="button" role="radio" aria-checked={active} onClick={() => setTheme(o.value)}
                  className={cx('group rounded-xl border p-3 text-start transition-all duration-150 hover:-translate-y-0.5 active:scale-[0.98]',
                    active ? 'border-brand ring-2 ring-brand/25' : 'border-line hover:border-line-strong')}>
                  <div className={cx('mb-3 h-16 rounded-lg border', o.preview)}>
                    <div className="m-2 h-2 w-10 rounded-full bg-[#1c69d4]" />
                  </div>
                  <span className="flex items-center justify-between text-sm font-medium text-fg">
                    <span className="flex items-center gap-2">{o.icon}{t(`theme.${o.value}`)}</span>
                    {active && <Check className="h-4 w-4 text-brand" />}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
        <div>
          <p className="mb-1 text-sm font-medium text-fg">{t('consent.settings')}</p>
          <p className="mb-2 text-xs text-fg-subtle">{t('settings.cookies.hint')}</p>
          <Button variant="secondary" size="sm" onClick={openCookieSettings}>{t('settings.cookies.change')}</Button>
        </div>
        <Field label={t('settings.language')} htmlFor="s-lang" hint={t('settings.language.hint')}>
          <Select id="s-lang" value={lang} onChange={(e) => { if (isLang(e.target.value)) setLanguage(e.target.value) }} className="sm:max-w-xs">
            {LANGUAGES.map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
          </Select>
        </Field>
      </div>
    </Section>
  )
}

function PasswordSection() {
  const { t } = useI18n()
  const { user } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const valid = current && passwordChecks(next, user?.email, user?.name).every((c) => c.ok) && next === confirm && next !== current
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!valid) return
    setBusy(true); setError(null); setDone(false)
    try {
      await api.changePassword(current, next)
      setDone(true); setCurrent(''); setNext(''); setConfirm('')
    } catch (err) {
      const apiErr = toApiError(err)
      setError(apiErr.status === 403 ? t('settings.password.wrong') : errorText(t, apiErr))
    } finally { setBusy(false) }
  }
  return (
    <Section icon={<KeyRound className="h-4 w-4" />} title={t('settings.password')} subtitle={t('settings.password.subtitle')}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
        {done && <div className="sm:col-span-2"><Alert tone="success">{t('settings.password.changed')}</Alert></div>}
        {error && <div className="sm:col-span-2"><Alert tone="error">{error}</Alert></div>}
        <div className="sm:col-span-2 sm:max-w-sm">
          <Field label={t('settings.password.current')} htmlFor="p-current">
            <PasswordInput id="p-current" value={current} onChange={setCurrent} autoComplete="current-password" />
          </Field>
        </div>
        <Field label={t('settings.password.new')} htmlFor="p-new">
          <PasswordInput id="p-new" value={next} onChange={setNext} autoComplete="new-password" />
          <div className="pt-1"><PasswordStrength password={next} email={user?.email} name={user?.name} /></div>
        </Field>
        <Field label={t('auth.password.confirm')} htmlFor="p-confirm" error={confirm && next !== confirm ? t('auth.password.mismatch') : null}>
          <PasswordInput id="p-confirm" value={confirm} onChange={setConfirm} autoComplete="new-password" invalid={!!confirm && next !== confirm} />
        </Field>
        <div className="sm:col-span-2"><Button type="submit" loading={busy} disabled={!valid}>{t('settings.password.submit')}</Button></div>
      </form>
    </Section>
  )
}

function describeAgent(ua: string): string {
  const browser = /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : null
  const os = /Windows/.test(ua) ? 'Windows' : /Mac OS X/.test(ua) ? 'macOS' : /Android/.test(ua) ? 'Android' : /iPhone|iPad/.test(ua) ? 'iOS' : /Linux/.test(ua) ? 'Linux' : null
  return [browser, os].filter(Boolean).join(' · ')
}

function SessionsSection() {
  const { t, formatDate } = useI18n()
  const [sessions, setSessions] = useState<SessionInfo[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [asking, setAsking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const load = () => api.listSessions().then((r) => setSessions(r.sessions)).catch((err) => setError(errorText(t, err)))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void load() }, [])
  const others = (sessions ?? []).filter((s) => !s.current).length
  const revoke = async () => {
    setBusy(true); setError(null)
    try { await api.signOutOtherSessions(); await load() } catch (err) { setError(errorText(t, err)) } finally { setBusy(false); setAsking(false) }
  }
  return (
    <Section icon={<Laptop className="h-4 w-4" />} title={t('settings.sessions')} subtitle={t('settings.sessions.subtitle')}>
      {error && <Alert tone="error" className="mb-3">{error}</Alert>}
      <ul className="divide-y divide-line rounded-lg border border-line">
        {(sessions ?? []).map((s) => (
          <li key={s.id} className="flex items-center gap-3 px-4 py-3 text-sm">
            <Laptop className="h-4 w-4 shrink-0 text-fg-subtle" />
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-fg">{describeAgent(s.user_agent) || t('settings.sessions.unknownDevice')}</p>
              <p className="text-xs text-fg-subtle">{t('settings.sessions.lastActive', { date: formatDate(s.last_seen_at) })}</p>
            </div>
            {s.current && <Badge tone="brand">{t('settings.sessions.current')}</Badge>}
          </li>
        ))}
        {sessions === null && <li className="px-4 py-3"><div className="skeleton h-4 w-1/2" /></li>}
      </ul>
      <Button variant="secondary" className="mt-4" onClick={() => setAsking(true)} disabled={!others}>
        <LogOut className="h-4 w-4" /> {t('settings.sessions.revoke')}
      </Button>
      <ConfirmDialog open={asking} onCancel={() => setAsking(false)} onConfirm={() => void revoke()} busy={busy}
        title={t('settings.sessions.revoke')} description={t('settings.sessions.confirm')} confirmLabel={t('settings.sessions.revoke.short')} />
    </Section>
  )
}

function DangerSection() {
  const { t } = useI18n()
  const { replaceUser } = useAuth()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const word = t('settings.delete.word')
  const submit = async () => {
    setBusy(true); setError(null)
    try {
      await api.deleteAccount(password)
      replaceUser(null)
      navigate('/signin', { replace: true })
    } catch (err) {
      const apiErr = toApiError(err)
      setError(apiErr.status === 403 ? t('settings.password.wrong') : errorText(t, apiErr))
      setBusy(false)
    }
  }
  return (
    <Card className="animate-fade-up border-bad/30">
      <CardHeader title={<span className="flex items-center gap-2 text-bad-fg"><Trash2 className="h-4 w-4" />{t('settings.delete')}</span>}
        subtitle={t('settings.delete.subtitle')} />
      <div className="p-5">
        <Button variant="danger" onClick={() => setOpen(true)}>{t('settings.delete.start')}</Button>
        <ConfirmDialog open={open} onCancel={() => { setOpen(false); setPassword(''); setConfirm(''); setError(null) }}
          onConfirm={() => void submit()} title={t('settings.delete')} description={t('settings.delete.warning')}
          confirmLabel={t('settings.delete.confirm')} busy={busy} error={error}
          disabled={!password || confirm.trim().toLowerCase() !== word.toLowerCase()}>
          <Field label={t('auth.password')} htmlFor="d-password">
            <PasswordInput id="d-password" value={password} onChange={setPassword} autoComplete="current-password" />
          </Field>
          <Field label={t('settings.delete.type', { word })} htmlFor="d-confirm">
            <Input id="d-confirm" value={confirm} onChange={(e) => setConfirm(e.target.value)} autoComplete="off" />
          </Field>
        </ConfirmDialog>
      </div>
    </Card>
  )
}

export function SettingsPage() {
  const { t } = useI18n()
  usePageMeta(t('settings.title'), undefined, { noindex: true })
  return (
    <>
      <PageHeader title={t('settings.title')} description={t('settings.description')} />
      <div className="grid gap-6">
        <ProfileSection />
        <AppearanceSection />
        <PasswordSection />
        <SessionsSection />
        <DangerSection />
      </div>
    </>
  )
}
