import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, FileText } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import Card from '@/components/ui/Card'
import { OriginBadge } from '@/components/ui/Badge'
import { staggerContainer, fadeUp } from '@/utils/animation'

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'bom', label: 'BOM' },
  { key: 'trend', label: 'Trend' },
]

export default function DriversPage() {
  const { data, loading } = useApi('/api/drivers')
  const [filter, setFilter] = useState('all')
  const [expandedId, setExpandedId] = useState(null)

  const drivers = data || []

  const counts = useMemo(() => {
    const c = { all: drivers.length, bom: 0, trend: 0 }
    for (const d of drivers) {
      if (d.origin === 'bom') c.bom++
      else if (d.origin === 'trend') c.trend++
    }
    return c
  }, [drivers])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const filtered = filter === 'all'
    ? drivers
    : drivers.filter((d) => d.origin === filter)

  return (
    <div className="max-w-7xl mx-auto px-8 py-8">
      {/* Header + filters */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Technology Drivers</h1>
        <div className="flex gap-2">
          {FILTERS.map((f) => {
            const active = filter === f.key
            return (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'bg-zinc-800/60 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                }`}
              >
                {f.label}
                <span className={`ml-1.5 ${active ? 'text-blue-200' : 'text-zinc-600'}`}>
                  {counts[f.key]}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Card grid */}
      <motion.div
        variants={staggerContainer}
        initial="enter"
        animate="center"
        className="grid md:grid-cols-2 xl:grid-cols-3 gap-4"
      >
        {filtered.map((driver) => {
          const expanded = expandedId === driver.id
          const accentColor = driver.origin === 'bom' ? '#0ea5e9' : '#8b5cf6'

          return (
            <motion.div key={driver.id} variants={fadeUp} layout>
              <Card
                hover
                onClick={() => setExpandedId(expanded ? null : driver.id)}
                className="h-full relative"
              >
                {/* Origin accent */}
                <div
                  className="absolute left-0 top-3 bottom-3 w-[3px] rounded-r"
                  style={{ background: accentColor, opacity: expanded ? 1 : 0.4 }}
                />

                <div className="pl-3">
                  {/* Top row */}
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <h3 className="text-sm font-semibold text-white leading-snug">
                      {driver.name}
                    </h3>
                    <ChevronDown
                      size={14}
                      className={`text-zinc-600 shrink-0 mt-0.5 transition-transform duration-200 ${
                        expanded ? 'rotate-180' : ''
                      }`}
                    />
                  </div>

                  {/* Badge */}
                  <div className="mb-2.5">
                    <OriginBadge origin={driver.origin} />
                  </div>

                  {/* Description */}
                  <p
                    className={`text-xs text-zinc-400 leading-relaxed ${
                      expanded ? '' : 'line-clamp-2'
                    }`}
                  >
                    {driver.description}
                  </p>

                  {/* Expanded section */}
                  <AnimatePresence>
                    {expanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-3 pt-3 border-t border-white/5 space-y-3">
                          {driver.merge_reasoning && (
                            <div>
                              <p className="text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-1">
                                Merge Reasoning
                              </p>
                              <p className="text-xs text-zinc-400 leading-relaxed">
                                {driver.merge_reasoning}
                              </p>
                            </div>
                          )}
                          <div className="flex items-center gap-4 text-xs text-zinc-500">
                            <div className="flex items-center gap-1.5">
                              <FileText size={11} />
                              <span>{driver.source_chunk_ids?.length || 0} source chunks</span>
                            </div>
                            {driver.dimension_type && (
                              <span className="capitalize">{driver.dimension_type}</span>
                            )}
                          </div>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </Card>
            </motion.div>
          )
        })}
      </motion.div>
    </div>
  )
}
