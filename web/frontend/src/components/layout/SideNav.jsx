import { NavLink, useLocation } from 'react-router-dom'
import {
  LayoutDashboard, Workflow, Zap, Network, Grid3X3, GitBranch,
  Globe, Map, Atom, Target, ChevronLeft, ChevronRight,
} from 'lucide-react'
import { useState } from 'react'

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/pipeline', label: 'Pipeline', icon: Workflow },
  { path: '/drivers', label: 'Drivers', icon: Zap },
  { path: '/bom', label: 'BOM', icon: GitBranch },
  { path: '/morphbox', label: 'Morph Box', icon: Grid3X3 },
  { path: '/cib', label: 'CIB', icon: Network },
  { path: '/scenarios', label: 'Scenarios', icon: Globe },
  { path: '/landscape', label: 'Landscape', icon: Map },
  { path: '/embeddings', label: 'Embeddings', icon: Atom },
  { path: '/strategy', label: 'Strategy', icon: Target },
]

export default function SideNav() {
  const [expanded, setExpanded] = useState(false)
  const location = useLocation()

  return (
    <nav
      className="fixed left-0 top-0 h-full z-50 flex flex-col bg-zinc-950/95 backdrop-blur-xl border-r border-white/[0.06] transition-all duration-300"
      style={{ width: expanded ? 200 : 64 }}
      onMouseEnter={() => setExpanded(true)}
      onMouseLeave={() => setExpanded(false)}
    >
      <div className="flex items-center h-14 px-4 border-b border-white/[0.06]">
        <div className="w-8 h-8 flex items-center justify-center flex-shrink-0">
          <svg viewBox="0 0 68 68" width="32" height="32" xmlns="http://www.w3.org/2000/svg">
            <path fill="#e4e4e7" d="M34 0L0 34l34 34 34-34L34 0zm28.6 34L48.8 47.8c.3-.7.5-1.5.5-2.3 0-2.6-1.8-4.9-5.3-5.6l-2.5-.5c-1.3-.2-1.8-.9-1.8-1.8 0-1 1-2 2.5-2 2.2 0 2.9 1.4 3.1 2.2l3.6-1.5c-.6-2.1-2.4-4.4-6.6-4.4-1.6 0-3 .5-4.2 1.3 1.4-1.9 2.9-3.8 4.5-5.4 4.7-4.7 7.3-6.1 7.9-6.3L62.6 34zM47.4 18.8c-.5.3-3.2 1.7-7.9 6.3-2.4 2.4-4.5 5.4-6.6 8.4l-2.3-4.7c1.9-1.1 2.7-3.2 2.7-5.2 0-3.3-2.3-5.8-6-5.8h-5.7L34 5.4l13.4 13.4zm-18.3 4.9c0 1.3-.9 2.2-2.6 2.2h-2.4v-4.5h2.4c1.7 0 2.6.9 2.6 2.3zM5.4 34l14.5-14.5v16.9H24v-6.9h2.5l3.7 7.7c-1.1 1.4-2.2 2.7-3.4 3.9-4.7 4.7-7.5 6.1-8 6.3L5.4 34zm16.4 16.3c.4-.2 3.3-1.6 8-6.3 2.3-2.3 4.2-4.9 6.1-7.5-.1.5-.2 1-.2 1.6 0 2.7 1.9 4.8 5 5.4l2.5.5c1.2.2 2 .9 2 1.9 0 1.1-1 1.9-2.6 1.9-2.5 0-3.6-1.4-3.8-3.1l-3.7 1.5c.6 2.5 2.8 5.2 7.4 5.2 1.4 0 2.5-.3 3.5-.8L34.1 62.5 21.8 50.3z"/>
          </svg>
        </div>
        {expanded && (
          <span className="ml-3 text-sm font-semibold text-white whitespace-nowrap overflow-hidden">
            Horizon 35
          </span>
        )}
      </div>

      <div className="flex-1 py-3 flex flex-col gap-0.5 px-2">
        {NAV_ITEMS.map(({ path, label, icon: Icon }) => {
          const isActive = location.pathname === path
          return (
            <NavLink
              key={path}
              to={path}
              className={`
                flex items-center h-10 rounded-lg px-3 transition-all duration-200 group relative
                ${isActive
                  ? 'bg-blue-500/10 text-blue-400'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04]'
                }
              `}
            >
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)]" />
              )}
              <Icon size={18} className="flex-shrink-0" />
              {expanded && (
                <span className="ml-3 text-sm font-medium whitespace-nowrap overflow-hidden">
                  {label}
                </span>
              )}
            </NavLink>
          )
        })}
      </div>

      <div className="px-2 pb-3">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center justify-center w-full h-8 rounded-lg text-zinc-600 hover:text-zinc-400 hover:bg-white/[0.04] transition-colors"
        >
          {expanded ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>
    </nav>
  )
}
