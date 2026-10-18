import { useEffect, useState, type FormEvent } from 'react'
import { CheckCircle2, MessageSquare } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { SITE } from '../config/site'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { api, toApiError } from '../services/api'
import { errorText } from '../services/errors'
import { Modal } from './Modal'
import { Alert, Button, Field, Input, Select, Textarea } from './ui'

export const OPEN_CONTACT_EVENT = 'researchmind:open-contact'
export function openContact(): void {
  window.dispatchEvent(new Event(OPEN_CONTACT_EVENT))
}

const TOPICS: { value: string; label: MessageKey }[] = [
  { value: 'question', label: 'contact.topic.question' },
  { value: 'feedback', label: 'contact.topic.feedback' },
  { value: 'bug', label: 'contact.topic.bug' },
  { value: 'privacy', label: 'contact.topic.privacy' },
]
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function ContactForm({ onDone }: { onDone: () => void }) {
  const { t } = useI18n()
  const { user } = useAuth()
  const [name, setName] = useState(user?.name ?? '')
  const [email, setEmail] = useState(user?.email ?? '')
  const [topic, setTopic] = useState('question')
  const [message, setMessage] = useState('')
  const [website, setWebsite] = useState('')  // honeypot, invisible to people
  const [challenge, setChallenge] = useState('')
  const [touched, setTouched] = useState(false)
  const [state, setState] = useState<'idle' | 'sending' | 'sent'>('idle')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { api.formChallenge().then((r) => setChallenge(r.challenge)).catch(() => undefined) }, [])

  const errors = {
    name: !name.trim() ? t('auth.name.required') : null,
    email: !EMAIL.test(email.trim()) ? t('auth.email.invalid') : null,
    message: message.trim().length < 10 ? t('contact.message.short') : null,
  }
  const valid = !errors.name && !errors.email && !errors.message

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setTouched(true)
    if (!valid || state === 'sending') return
    setState('sending')
    setError(null)
    try {
      await api.contact({ name: name.trim(), email: email.trim(), topic, message: message.trim(), challenge, website })
      setState('sent')
    } catch (err) {
      const apiErr = toApiError(err)
      if (apiErr.status === 400) api.formChallenge().then((r) => setChallenge(r.challenge)).catch(() => undefined)
      setError(apiErr.status === 400 ? t('form.expired') : errorText(t, apiErr))
      setState('idle')
    }
  }

  if (state === 'sent') {
    return (
      <div className="flex flex-col items-center py-6 text-center" role="status">
        <span className="mb-3 rounded-full bg-ok-soft p-3 text-ok"><CheckCircle2 className="h-6 w-6" /></span>
        <p className="font-medium text-fg">{t('contact.sent.title')}</p>
        <p className="mt-1 max-w-sm text-sm text-fg-muted">{t('contact.sent.text')}</p>
        <Button variant="secondary" className="mt-5" onClick={onDone}>{t('common.close')}</Button>
      </div>
    )
  }

  return (
    <form id="contact-form" onSubmit={submit} className="space-y-4" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('auth.name')} htmlFor="c-name" error={touched ? errors.name : null}>
          <Input id="c-name" value={name} maxLength={80} autoComplete="name" onChange={(e) => setName(e.target.value)}
            aria-invalid={(touched && !!errors.name) || undefined} data-autofocus />
        </Field>
        <Field label={t('auth.email')} htmlFor="c-email" error={touched ? errors.email : null}>
          <Input id="c-email" type="email" value={email} maxLength={254} autoComplete="email" onChange={(e) => setEmail(e.target.value)}
            aria-invalid={(touched && !!errors.email) || undefined} />
        </Field>
      </div>
      <Field label={t('contact.topic')} htmlFor="c-topic">
        <Select id="c-topic" value={topic} onChange={(e) => setTopic(e.target.value)}>
          {TOPICS.map((x) => <option key={x.value} value={x.value}>{t(x.label)}</option>)}
        </Select>
      </Field>
      <Field label={t('contact.message')} htmlFor="c-message" error={touched ? errors.message : null}
        hint={`${message.trim().length}/3000`}>
        <Textarea id="c-message" rows={5} value={message} maxLength={3000} onChange={(e) => setMessage(e.target.value)}
          aria-invalid={(touched && !!errors.message) || undefined} />
      </Field>
      {/* Honeypot: hidden from people and assistive technology; bots that fill it are silently ignored. */}
      <div aria-hidden className="absolute -start-[10000px] h-px w-px overflow-hidden">
        <label htmlFor="c-website">Website</label>
        <input id="c-website" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
      </div>
      <p className="text-xs text-fg-subtle">{t('contact.privacy')}</p>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onDone}>{t('common.cancel')}</Button>
        <Button type="submit" loading={state === 'sending'}>{t('contact.send')}</Button>
      </div>
    </form>
  )
}

/** Floating "Contact" button (bottom corner) and the contact form dialog it opens. */
export function ContactWidget() {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [key, setKey] = useState(0)
  useEffect(() => {
    const show = () => { setKey((k) => k + 1); setOpen(true) }
    window.addEventListener(OPEN_CONTACT_EVENT, show)
    return () => window.removeEventListener(OPEN_CONTACT_EVENT, show)
  }, [])
  return (
    <>
      <button type="button" onClick={openContact}
        className="fixed bottom-4 end-4 z-40 inline-flex items-center gap-2 rounded-lg bg-fg px-3.5 py-2.5 text-sm font-medium text-canvas shadow-pop transition-all duration-150 hover:-translate-y-0.5 active:scale-95 sm:end-6 print:hidden">
        <MessageSquare className="h-4 w-4" aria-hidden /> <span>{t('contact.button')}</span>
      </button>
      <Modal open={open} onClose={() => setOpen(false)} size="lg" title={t('contact.title')}
        description={SITE.contactEmail ? t('contact.subtitle.email', { email: SITE.contactEmail }) : t('contact.subtitle')}>
        <div className="pb-5"><ContactForm key={key} onDone={() => setOpen(false)} /></div>
      </Modal>
    </>
  )
}
