import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthProvider'
import { PublicOnly, RequireAuth } from './auth/RequireAuth'
import { Layout } from './components/Layout'
import { LoadingBlock } from './components/ui'
import { I18nProvider } from './i18n/I18nProvider'
import { DashboardPage } from './pages/DashboardPage'
import { InvestigatePage } from './pages/InvestigatePage'
import { LibraryPage } from './pages/LibraryPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PaperDetailPage } from './pages/PaperDetailPage'
import { ProjectsPage } from './pages/ProjectsPage'
import { SettingsPage } from './pages/SettingsPage'
import { SignInPage } from './pages/SignInPage'
import { SignUpPage } from './pages/SignUpPage'
import { UploadPage } from './pages/UploadPage'
import { ThemeProvider } from './theme/ThemeProvider'

// React Flow is large; load it only when the graph page is opened.
const GraphPage = lazy(() => import('./pages/GraphPage'))

export default function App() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="signin" element={<PublicOnly><SignInPage /></PublicOnly>} />
              <Route path="signup" element={<PublicOnly><SignUpPage /></PublicOnly>} />
              <Route element={<RequireAuth><Layout /></RequireAuth>}>
                <Route index element={<DashboardPage />} />
                <Route path="investigate" element={<InvestigatePage />} />
                <Route path="library" element={<LibraryPage />} />
                <Route path="upload" element={<UploadPage />} />
                <Route path="papers/:paperId" element={<PaperDetailPage />} />
                <Route path="graph" element={<Suspense fallback={<LoadingBlock />}><GraphPage /></Suspense>} />
                <Route path="projects" element={<ProjectsPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </I18nProvider>
    </ThemeProvider>
  )
}
