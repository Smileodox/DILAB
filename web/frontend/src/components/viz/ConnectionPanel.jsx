import { useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Card from '@/components/ui/Card'
import { CIB_QUADRANT_COLORS } from '@/utils/colors'
import { staggerContainer, fadeUp } from '@/utils/animation'

function getQuadrant(inf, dep, medInf, medDep) {
  if (inf >= medInf && dep >= medDep) return 'critical'
  if (inf >= medInf && dep < medDep) return 'enabler'
  if (inf < medInf && dep >= medDep) return 'dependent'
  return 'isolated'
}

export default function ConnectionPanel({ node, edges, nodes, onSelectNode }) {
  const nodeById = useMemo(() => {
    const m = {}
    for (const n of nodes) m[n.id] = n
    return m
  }, [nodes])

  const connections = useMemo(() => {
    if (!node) return []
    const outgoing = edges
      .filter(e => e.source === node.id)
      .map(e => ({ ...e, direction: 'out', other: nodeById[e.target] }))
    const incoming = edges
      .filter(e => e.target === node.id)
      .map(e => ({ ...e, direction: 'in', other: nodeById[e.source] }))
    return [...outgoing, ...incoming]
      .filter(c => c.other)
      .sort((a, b) => Math.abs(b.score) - Math.abs(a.score))
  }, [node, edges, nodeById])

  const infValues = nodes.map(n => n.influence)
  const depValues = nodes.map(n => n.dependence)
  const sorted = (arr) => [...arr].sort((a, b) => a - b)
  const med = (arr) => { const s = sorted(arr); const m = Math.floor(s.length / 2); return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2 }
  const medInf = med(infValues)
  const medDep = med(depValues)

  if (!node) return null

  const quadrant = getQuadrant(node.influence, node.dependence, medInf, medDep)
  const qColor = CIB_QUADRANT_COLORS[quadrant]

  return (
    <Card className="h-full overflow-hidden">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-3 h-3 rounded-full mt-1 shrink-0" style={{ background: qColor }} />
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-white leading-snug">{node.name}</h3>
          <div className="flex gap-3 mt-1 text-xs text-zinc-500">
            <span>Influence: <span className="text-zinc-300">{node.influence}</span></span>
            <span>Dependence: <span className="text-zinc-300">{node.dependence}</span></span>
            <span className="capitalize" style={{ color: qColor }}>{quadrant}</span>
          </div>
        </div>
      </div>

      <div className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">
        Connections ({connections.length})
      </div>

      <motion.div variants={staggerContainer} initial="enter" animate="center" className="space-y-1.5 max-h-[360px] overflow-y-auto pr-1">
        <AnimatePresence>
          {connections.map((c, i) => {
            const positive = c.score > 0
            const abs = Math.abs(c.score)
            const barWidth = (abs / 3) * 100

            return (
              <motion.div
                key={`${c.source}-${c.target}-${c.direction}`}
                variants={fadeUp}
                onClick={() => onSelectNode?.(c.other.id)}
                className="flex items-center gap-2 py-1.5 px-2 rounded-md cursor-pointer hover:bg-white/[0.04] transition-colors"
              >
                <span className="text-[10px] text-zinc-600 w-4 shrink-0 text-right">{c.direction === 'out' ? '→' : '←'}</span>
                <span className="text-xs text-zinc-300 flex-1 truncate">{c.other.name}</span>
                <div className="w-16 h-1.5 rounded-full bg-zinc-800 shrink-0 overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${barWidth}%`,
                      background: positive ? '#10b981' : '#ef4444',
                    }}
                  />
                </div>
                <span
                  className="text-[10px] font-mono w-6 text-right shrink-0"
                  style={{ color: positive ? '#10b981' : '#ef4444' }}
                >
                  {c.score > 0 ? '+' : ''}{c.score}
                </span>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </motion.div>
    </Card>
  )
}
