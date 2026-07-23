import { motion } from 'framer-motion'
import { ArrowRight, Database, Zap, Grid3x3, Network, Map, Target } from 'lucide-react'
import SlideFrame from './SlideFrame'

export const STEPS = 2

const STAGES = [
  { label: 'Knowledge Base', sub: 'ingest · arXiv enrichment · DVI maturity', icon: Database, color: '#3b82f6' },
  { label: 'Drivers', sub: 'BOM decomposition · trend scanning · merge', icon: Zap, color: '#60a5fa' },
  { label: 'Morphology + CIB', sub: '14×4 futures · 5-persona Delphi panel', icon: Grid3x3, color: '#8b5cf6' },
  { label: 'Scenario Field', sub: '120 consistent scenarios · null-model referee', icon: Network, color: '#a78bfa' },
  { label: 'Archetypes + Landscape', sub: 'HDBSCAN · honest continuum · this dashboard', icon: Map, color: '#10b981' },
  { label: 'Evaluation + Strategy', sub: 'grounded auditor · AHP/TOPSIS · no-regret moves', icon: Target, color: '#34d399' },
]

export default function ClosingScene({ data, step }) {
  return (
    <SlideFrame
      kicker="One pipeline, many futures"
      kickerColor="#10b981"
      title="Swap the knowledge base: same pipeline, new map."
      subtitle="Spectrum monitoring was only the test case. The framework is domain-agnostic: every stage docks onto whatever corpus you feed it."
      wide
    >
      <div className="h-full flex flex-col justify-center gap-10">
        {/* Pipeline blocks */}
        <div className="flex items-stretch justify-between gap-2">
          {STAGES.map((b, i) => {
            const Icon = b.icon
            return (
              <div key={b.label} className="flex items-center gap-2 flex-1">
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: i * 0.12 }}
                  className="flex-1 rounded-xl p-4 border h-full"
                  style={{ background: `${b.color}0d`, borderColor: `${b.color}30` }}
                >
                  <Icon size={20} style={{ color: b.color }} className="mb-2" />
                  <p className="text-sm font-bold text-white leading-tight">{b.label}</p>
                  <p className="text-xs text-zinc-400 mt-1 leading-snug">{b.sub}</p>
                </motion.div>
                {i < STAGES.length - 1 && <ArrowRight size={14} className="text-zinc-700 shrink-0" />}
              </div>
            )
          })}
        </div>

        {/* Final chain recap */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={step >= 1 ? { opacity: 1 } : {}}
          transition={{ duration: 0.6 }}
          className="text-center"
        >
          <p className="text-2xl md:text-3xl font-bold text-zinc-200 tracking-tight">
            <span className="text-blue-400">{data.meta.sources} sources</span>
            <span className="text-zinc-600 mx-3">→</span>
            <span className="text-blue-300">{data.meta.cib_drivers} factors</span>
            <span className="text-zinc-600 mx-3">→</span>
            <span className="text-violet-400">268M futures</span>
            <span className="text-zinc-600 mx-3">→</span>
            <span className="text-violet-300">{data.meta.scenarios} scenarios</span>
            <span className="text-zinc-600 mx-3">→</span>
            <span className="text-emerald-400">{data.meta.archetypes} archetypes</span>
          </p>
          <p className="mt-4 text-sm text-zinc-500">
            Every step traceable by ID, from source chunk to strategy. Thank you.
          </p>
        </motion.div>
      </div>
    </SlideFrame>
  )
}
