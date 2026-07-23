import { useLocation } from 'react-router-dom'
import { useKb } from '@/context/KbContext'

const PAGE_TITLES = {
  '/': 'Overview',
  '/pipeline': 'Pipeline Architecture',
  '/drivers': 'Technology Drivers',
  '/bom': 'Bill of Materials',
  '/morphbox': 'Morphological Box',
  '/cib': 'Cross-Impact Balance',
  '/scenarios': 'Scenarios',
  '/landscape': 'Scenario Landscape',
  '/archetypes': 'Scenario Archetypes',
  '/embeddings': 'Embeddings Lab',
  '/strategy': 'Strategic Framing',
}

export default function TopBar() {
  const location = useLocation()
  const title = PAGE_TITLES[location.pathname] || ''
  const { kb, setKb, kbs } = useKb()

  return (
    <div className="h-11 flex items-center px-6 border-b border-white/[0.04] bg-zinc-950/50 backdrop-blur-sm">
      {kbs.length > 1 ? (
        <select
          value={kb}
          onChange={(e) => {
            setKb(e.target.value)
            e.target.blur() // release focus so arrow keys navigate pages again
          }}
          title="Switch knowledge base"
          className="text-xs font-medium text-emerald-300 bg-zinc-900 border border-white/10 rounded px-2 py-1 tracking-wide focus:outline-none focus:border-emerald-500 cursor-pointer"
        >
          {kbs.map((k) => (
            <option key={k.id} value={k.id} className="bg-zinc-900">
              {k.label}
            </option>
          ))}
        </select>
      ) : (
        <span className="text-xs font-medium text-zinc-500 uppercase tracking-widest">
          R&S Horizon 35
        </span>
      )}
      <span className="mx-3 text-zinc-800">/</span>
      <span className="text-xs font-medium text-zinc-400">{title}</span>
    </div>
  )
}
