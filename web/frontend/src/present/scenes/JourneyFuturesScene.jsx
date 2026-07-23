import { motion } from 'framer-motion'
import SlideFrame from './SlideFrame'
import { PLAUSIBILITY_COLORS } from '../../utils/colors'

export const STEPS = 2

// Optimistic → pessimistic position accents (endpoints per design system: teal → red).
const POSITION_COLORS = ['#14b8a6', '#eab308', '#f97316', '#ef4444']

function withEllipsis(text) {
  const t = (text ?? '').trim()
  if (!t) return ''
  return /[.!?]$/.test(t) ? t : `${t}…`
}

export default function JourneyFuturesScene({ data, step }) {
  const futures = (data?.journey?.manifestations ?? []).slice(0, 4)
  const driver = data?.journey?.driver ?? {}
  const meta = data?.meta ?? {}
  const nFactors = meta.cib_drivers ?? 14
  const combos = (meta.combinations ?? 0).toLocaleString('en-US')

  return (
    <SlideFrame
      kicker="The journey of one driver · Station 4"
      kickerColor="#8b5cf6"
      title="Four futures per factor"
      subtitle={driver?.name ? `How "${driver.name}" could actually play out by 2035.` : undefined}
      wide
    >
      <div className="h-full flex flex-col relative">
        {/* Optimistic → pessimistic axis */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: step >= 1 ? 0.35 : 1 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="shrink-0 flex items-center gap-4 mb-5 px-1"
        >
          <span className="text-sm font-semibold uppercase tracking-wider" style={{ color: '#14b8a6' }}>
            Optimistic
          </span>
          <motion.div
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ duration: 0.9, delay: 0.25, ease: 'easeOut' }}
            className="flex-1 h-1.5 rounded-full origin-left"
            style={{ background: 'linear-gradient(90deg, #14b8a6, #eab308, #f97316, #ef4444)' }}
          />
          <span className="text-sm font-semibold uppercase tracking-wider" style={{ color: '#ef4444' }}>
            Pessimistic
          </span>
        </motion.div>

        {/* The four manifestation cards, fanning in left to right */}
        <div className="flex-1 min-h-0 grid grid-cols-4 gap-5 items-stretch">
          {futures.map((m, i) => {
            const accent = POSITION_COLORS[i % POSITION_COLORS.length]
            const plaus = m?.plausibility ?? 'medium'
            return (
              <motion.div
                key={m?.id ?? i}
                initial={{ opacity: 0, x: -48, rotate: -2.5 }}
                animate={{ opacity: step >= 1 ? 0.35 : 1, x: 0, rotate: 0 }}
                transition={{ duration: 0.55, delay: step >= 1 ? 0 : 0.35 + i * 0.18, ease: [0.16, 1, 0.3, 1] }}
                className="glass rounded-xl p-5 flex flex-col overflow-hidden"
                style={{ borderTop: `3px solid ${accent}` }}
              >
                <h3 className="text-lg font-bold text-white leading-snug mb-2.5">
                  {m?.label ?? '—'}
                </h3>
                <p className="text-sm text-zinc-400 leading-snug line-clamp-6">
                  {withEllipsis(m?.description)}
                </p>
                <div className="mt-auto pt-4 flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: PLAUSIBILITY_COLORS[plaus] ?? PLAUSIBILITY_COLORS.medium }}
                  />
                  <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                    {plaus} plausibility
                  </span>
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* The combinatorial stamp */}
        {step >= 1 && (
          <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
            <motion.div
              initial={{ opacity: 0, scale: 1.6, rotate: -8 }}
              animate={{ opacity: 1, scale: 1, rotate: -2 }}
              transition={{ duration: 0.4, delay: 0.15, ease: 'easeOut' }}
              className="glass-solid rounded-2xl px-14 py-9 text-center shadow-2xl"
              style={{ border: '2px solid rgba(139, 92, 246, 0.55)' }}
            >
              <div className="text-2xl font-bold text-zinc-200 mb-1">
                {nFactors} factors × 4 futures
              </div>
              <div className="text-6xl font-extrabold tabular-nums tracking-tight text-violet-300">
                = {combos}
              </div>
              <div className="text-xl font-semibold text-zinc-300 mt-1">possible combinations</div>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.5, delay: 0.9 }}
                className="text-sm text-zinc-500 mt-4"
              >
                Most of them contradict themselves. The next station kills those.
              </motion.div>
            </motion.div>
          </div>
        )}
      </div>
    </SlideFrame>
  )
}
