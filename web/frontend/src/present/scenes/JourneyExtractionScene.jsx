import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import SlideFrame from './SlideFrame'
import { ORIGIN_COLORS } from '../../utils/colors'

export const STEPS = 2

// Index-based vertical jitter for a "loose grid" feel — deterministic, no Math.random.
const jitter = (i) => ((i * 13) % 11) - 5 // -5 … +5 px

function Chip({ d, i, step, isOurs }) {
  const c = ORIGIN_COLORS[d?.origin] ?? ORIGIN_COLORS.bom
  const selected = !!d?.selected
  const active = step >= 1
  return (
    <span className="relative inline-flex">
      {/* Pulsing halo + callout for the driver we are following */}
      {isOurs && active && (
        <>
          <motion.span
            className="absolute -inset-1 rounded-full pointer-events-none"
            animate={{
              boxShadow: [
                '0 0 0 0px rgba(139, 92, 246, 0.7)',
                '0 0 0 10px rgba(139, 92, 246, 0)',
              ],
            }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut' }}
          />
          <motion.span
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.9 }}
            className="absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap px-2.5 py-1 rounded-full glass-solid text-xs font-bold text-violet-300 z-10"
            style={{ border: '1px solid rgba(139, 92, 246, 0.5)' }}
          >
            our driver ↓
          </motion.span>
        </>
      )}
      <motion.span
        initial={{ opacity: 0, scale: 0.5 }}
        animate={{
          opacity: active ? (selected ? 1 : 0.25) : 1,
          scale: active ? (selected ? 1.08 : 0.94) : 1,
          y: jitter(i),
          boxShadow: active && selected ? `0 0 0 2px ${c.border}` : '0 0 0 0px rgba(0,0,0,0)',
        }}
        transition={{ duration: 0.45, delay: step >= 1 ? (i % 9) * 0.03 : 0.1 + i * 0.025 }}
        title={d?.name}
        className="px-3 py-1.5 rounded-full text-xs font-medium max-w-[170px] truncate cursor-default"
        style={{ backgroundColor: c.bg, color: c.text, border: `1px solid ${c.border}` }}
      >
        {d?.name ?? '—'}
      </motion.span>
    </span>
  )
}

export default function JourneyExtractionScene({ data, step }) {
  const drivers = data?.journey?.all_drivers ?? []
  const ourId = data?.journey?.driver?.id
  const meta = data?.meta ?? {}
  const nBom = drivers.filter((d) => d?.origin === 'bom').length
  const nTrend = drivers.filter((d) => d?.origin === 'trend').length
  const nTotal = meta.drivers_total ?? drivers.length
  const nSelected = meta.cib_drivers ?? drivers.filter((d) => d?.selected).length
  const nChunks = (meta.chunks ?? 0).toLocaleString('en-US')

  return (
    <SlideFrame
      kicker="The journey of one driver · Station 3"
      kickerColor="#8b5cf6"
      title={`${nChunks} chunks → ${nTotal} candidates → ${nSelected} factors`}
      subtitle="Hardware components meet market trends: two extraction routes, one unified driver pool."
      wide
    >
      <div className="h-full flex flex-col">
        {/* Legend */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="shrink-0 flex items-center justify-center gap-6 mb-4"
        >
          <span className="flex items-center gap-2 text-sm text-zinc-400">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#0ea5e9' }} />
            {nBom} BOM <span className="text-zinc-600">· from the component tree</span>
          </span>
          <span className="flex items-center gap-2 text-sm text-zinc-400">
            <span className="w-3 h-3 rounded-full" style={{ backgroundColor: '#8b5cf6' }} />
            {nTrend} Trend <span className="text-zinc-600">· from the document corpus</span>
          </span>
        </motion.div>

        {/* All 41 candidates */}
        <div className="flex-1 min-h-0 flex items-center justify-center">
          {/* gap-y-8 leaves the "our driver" callout (-top-8) a clear band above its chip */}
          <div className="flex flex-wrap justify-center content-center gap-x-2.5 gap-y-8 max-w-6xl pt-4">
            {drivers.map((d, i) => (
              <Chip key={d?.id ?? i} d={d} i={i} step={step} isOurs={d?.id != null && d?.id === ourId} />
            ))}
          </div>
        </div>

        {/* Counter row */}
        <div className="h-12 shrink-0 flex items-center justify-center">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={step >= 1 ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
            transition={{ duration: 0.5, delay: 0.6 }}
            className="flex items-center gap-3 text-sm"
          >
            <span className="font-semibold text-zinc-300">{nTotal} unified</span>
            <ArrowRight size={16} className="text-zinc-600" />
            <span className="text-zinc-400">deduplicated &amp; relevance-ranked</span>
            <ArrowRight size={16} className="text-zinc-600" />
            <span className="font-semibold text-violet-300">{nSelected} CIB axes</span>
          </motion.div>
        </div>
      </div>
    </SlideFrame>
  )
}
