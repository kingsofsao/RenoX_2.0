import { Compass } from 'lucide-react'
import { ButtonLink, EmptyState } from '../components/ui'
import { useI18n } from '../i18n/I18nProvider'

export function NotFoundPage() {
  const { t } = useI18n()
  return (
    <EmptyState icon={<Compass className="h-6 w-6" />} title={t('notFound.title')} description={t('notFound.text')}
      action={<ButtonLink to="/">{t('notFound.back')}</ButtonLink>} />
  )
}
