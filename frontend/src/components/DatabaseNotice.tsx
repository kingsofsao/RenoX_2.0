import { RefreshCw } from 'lucide-react'
import { useHealth } from '../hooks/HealthContext'
import { useI18n } from '../i18n/I18nProvider'
import { Alert, Button } from './ui'

/** Explains why data is missing when the service or database is not usable. Renders nothing when healthy. */
export function DatabaseNotice() {
  const { t } = useI18n()
  const { health, error, refresh } = useHealth()
  const retry = <Button variant="secondary" size="sm" onClick={refresh}><RefreshCw className="h-3.5 w-3.5" />{t('common.retry')}</Button>

  if (error) return <Alert tone="error" title={t('health.offline.title')} action={retry}>{t('error.network')}</Alert>
  if (health && health.database.status !== 'connected') {
    return <Alert tone="error" title={t('error.unavailable.title')} action={retry}>{t('error.unavailable')}</Alert>
  }
  return null
}
