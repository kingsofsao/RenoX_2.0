import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthProvider'
import { FullScreenLoader, PublicOnly, RequireAuth } from './auth/RequireAuth'
import { ConsentBanner } from './components/ConsentBanner'
import { ContactWidget } from './components/ContactWidget'
import { Layout } from './components/Layout'
import { PublicLayout } from './components/PublicLayout'
import { BackToTop, ScrollProgress } from './components/ScrollAids'
import { LoadingBlock } from './components/ui'
import { I18nProvider } from './i18n/I18nProvider'
import { CONSENT_EVENT, captureUtm, track } from './services/analytics'
import { ThemeProvider } from './theme/ThemeProvider'

// Every page is its own chunk: visitors to the public pages never download the app, and vice versa.
const LandingPage = lazy(() => import('./pages/LandingPage'))
const LegalPage = lazy(() => import('./pages/LegalPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))
const SignInPage = lazy(() => import('./pages/SignInPage').then((m) => ({ default: m.SignInPage })))
const SignUpPage = lazy(() => import('./pages/SignUpPage').then((m) => ({ default: m.SignUpPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const InvestigatePage = lazy(() => import('./pages/InvestigatePage').then((m) => ({ default: m.InvestigatePage })))
const LibraryPage = lazy(() => import('./pages/LibraryPage').then((m) => ({ default: m.LibraryPage })))
const UploadPage = lazy(() => import('./pages/UploadPage').then((m) => ({ default: m.UploadPage })))
const PaperDetailPage = lazy(() => import('./pages/PaperDetailPage').then((m) => ({ default: m.PaperDetailPage })))
const ProjectsPage = lazy(() => import('./pages/ProjectsPage').then((m) => ({ default: m.ProjectsPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })))
const GraphPage = lazy(() => import('./pages/GraphPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))

/** Counts a page view on every navigation (only if the visitor allowed statistics) and keeps UTM tags. */
function RouteTracker() {
  const location = useLocation()
  useEffect(() => { captureUtm(location.search) }, [location.search])
  useEffect(() => { track('page_view', location.pathname) }, [location.pathname])
  useEffect(() => {
    const onConsent = (e: Event) => { if ((e as CustomEvent).detail === 'granted') track('page_view', window.location.pathname) }
    window.addEventListener(CONSENT_EVENT, onConsent)
    return () => window.removeEventListener(CONSENT_EVENT, onConsent)
  }, [])
  // Move to the top on navigation, unless the URL points at a section (#faq).
  useEffect(() => { if (!location.hash) window.scrollTo(0, 0) }, [location.pathname, location.hash])
  return null
}

function Page({ children }: { children: React.ReactNode }) {
  // The placeholder fills the screen, so the footer does not jump when the page arrives (no layout shift).
  return <Suspense fallback={<div className="min-h-svh"><LoadingBlock rows={5} /></div>}>{children}</Suspense>
}

function Chrome() {
  const { status } = useAuth()
  if (status === 'loading') return null
  return (
    <>
      <ScrollProgress />
      <BackToTop />
      <ContactWidget />
      <ConsentBanner />
    </>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <AuthProvider>
          <BrowserRouter>
            <RouteTracker />
            <Suspense fallback={<FullScreenLoader />}>
              <Routes>
                <Route path="signin" element={<PublicOnly><SignInPage /></PublicOnly>} />
                <Route path="signup" element={<PublicOnly><SignUpPage /></PublicOnly>} />
                <Route element={<PublicLayout />}>
                  <Route path="privacy" element={<Page><LegalPage doc="privacy" /></Page>} />
                  <Route path="terms" element={<Page><LegalPage doc="terms" /></Page>} />
                </Route>
                {/* Signed-out visitors to "/" see the public home page; everything else here needs an account. */}
                <Route element={<RequireAuth landing={<PublicLayout><Page><LandingPage /></Page></PublicLayout>}><Layout /></RequireAuth>}>
                  <Route index element={<Page><DashboardPage /></Page>} />
                  <Route path="investigate" element={<Page><InvestigatePage /></Page>} />
                  <Route path="library" element={<Page><LibraryPage /></Page>} />
                  <Route path="upload" element={<Page><UploadPage /></Page>} />
                  <Route path="papers/:paperId" element={<Page><PaperDetailPage /></Page>} />
                  <Route path="graph" element={<Page><GraphPage /></Page>} />
                  <Route path="projects" element={<Page><ProjectsPage /></Page>} />
                  <Route path="settings" element={<Page><SettingsPage /></Page>} />
                  <Route path="admin" element={<Page><AdminPage /></Page>} />
                </Route>
                <Route path="*" element={<PublicLayout><Page><NotFoundPage /></Page></PublicLayout>} />
              </Routes>
            </Suspense>
            <Chrome />
          </BrowserRouter>
        </AuthProvider>
      </I18nProvider>
    </ThemeProvider>
  )
}
