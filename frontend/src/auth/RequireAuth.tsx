import { useEffect, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { RefreshCw } from 'lucide-react'
import { Alert, Button, Logo } from '../components/ui'
import { HealthProvider } from '../hooks/HealthContext'
import { ProjectProvider, useProjects } from '../hooks/ProjectContext'
import { useI18n } from '../i18n/I18nProvider'
import { clearPostAuthRedirect, peekPostAuthRedirect, safeNext } from './redirect'
import { useAuth } from './AuthProvider'

export function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas">
      <div className="flex animate-fade-in flex-col items-center gap-4">
        <Logo className="h-10 w-10 animate-pulse" />
        <div className="h-1 w-32 overflow-hidden rounded-full bg-surface-3"><div className="h-full w-1/3 animate-indeterminate rounded-full bg-brand" /></div>
      </div>
    </div>
  )
}

/** Waits for the user's projects, so every page renders with a project the user owns. */
function ProjectGate({ children }: { children: ReactNode }) {
  const { t } = useI18n()
  const { loading, activeId, error, refresh } = useProjects()
  if (loading) return <FullScreenLoader />
  if (error || !activeId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-canvas p-6">
        <div className="w-full max-w-md">
          <Alert tone="error" title={t('error.unavailable.title')}
            action={<Button variant="secondary" size="sm" onClick={() => void refresh()}><RefreshCw className="h-4 w-4" />{t('common.retry')}</Button>}>
            {t('error.unavailable')}
          </Alert>
        </div>
      </div>
    )
  }
  return <>{children}</>
}

/** Only signed-in users get past this; everyone else is sent to the sign-in page and back afterwards.
 *  `landing` is shown instead to signed-out visitors of the home page "/". */
export function RequireAuth({ children, landing }: { children: ReactNode; landing?: ReactNode }) {
  const { status, user } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <FullScreenLoader />
  if ((status !== 'signed-in' || !user) && landing && location.pathname === '/') return <>{landing}</>
  if (status !== 'signed-in' || !user) {
    const next = location.pathname + location.search
    return <Navigate to={next && next !== '/' ? `/signin?next=${encodeURIComponent(next)}` : '/signin'} replace />
  }
  return <SignedIn userId={user.id}>{children}</SignedIn>
}

function SignedIn({ userId, children }: { userId: string; children: ReactNode }) {
  useEffect(() => clearPostAuthRedirect(), [])
  return (
    <ProjectProvider key={userId} userId={userId}>
      <ProjectGate>
        <HealthProvider>{children}</HealthProvider>
      </ProjectGate>
    </ProjectProvider>
  )
}

/** Sign-in and sign-up pages: a signed-in user goes straight to the app. */
export function PublicOnly({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <FullScreenLoader />
  if (status === 'signed-in') return <Navigate to={peekPostAuthRedirect() ?? safeNext(location.search)} replace />
  return <>{children}</>
}
