import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import SlideFrame from './SlideFrame'
import { DIMENSION_COLORS } from '../../utils/colors'

export const STEPS = 4

function useCountUp(target, active, duration = 1400) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (!active || !target) return
    let frame
    const start = performance.now()
    function tick(now) {
      const p = Math.min((now - start) / duration, 1)
      setValue(Math.round((1 - Math.pow(1 - p, 3)) * target))
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, active, duration])
  return value
}

const NEUTRAL = '#52525b'
const PULL = 0.45 // how far orphans contract toward their cluster centroid at step 3

/* One <circle> per sampled chunk. All motion is plain CSS transitions on
 * transform/fill/opacity — 600 framer-motion nodes would tank the frame rate. */
function Dot({ p, i, step, centroid, mounted }) {
  const contracted = step >= 3 && !p.covered && centroid
  const x = contracted ? p.x + (centroid.cx - p.x) * PULL : p.x
  const y = contracted ? p.y + (centroid.cy - p.y) * PULL : p.y
  const fill = step >= 2 && !p.covered ? (DIMENSION_COLORS[p.dim]?.border ?? NEUTRAL) : NEUTRAL
  const opacity = !mounted ? 0 : p.covered && step >= 1 ? 0.05 : step >= 2 ? 0.9 : 0.75
  return (
    <circle
      r={0.55}
      style={{
        transform: `translate(${x * 100}px, ${y * 100}px)`,
        fill,
        opacity,
        transition: 'transform 0.9s ease, fill 0.5s ease, opacity 0.6s ease',
        transitionDelay: `${(i % 50) * 6}ms`,
      }}
    />
  )
}

function StepCard({ active, past, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 16 }}
      animate={active || past ? { opacity: past ? 0.45 : 1, x: 0 } : { opacity: 0, x: 16 }}
      transition={{ duration: 0.45 }}
      className="glass rounded-xl p-4"
    >
      {children}
    </motion.div>
  )
}

function BigNum({ value, active, color, label, sub }) {
  const n = useCountUp(value, active)
  return (
    <div>
      <span className="text-3xl font-extrabold tabular-nums tracking-tight" style={{ color }}>
        {n.toLocaleString('en-US')}
      </span>
      <span className="ml-2 text-sm font-semibold text-zinc-200">{label}</span>
      {sub && <p className="mt-1 text-xs text-zinc-500 leading-relaxed">{sub}</p>}
    </div>
  )
}

export default function JourneyMechanismScene({ data, step }) {
  const ext = data?.extraction
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50)
    return () => clearTimeout(t)
  }, [])

  if (!ext?.points) {
    return (
      <SlideFrame kicker="The journey of one driver · Station 2" kickerColor="#8b5cf6"
        title="How a driver is found" wide>
        <div className="h-full flex items-center justify-center text-zinc-500">
          extraction data missing: run scripts/prepare_present_extraction.py
        </div>
      </SlideFrame>
    )
  }

  const meta = ext.meta ?? {}
  const clusters = ext.clusters ?? []
  const centroidByKey = Object.fromEntries(clusters.map((c) => [c.key, c]))
  const ours = clusters.find((c) => c.is_journey)
  const buckets = meta.dimension_bucket_sizes ?? {}
  const exampleChips = ours ? [ours, ...clusters.filter((c) => !c.is_journey).slice(0, 2)] : clusters.slice(0, 3)

  return (
    <SlideFrame
      kicker="The journey of one driver · Station 2"
      kickerColor="#8b5cf6"
      title="How a driver is found"
      subtitle="Coverage-gap detection: embed everything, keep what the product does not explain, cluster it, name it."
      wide
    >
      <div className="h-full flex gap-8 min-h-0">
        {/* Point field */}
        <div className="flex-1 min-h-0 flex items-center justify-center">
          <svg viewBox="-3 -3 106 106" className="h-full max-h-[560px] aspect-square">
            {ext.points.map((p, i) => (
              <Dot key={i} p={p} i={i} step={step} mounted={mounted}
                   centroid={p.cluster ? centroidByKey[p.cluster] : null} />
            ))}
            {/* Pulsing marker on our cluster once it exists. Label gets a backing pill so it
                stays readable over foreign points, clamped into the viewBox and flipped below
                the cluster when the centroid sits near the top edge. */}
            {step >= 3 && ours && (() => {
              const cx = Math.min(Math.max(ours.cx * 100, 13), 87)
              const below = ours.cy * 100 < 16
              const ly = below ? ours.cy * 100 + 11 : ours.cy * 100 - 9
              return (
                <>
                  <motion.circle
                    cx={ours.cx * 100} cy={ours.cy * 100} fill="none"
                    stroke="#8b5cf6" strokeWidth={0.4}
                    initial={{ r: 2, opacity: 0.9 }}
                    animate={{ r: [3, 9], opacity: [0.9, 0] }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut', delay: 1.0 }}
                  />
                  <motion.g initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                    transition={{ duration: 0.5, delay: 1.2 }}>
                    <rect x={cx - 11.5} y={ly - 3.4} width={23} height={5.2} rx={2.6}
                      fill="rgba(24,24,27,0.88)" stroke="rgba(139,92,246,0.55)" strokeWidth={0.22} />
                    <text x={cx} y={ly} textAnchor="middle" dominantBaseline="central"
                      fill="#c4b5fd" style={{ fontSize: 3.2, fontWeight: 700 }}>
                      {below ? 'our driver ↑' : 'our driver ↓'}
                    </text>
                  </motion.g>
                </>
              )
            })()}
          </svg>
        </div>

        {/* Narration stack — one card per reveal step */}
        <div className="w-[400px] shrink-0 flex flex-col justify-center gap-3">
          <StepCard active={step === 0} past={step > 0}>
            <BigNum value={meta.n_trend_chunks} active label="chunks embedded" color="#e4e4e7"
              sub={`The entire trend corpus as vectors. Every dot is a real chunk (sample of ${(meta.n_points_sampled ?? 0).toLocaleString('en-US')} shown).`} />
          </StepCard>

          {step >= 1 && (
            <StepCard active={step === 1} past={step > 1}>
              <BigNum value={meta.n_orphan_chunks} active={step >= 1} label="orphan chunks" color="#f4f4f5"
                sub={`Coverage check against the product's own technology: similarity < ${meta.coverage_threshold ?? 0.55} → the product does NOT cover it. That gap is where external drivers live.`} />
            </StepCard>
          )}

          {step >= 2 && (
            <StepCard active={step === 2} past={step > 2}>
              <p className="text-sm font-semibold text-zinc-200 mb-2">
                bucketed by driving dimension
              </p>
              <div className="flex flex-col gap-1.5">
                {Object.entries(buckets).map(([dim, n]) => {
                  const c = DIMENSION_COLORS[dim]
                  return (
                    <span key={dim} className="flex items-center gap-2 text-xs text-zinc-400">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: c?.border }} />
                      <span className="font-medium" style={{ color: c?.text }}>{dim}</span>
                      <span className="tabular-nums text-zinc-500">{n.toLocaleString('en-US')} chunks</span>
                    </span>
                  )
                })}
              </div>
            </StepCard>
          )}

          {step >= 3 && (
            <StepCard active={step >= 3} past={false}>
              <BigNum value={meta.n_final} active={step >= 3} label="clusters → named drivers" color="#a78bfa"
                sub="K-means inside each bucket, then ONE focused LLM call per cluster reads its five most central chunks and names the force behind them:" />
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {exampleChips.map((c) => {
                  const col = DIMENSION_COLORS[c.dim]
                  return (
                    <span key={c.key}
                      className={`px-2.5 py-1 rounded-full text-[11px] font-medium max-w-[180px] truncate ${c.is_journey ? 'ring-2 ring-violet-400' : ''}`}
                      style={{ backgroundColor: col?.bg, color: col?.text, border: `1px solid ${col?.border}` }}
                      title={c.name}>
                      {c.name}
                    </span>
                  )
                })}
                <span className="px-2 py-1 text-[11px] text-zinc-500">…{Math.max(clusters.length - exampleChips.length, 0)} more</span>
              </div>
            </StepCard>
          )}
        </div>
      </div>
    </SlideFrame>
  )
}
