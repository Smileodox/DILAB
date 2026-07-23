import { motion } from 'framer-motion'
import { FileText, Link2 } from 'lucide-react'
import SlideFrame from './SlideFrame'
import { ORIGIN_COLORS } from '../../utils/colors'

export const STEPS = 2

// Deterministic "messy desk" scatter — index-based, so it never reshuffles on re-render.
const rot = (i) => ((i * 47) % 9) - 4 // -4 … +4 deg
const dy = (i) => ((i * 31) % 17) - 8 // -8 … +8 px

function Badge({ label, bg, text, border }) {
  return (
    <span
      className="px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider"
      style={{ backgroundColor: bg, color: text, border: `1px solid ${border}` }}
    >
      {label}
    </span>
  )
}

export default function JourneySourceScene({ data, step }) {
  const previews = data?.journey?.chunk_previews ?? []
  const driver = data?.journey?.driver ?? {}
  const topSources = driver?.top_sources ?? []
  const maxCount = Math.max(1, ...topSources.map((s) => s?.count ?? 0))
  const originColors = ORIGIN_COLORS[driver?.origin] ?? ORIGIN_COLORS.trend

  return (
    <SlideFrame
      kicker="The journey of one driver · Station 1"
      kickerColor="#8b5cf6"
      title="Every future begins as a paragraph"
      subtitle="Real excerpts from the corpus: regulatory reports, OECD papers, spectrum strategies. Before any model touches them."
      wide
    >
      <div className="h-full flex flex-col">
        <div className="relative flex-1 min-h-0">
          {/* The eight raw source chunks */}
          <div className="grid grid-cols-4 grid-rows-2 gap-4 h-full">
            {previews.slice(0, 8).map((c, i) => {
              const col = i % 4
              const row = Math.floor(i / 4)
              const pullX = (1.5 - col) * 70
              const pullY = (0.5 - row) * 50
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 30, rotate: 0 }}
                  animate={
                    step >= 1
                      ? { opacity: 0.12, x: pullX, y: pullY, rotate: rot(i) * 0.4, scale: 0.82 }
                      : { opacity: 1, x: 0, y: dy(i), rotate: rot(i), scale: 1 }
                  }
                  transition={{ duration: 0.55, delay: step >= 1 ? i * 0.03 : 0.15 + i * 0.09 }}
                  className="glass rounded-xl p-4 overflow-hidden flex flex-col min-h-0"
                >
                  <div className="flex items-center gap-1.5 mb-2 shrink-0">
                    <FileText size={12} className="text-zinc-500 shrink-0" />
                    <span className="text-xs font-medium text-zinc-500 truncate" title={c?.source}>
                      {c?.source ?? 'Unknown source'}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-300 leading-snug line-clamp-5">{c?.text ?? ''}</p>
                </motion.div>
              )
            })}
          </div>

          {/* The extracted driver, condensed out of the noise */}
          {step >= 1 && (
            <div className="absolute inset-0 z-10 flex items-center justify-center">
              <motion.div
                initial={{ opacity: 0, scale: 0.72, y: 24 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                transition={{ duration: 0.55, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
                className="glass-solid rounded-2xl p-8 max-w-4xl w-full shadow-2xl"
                style={{ border: '1px solid rgba(139, 92, 246, 0.35)' }}
              >
                <div className="flex items-center gap-2 mb-4">
                  <Badge label={driver?.origin ?? 'trend'} {...originColors} />
                  <Badge label={driver?.dimension ?? 'market'} bg="#27272a" text="#a1a1aa" border="#3f3f46" />
                  <Badge label={`${driver?.axis_role ?? 'driving'} axis`} bg="#1e3a5f" text="#60a5fa" border="#3b82f6" />
                </div>
                <h2 className="text-3xl font-extrabold text-white tracking-tight leading-tight mb-3">
                  {driver?.name ?? 'Driver'}
                </h2>
                <p className="text-sm text-zinc-400 leading-relaxed line-clamp-3 mb-6">
                  {driver?.description ?? ''}
                </p>
                <div className="flex items-start gap-10">
                  <div className="flex gap-8 shrink-0">
                    <div>
                      <div className="text-4xl font-extrabold tabular-nums text-violet-300">
                        {(driver?.n_chunks ?? 0).toLocaleString('en-US')}
                      </div>
                      <div className="text-sm text-zinc-400 mt-1">source chunks</div>
                    </div>
                    <div>
                      <div className="text-4xl font-extrabold tabular-nums text-violet-300">
                        {(driver?.n_sources ?? 0).toLocaleString('en-US')}
                      </div>
                      <div className="text-sm text-zinc-400 mt-1">sources</div>
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-2">
                      Top sources
                    </div>
                    <div className="space-y-1.5">
                      {topSources.slice(0, 5).map((s, i) => (
                        <div key={i} className="flex items-center gap-3">
                          <span className="text-xs text-zinc-400 truncate w-64" title={s?.title}>
                            {s?.title ?? ''}
                          </span>
                          <div className="flex-1 h-2 rounded-full bg-zinc-800 overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${((s?.count ?? 0) / maxCount) * 100}%` }}
                              transition={{ duration: 0.7, delay: 0.7 + i * 0.1 }}
                              className="h-full rounded-full"
                              style={{ backgroundColor: '#8b5cf6' }}
                            />
                          </div>
                          <span className="text-xs tabular-nums text-zinc-500 w-7 text-right">
                            {s?.count ?? 0}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          )}
        </div>

        {/* Bottom message — traceability is the point */}
        <div className="h-10 shrink-0 flex items-center justify-center">
          <motion.p
            initial={{ opacity: 0, y: 6 }}
            animate={step >= 1 ? { opacity: 1, y: 0 } : { opacity: 0, y: 6 }}
            transition={{ duration: 0.5, delay: 1.1 }}
            className="flex items-center gap-2 text-sm text-zinc-500"
          >
            <Link2 size={14} className="text-violet-400" />
            Nothing is invented: every driver keeps its source-chunk IDs for life.
          </motion.p>
        </div>
      </div>
    </SlideFrame>
  )
}
