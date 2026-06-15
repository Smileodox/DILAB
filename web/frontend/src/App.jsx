import { Routes, Route } from 'react-router-dom'
import Shell from '@/components/layout/Shell'
import OverviewPage from '@/pages/OverviewPage'
import DriversPage from '@/pages/DriversPage'
import BOMPage from '@/pages/BOMPage'
import MorphBoxPage from '@/pages/MorphBoxPage'
import CIBPage from '@/pages/CIBPage'
import ScenariosPage from '@/pages/ScenariosPage'
import LandscapePage from '@/pages/LandscapePage'
import StrategyPage from '@/pages/StrategyPage'
import PipelinePage from '@/pages/PipelinePage'
import EmbeddingsLabPage from '@/pages/EmbeddingsLabPage'

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/pipeline" element={<PipelinePage />} />
        <Route path="/drivers" element={<DriversPage />} />
        <Route path="/bom" element={<BOMPage />} />
        <Route path="/morphbox" element={<MorphBoxPage />} />
        <Route path="/cib" element={<CIBPage />} />
        <Route path="/scenarios" element={<ScenariosPage />} />
        <Route path="/landscape" element={<LandscapePage />} />
        <Route path="/embeddings" element={<EmbeddingsLabPage />} />
        <Route path="/strategy" element={<StrategyPage />} />
      </Routes>
    </Shell>
  )
}
