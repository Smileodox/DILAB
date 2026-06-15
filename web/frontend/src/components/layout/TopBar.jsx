import { useLocation } from 'react-router-dom'

const PAGE_TITLES = {
  '/': 'Overview',
  '/pipeline': 'Pipeline Architecture',
  '/drivers': 'Technology Drivers',
  '/bom': 'Bill of Materials',
  '/morphbox': 'Morphological Box',
  '/cib': 'Cross-Impact Balance',
  '/scenarios': 'Scenarios',
  '/landscape': 'Scenario Landscape',
  '/embeddings': 'Embeddings Lab',
  '/strategy': 'Strategic Framing',
}

export default function TopBar() {
  const location = useLocation()
  const title = PAGE_TITLES[location.pathname] || ''

  return (
    <div className="h-11 flex items-center px-6 border-b border-white/[0.04] bg-zinc-950/50 backdrop-blur-sm">
      <span className="text-xs font-medium text-zinc-500 uppercase tracking-widest">
        R&S Horizon 35
      </span>
      <span className="mx-3 text-zinc-800">/</span>
      <span className="text-xs font-medium text-zinc-400">{title}</span>
    </div>
  )
}
