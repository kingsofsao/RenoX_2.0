import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { HealthProvider } from './hooks/HealthContext'
import { ProjectProvider } from './hooks/ProjectContext'
import { ProjectsPage } from './pages/ProjectsPage'
import { DashboardPage } from './pages/DashboardPage'
import { InvestigatePage } from './pages/InvestigatePage'
import { LibraryPage } from './pages/LibraryPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PaperDetailPage } from './pages/PaperDetailPage'
import { UploadPage } from './pages/UploadPage'
import { LoadingBlock } from './components/ui'

// React Flow is large; load it only when the graph page is opened.
const GraphPage = lazy(() => import('./pages/GraphPage'))

export default function App() {
  return (
    <HealthProvider>
      <ProjectProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="library" element={<LibraryPage />} />
            <Route path="upload" element={<UploadPage />} />
            <Route path="papers/:paperId" element={<PaperDetailPage />} />
            <Route path="graph" element={<Suspense fallback={<LoadingBlock label="Loading graph view…" />}><GraphPage /></Suspense>} />
            <Route path="investigate" element={<InvestigatePage />} />
            <Route path="projects" element={<ProjectsPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
      </ProjectProvider>
    </HealthProvider>
  )
}
