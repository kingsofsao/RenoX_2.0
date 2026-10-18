import { ArrowLeft } from 'lucide-react'
import { DisconnectedArt } from '../components/GraphArt'
import { ButtonLink } from '../components/ui'
import { useAuth } from '../auth/AuthProvider'
import { usePageMeta } from '../hooks/usePageMeta'
import { useI18n } from '../i18n/I18nProvider'

export default function NotFoundPage() {
  const { t } = useI18n()
  const { status } = useAuth()
  usePageMeta(t('notFound.title'), t('notFound.text'), { noindex: true })
  return (
    <section className="mx-auto flex max-w-xl flex-col items-center px-4 py-24 text-center sm:py-32">
      <DisconnectedArt className="h-auto w-64" />
      <p className="mt-8 text-sm font-semibold tracking-[0.14em] text-brand">404</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight text-fg">{t('notFound.title')}</h1>
      <p className="mt-3 text-fg-muted">{t('notFound.text')}</p>
      <ButtonLink to="/" className="mt-8"><ArrowLeft className="h-4 w-4 rtl:rotate-180" />
        {status === 'signed-in' ? t('notFound.back') : t('notFound.home')}
      </ButtonLink>
    </section>
  )
}
