import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { Database, Zap, Grid3X3, Globe, Maximize2, X } from 'lucide-react'
import { useKbApi } from '@/context/KbContext'
import MetricCard from '@/components/ui/MetricCard'
import Card from '@/components/ui/Card'
import PipelineFlow from '@/components/viz/PipelineFlow'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

const METHOD_CARDS = [
  {
    title: 'Morphological Analysis',
    desc: 'Zwicky box decomposing each driver into discrete manifestations, then systematically combining them to span the full possibility space.',
    icon: '🔲',
  },
  {
    title: 'Cross-Impact Balance',
    desc: 'Weimer-Jehle consistency algorithm evaluating pairwise driver interactions to filter for internally coherent scenario configurations.',
    icon: '⚖️',
  },
  {
    title: 'MCDA Evaluation',
    desc: 'AHP-derived criteria weights combined with TOPSIS ranking to produce a defensible, multi-criteria scenario prioritization.',
    icon: '📊',
  },
]

export default function OverviewPage() {
  const { data, loading } = useKbApi('/api/overview')
  const navigate = useNavigate()
  const [pipelineExpanded, setPipelineExpanded] = useState(false)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
    >
      {/* Hero */}
      <div className="h-72 bg-gradient-to-br from-blue-900/30 via-zinc-900 to-violet-900/20 flex items-center">
        <div className="max-w-7xl mx-auto px-8 w-full">
          <motion.p
            variants={fadeUp}
            className="text-sm font-medium text-blue-400 uppercase tracking-widest mb-3"
          >
            Rohde & Schwarz
          </motion.p>
          <motion.h1
            variants={fadeUp}
            className="text-4xl md:text-5xl font-extrabold text-white tracking-tight leading-tight"
          >
            Horizon 35
          </motion.h1>
          <motion.p
            variants={fadeUp}
            className="mt-3 text-lg text-zinc-400"
          >
            AI-Driven Technology Foresight — Regulatory Frequency Monitoring
          </motion.p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-8 py-8 space-y-10">
        {/* Metric cards */}
        <motion.div
          variants={staggerContainer}
          className="grid grid-cols-2 lg:grid-cols-4 gap-4"
        >
          <MetricCard label="Sources" value={data.sources} icon={Database} />
          <MetricCard label="Drivers" value={data.drivers_total} icon={Zap} />
          <MetricCard label="Manifestations" value={data.manifestations} icon={Grid3X3} />
          <MetricCard label="Scenarios" value={data.scenarios} icon={Globe} />
        </motion.div>

        {/* Pipeline flow (inline) */}
        <motion.div variants={fadeIn}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Pipeline Architecture</h2>
            <button
              onClick={() => setPipelineExpanded(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
            >
              <Maximize2 size={14} />
              Expand
            </button>
          </div>
          <div
            className="cursor-pointer rounded-xl hover:ring-1 hover:ring-white/10 transition-all"
            onClick={() => setPipelineExpanded(true)}
          >
            <PipelineFlow
              overview={data}
              onNodeClick={(path) => navigate(path)}
            />
          </div>
        </motion.div>

        {/* Methodology cards */}
        <motion.div variants={fadeIn}>
          <h2 className="text-lg font-semibold text-white mb-4">Methodology</h2>
          <motion.div
            variants={staggerContainer}
            className="grid md:grid-cols-3 gap-4"
          >
            {METHOD_CARDS.map((m) => (
              <motion.div key={m.title} variants={fadeUp}>
                <Card className="h-full">
                  <span className="text-2xl mb-3 block">{m.icon}</span>
                  <h3 className="text-sm font-semibold text-white mb-2">{m.title}</h3>
                  <p className="text-xs leading-relaxed text-zinc-400">{m.desc}</p>
                </Card>
              </motion.div>
            ))}
          </motion.div>
        </motion.div>
      </div>

      {/* Pipeline expanded modal */}
      <AnimatePresence>
        {pipelineExpanded && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
            onClick={() => setPipelineExpanded(false)}
          >
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
              className="w-[90vw] max-w-[1600px] glass-solid rounded-2xl p-6 shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white">Pipeline Architecture</h2>
                <button
                  onClick={() => setPipelineExpanded(false)}
                  className="p-2 rounded-lg text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-colors"
                >
                  <X size={18} />
                </button>
              </div>
              <div style={{ height: 500 }}>
                <PipelineFlow
                  overview={data}
                  expanded
                  onNodeClick={(path) => {
                    setPipelineExpanded(false)
                    navigate(path)
                  }}
                  height={500}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
