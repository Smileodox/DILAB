import { Routes, Route } from 'react-router-dom'
import Shell from '@/components/layout/Shell'
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

// Renders the page only if the active KB has data for this route; else a graceful fallback.
function Guarded({ path, children }) {
  const { kb, kbs } = useKb()
  const cur = kbs.find((k) => k.id === kb)
  if (cur?.views && !cur.views.includes(path)) return <NotForThisKb />
  return children
}

export default function App() {
  return (
    <KbProvider>
      <Shell>
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
        </Routes>
      </Shell>
    </KbProvider>
  )
}
