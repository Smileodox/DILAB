import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { Scale, Dices, Layers } from 'lucide-react'
import SlideFrame from './SlideFrame'
import { archetypeColor, CONTINUUM_COLOR } from '../../utils/colors'

export const STEPS = 2

/*
 * Animates from wherever the number currently sits to `target`, so the
 * before→after morph plays forward on step 1 and rewinds cleanly if the
 * presenter steps back. State updates happen only inside rAF callbacks.
 */
function useAnimatedNumber(target, duration = 1400) {
  const [value, setValue] = useState(target)
  const latest = useRef(target)
  useEffect(() => {
    const from = latest.current
    if (from === target) return undefined
    let frame
    let start = null
    const tick = (now) => {
      if (start === null) start = now
      const p = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - p, 3)
      const v = from + (target - from) * eased
      latest.current = v
      setValue(v)
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, duration])
  return value
}

/* Horizontal band gauge 0–max with a shaded target zone and a needle. */
function BandGauge({ value, band = [0.2, 0.3], max = 0.4 }) {
  const pct = (v) => Math.min(Math.max(v / max, 0), 1) * 100
  return (
    <div className="mt-6">
      <div className="relative h-2.5 rounded-full bg-zinc-800">
        <div
          className="absolute inset-y-0 bg-emerald-500/25 border-x border-emerald-400/60"
          style={{ left: `${pct(band[0])}%`, width: `${pct(band[1]) - pct(band[0])}%` }}
        />
        <div
          className="absolute -top-1.5 h-[22px] w-[3px] rounded-full bg-white shadow-[0_0_8px_rgba(255,255,255,0.55)]"
          style={{ left: `calc(${pct(value)}% - 1.5px)` }}
        />
      </div>
      <div className="relative mt-1.5 h-4 text-[11px] text-zinc-500 tabular-nums">
        <span className="absolute left-0">0</span>
        <span className="absolute -translate-x-1/2 text-emerald-400" style={{ left: `${pct(band[0])}%` }}>
          {Math.round(band[0] * 100)}
        </span>
        <span className="absolute -translate-x-1/2 text-emerald-400" style={{ left: `${pct(band[1])}%` }}>
          {Math.round(band[1] * 100)}
        </span>
        <span className="absolute right-0">{Math.round(max * 100)}%</span>
      </div>
    </div>
  )
}

/* Slim z-score scale min..max with a labeled significance line and a marker. */
function ZScale({ value, min = -1, max = 5, sig = 2 }) {
  const pct = (v) => ((Math.min(Math.max(v, min), max) - min) / (max - min)) * 100
  const passed = value >= sig
  return (
    <div className="mt-6">
      <div className="relative h-2.5 rounded-full bg-zinc-800">
        <div className="absolute inset-y-0 right-0 rounded-r-full bg-emerald-500/15" style={{ left: `${pct(sig)}%` }} />
        <div className="absolute -top-1 -bottom-1 w-px bg-emerald-400/80" style={{ left: `${pct(sig)}%` }} />
        <div
          className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white/70"
          style={{ left: `${pct(value)}%`, backgroundColor: passed ? '#34d399' : '#a78bfa' }}
        />
      </div>
      <div className="relative mt-1.5 h-4 text-[11px] text-zinc-500 tabular-nums">
        <span className="absolute left-0">−1</span>
        <span className="absolute -translate-x-1/2 text-emerald-400" style={{ left: `${pct(sig)}%` }}>
          z = {sig} · significance
        </span>
        <span className="absolute right-0">+5</span>
      </div>
    </div>
  )
}

/* Fill bar 0..max with a tick marking the "before" baseline. */
function CorpusBar({ value, before, max }) {
  const pct = (v) => Math.min(Math.max(v / max, 0), 1) * 100
  return (
    <div className="mt-6">
      <div className="relative h-2.5 rounded-full bg-zinc-800">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-sky-500/80"
          style={{ width: `${pct(value)}%` }}
        />
        <div className="absolute -top-1 -bottom-1 w-px bg-white/60" style={{ left: `${pct(before)}%` }} />
      </div>
      <div className="relative mt-1.5 h-4 text-[11px] text-zinc-500 tabular-nums">
        <span className="absolute left-0">0</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${pct(before)}%` }}>
          {before.toLocaleString('en-US')}
        </span>
        <span className="absolute right-0">{max.toLocaleString('en-US')}</span>
      </div>
    </div>
  )
}

/* The real field "after": live mini-scatter in cluster space with the Station-7
 * archetype colors — dark and native instead of a white matplotlib export. */
function AfterField({ points }) {
  const pts = (points ?? []).filter((p) => Number.isFinite(p?.ox) && Number.isFinite(p?.oy))
  if (!pts.length) return null
  const labels = pts.map((p) => p.archetype)
  const xs = pts.map((p) => p.ox)
  const ys = pts.map((p) => p.oy)
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)]
  const [y0, y1] = [Math.min(...ys), Math.max(...ys)]
  const X = (v) => ((v - x0) / (x1 - x0 || 1)) * 90 + 5
  const Y = (v) => 95 - ((v - y0) / (y1 - y0 || 1)) * 90
  return (
    <svg viewBox="0 0 100 100" className="w-full rounded-lg border border-emerald-400/30 bg-zinc-900/70">
      {pts.map((p, i) => {
        const cont = !p.archetype || p.archetype === 'Continuum'
        return (
          <circle
            key={p.id ?? i}
            cx={X(p.ox)} cy={Y(p.oy)} r={cont ? 1.1 : 1.9}
            fill={cont ? CONTINUUM_COLOR : archetypeColor(p.archetype, labels)}
            opacity={cont ? 0.25 : 0.95}
          />
        )
      })}
    </svg>
  )
}

/* The real 14×14 CIB sign matrix. Before: everything reads positive/neutral (the
 * positivity-bias look). On step 1 the inhibiting cells flip red one by one. */
function MiniMatrix({ signs, on }) {
  if (!signs?.length) return null
  let negIdx = 0
  return (
    <div
      className="mt-4 mx-auto grid w-fit gap-[2px]"
      style={{ gridTemplateColumns: `repeat(${signs.length}, 9px)` }}
    >
      {signs.flatMap((row, i) =>
        row.map((v, j) => {
          const neg = v < 0
          const d = neg ? negIdx++ : 0
          return (
            <div
              key={`${i}-${j}`}
              className="h-[9px] rounded-[2px]"
              style={{
                backgroundColor:
                  i === j ? '#18181b'
                  : neg && on ? 'rgba(244,63,94,0.85)'
                  : v > 0 ? 'rgba(16,185,129,0.28)'
                  : 'rgba(63,63,70,0.55)',
                transition: 'background-color 0.35s ease',
                transitionDelay: neg ? `${d * 18}ms` : '0ms',
              }}
            />
          )
        }),
      )}
    </div>
  )
}

function LeverCard({ icon: Icon, accent, title, metric, delay, children }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay }}
      className="glass-solid rounded-2xl p-6 flex flex-col"
    >
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-lg shrink-0" style={{ backgroundColor: `${accent}1f` }}>
          <Icon size={20} style={{ color: accent }} />
        </div>
        <div className="min-w-0">
          <p className="text-base font-bold text-zinc-100">{title}</p>
          <p className="text-[11px] uppercase tracking-[0.15em] text-zinc-500">{metric}</p>
        </div>
      </div>
      {children}
    </motion.div>
  )
}

export default function ImprovementLeversScene({ data, step }) {
  const imp = data?.improvement ?? {}
  const cib = imp.cib_negative_share ?? {}
  const zs = imp.z_score ?? {}
  const corpus = imp.corpus_chunks ?? {}
  const counts = imp.cib_counts ?? {}
  const on = (step ?? 0) >= 1

  const cibBefore = cib.before ?? 0
  const cibAfter = cib.after ?? 0.29
  const band = cib.band ?? [0.2, 0.3]
  const bandLabel = cib.band_label ?? 'Weimer-Jehle 20–30%'
  const zBefore = zs.before ?? 1.4
  const zAfter = zs.after ?? 3.55
  const zSig = zs.significant_at ?? 2.0
  const cBefore = corpus.before ?? 2875
  const cAfter = corpus.after ?? 3905
  const cMax = Math.ceil((cAfter * 1.1) / 500) * 500

  // All three levers morph before→after simultaneously on step 1.
  const cibVal = useAnimatedNumber(on ? cibAfter : cibBefore)
  const zVal = useAnimatedNumber(on ? zAfter : zBefore)
  const cVal = useAnimatedNumber(on ? cAfter : cBefore)

  return (
    <SlideFrame
      kicker="Improvement · measured, not claimed"
      kickerColor="#10b981"
      title="Three levers, three measurements"
      subtitle="We never touched the outputs. We fixed the inputs, and each fix has a number."
      wide
    >
      <div className="h-full flex flex-col justify-center">
        <div className="grid grid-cols-3 gap-6">
          <LeverCard icon={Scale} accent="#34d399" title="Panel honesty" metric="CIB inhibiting share" delay={0}>
            <p className="mt-4 flex items-baseline gap-3">
              <span className="text-5xl font-extrabold tabular-nums tracking-tight" style={{ color: '#34d399' }}>
                {Math.round(cibVal * 100)}%
              </span>
              <span className="text-xs text-zinc-500 tabular-nums">
                {Math.round(cibBefore * 100)}% → {Math.round(cibAfter * 100)}% · target {bandLabel}
              </span>
            </p>
            <MiniMatrix signs={imp.cib_matrix_signs} on={on} />
            <p className="mt-1.5 text-center text-[11px] text-zinc-500 tabular-nums">
              the real matrix · {counts.inhibiting ?? 53} of {counts.pairs ?? 182} pairwise judgments inhibiting
            </p>
            <BandGauge value={cibVal} band={band} />
            <p className="mt-4 text-xs leading-relaxed text-zinc-500">
              Dissent-preserving Delphi panel (was: positivity bias).
            </p>
          </LeverCard>

          <LeverCard icon={Dices} accent="#a78bfa" title="Distance from chance" metric="z-score vs. null model" delay={0.12}>
            <p className="mt-5 flex items-baseline gap-3">
              <span className="text-6xl font-extrabold tabular-nums tracking-tight" style={{ color: '#a78bfa' }}>
                {zVal.toFixed(2)}
              </span>
            </p>
            <p className="mt-1 text-xs text-zinc-500 tabular-nums">
              {zBefore} → {zAfter} · significant beyond z = {zSig}
            </p>
            <ZScale value={zVal} sig={zSig} />
            <div className="mt-4 grid grid-cols-2 gap-2">
              <figure>
                <img src="/static/improvement/space_before_clean.png" alt="scenario field before"
                  className="w-full aspect-square object-cover rounded-lg border border-white/10 opacity-60" />
                <figcaption className="mt-1 text-center text-[11px] text-zinc-500 tabular-nums">
                  before · z = {zBefore}
                </figcaption>
              </figure>
              <motion.figure initial={false} animate={{ opacity: on ? 1 : 0.25 }} transition={{ duration: 0.7 }}>
                <AfterField points={data?.field?.points} />
                <figcaption className="mt-1 text-center text-[11px] text-emerald-300/80 tabular-nums">
                  after · z = {zAfter} · 5 archetypes
                </figcaption>
              </motion.figure>
            </div>
            <p className="mt-4 text-xs leading-relaxed text-zinc-500">
              Corpus enrichment + 4 driving dimensions: significantly above random.
            </p>
          </LeverCard>

          <LeverCard icon={Layers} accent="#60a5fa" title="Sharper corpus" metric="text chunks" delay={0.24}>
            <p className="mt-5 flex items-baseline gap-3">
              <span className="text-6xl font-extrabold tabular-nums tracking-tight" style={{ color: '#60a5fa' }}>
                {Math.round(cVal).toLocaleString('en-US')}
              </span>
              <motion.span
                initial={false}
                animate={on ? { opacity: 1 } : { opacity: 0 }}
                transition={{ duration: 0.6, delay: 0.4 }}
                className="text-xl font-bold text-emerald-300 tabular-nums"
              >
                +{(cAfter - cBefore).toLocaleString('en-US')}
              </motion.span>
            </p>
            <p className="mt-1 text-xs text-zinc-500 tabular-nums">
              {cBefore.toLocaleString('en-US')} → {cAfter.toLocaleString('en-US')} chunks
            </p>
            <CorpusBar value={cVal} before={cBefore} max={cMax} />
            <p className="mt-5 text-xs leading-relaxed text-zinc-500">
              Targeted arXiv + OECD/GSMA/NTIA reports; per-source cap breaks mega-doc dominance.
            </p>
          </LeverCard>
        </div>

        <div className="mt-10 h-16 flex items-center justify-center shrink-0">
          <motion.p
            initial={false}
            animate={on ? { opacity: 1, scale: 1, rotate: -1.5 } : { opacity: 0, scale: 1.6, rotate: -8 }}
            transition={{ type: 'spring', stiffness: 300, damping: 20 }}
            className="px-6 py-2.5 rounded-xl border-2 border-emerald-400/50 text-2xl font-bold text-white tracking-tight"
          >
            Inputs fixed first. <span className="text-emerald-300">Outputs untouched.</span>
          </motion.p>
        </div>
      </div>
    </SlideFrame>
  )
}
