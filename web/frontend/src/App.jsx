import { Component } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Shell from '@/components/layout/Shell'
import PresentShell from '@/present/PresentShell'
import { KbProvider, useKb } from '@/context/KbContext'
import NotForThisKb from '@/components/ui/NotForThisKb'
import OverviewPage from '@/pages/OverviewPage'
import DriversPage from '@/pages/DriversPage'
import BOMPage from '@/pages/BOMPage'
import MorphBoxPage from '@/pages/MorphBoxPage'
import CIBPage from '@/pages/CIBPage'
import ScenariosPage from '@/pages/ScenariosPage'
import LandscapePage from '@/pages/LandscapePage'
import ArchetypesPage from '@/pages/ArchetypesPage'
import StrategyPage from '@/pages/StrategyPage'
import PipelinePage from '@/pages/PipelinePage'
import EmbeddingsLabPage from '@/pages/EmbeddingsLabPage'
import MethodologyPage from '@/pages/MethodologyPage'

// Catches render errors anywhere below so a single broken page never white-screens the app.
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 max-w-md text-center">
          <h2 className="text-lg font-semibold text-zinc-100 mb-2">Something went wrong</h2>
          <p className="text-sm text-zinc-400 mb-6">This view hit an unexpected error. Reloading usually fixes it.</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-medium text-white"
          >
            Reload
          </button>
        </div>
      </div>
    )
  }
}

// Keyed by pathname so navigating away from a crashed page clears the error state.
function RouteErrorBoundary({ children }) {
  const location = useLocation()
  return <ErrorBoundary key={location.pathname}>{children}</ErrorBoundary>
}

// Renders the page only if the active KB has data for this route; else a graceful fallback.
function Guarded({ path, children }) {
  const { kb, kbs } = useKb()
  const cur = kbs.find((k) => k.id === kb)
  if (cur?.views && !cur.views.includes(path)) return <NotForThisKb />
  return children
}

export default function App() {
  const location = useLocation()

  // Presentation mode renders fullscreen without the dashboard chrome.
  if (location.pathname.startsWith('/present')) {
    return (
      <KbProvider>
        <ErrorBoundary>
          <Routes>
            <Route path="/present" element={<PresentShell />} />
          </Routes>
        </ErrorBoundary>
      </KbProvider>
    )
  }

  return (
    <KbProvider>
      <Shell>
        <RouteErrorBoundary>
        <Routes>
          <Route path="/" element={<Guarded path="/"><OverviewPage /></Guarded>} />
          <Route path="/pipeline" element={<Guarded path="/pipeline"><PipelinePage /></Guarded>} />
          <Route path="/drivers" element={<Guarded path="/drivers"><DriversPage /></Guarded>} />
          <Route path="/bom" element={<Guarded path="/bom"><BOMPage /></Guarded>} />
          <Route path="/morphbox" element={<Guarded path="/morphbox"><MorphBoxPage /></Guarded>} />
          <Route path="/cib" element={<Guarded path="/cib"><CIBPage /></Guarded>} />
          <Route path="/scenarios" element={<Guarded path="/scenarios"><ScenariosPage /></Guarded>} />
          <Route path="/landscape" element={<Guarded path="/landscape"><LandscapePage /></Guarded>} />
          <Route path="/archetypes" element={<Guarded path="/archetypes"><ArchetypesPage /></Guarded>} />
          <Route path="/embeddings" element={<Guarded path="/embeddings"><EmbeddingsLabPage /></Guarded>} />
          <Route path="/strategy" element={<Guarded path="/strategy"><StrategyPage /></Guarded>} />
          {/* Static content — needs no KB data, so deliberately unguarded. */}
          <Route path="/methodology" element={<MethodologyPage />} />
        </Routes>
        </RouteErrorBoundary>
      </Shell>
    </KbProvider>
  )
}
