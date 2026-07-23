import { useEffect, useMemo, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import Plotly from 'plotly.js-dist-min'
import SlideFrame from './SlideFrame'
import { archetypeColor, CONTINUUM_COLOR } from '@/utils/colors'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

export const STEPS = 4

const CAPTIONS = [
  'k-means forces every point into a ball, even where there is no cluster.',
  'Ordinal coding keeps the optimistic → pessimistic ordering of factor states.',
  'HDBSCAN allows an honest noise halo: clusters only where density is real.',
  'Ordered states + honest noise: the lens finally fits the field.',
]

/* Animates from the current displayed value to `target`; updates only inside rAF. */
function useAnimatedNumber(target, duration = 900) {
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

/* Vertical 0..max thermometer with the 'usable clusters' floor line.
 * The floor line flashes emerald the moment the fill crosses it. */
function SilhouetteScale({ value, floor, max = 0.5 }) {
  const pct = (v) => Math.min(Math.max(v / max, 0), 1) * 100
  const crossed = value >= floor
  return (
    <div className="relative h-44 w-32">
      <div className="absolute left-8 top-0 bottom-0 w-3 rounded-full bg-zinc-800 overflow-hidden">
        <div
          className="absolute bottom-0 left-0 right-0"
          style={{ height: `${pct(value)}%`, backgroundColor: crossed ? '#34d399' : '#a78bfa' }}
        />
      </div>
      <motion.div
        className="absolute left-5 w-9 h-[2px] rounded-full"
        style={{ bottom: `${pct(floor)}%` }}
        animate={crossed
          ? {
              backgroundColor: '#34d399',
              boxShadow: [
                '0 0 0px rgba(52,211,153,0)',
                '0 0 18px rgba(52,211,153,0.95)',
                '0 0 5px rgba(52,211,153,0.35)',
              ],
            }
          : { backgroundColor: '#71717a', boxShadow: '0 0 0px rgba(52,211,153,0)' }}
        transition={{ duration: 0.8 }}
      />
      <span className="absolute right-0 top-0 text-[11px] text-zinc-500 tabular-nums">{max.toFixed(2)}</span>
      <span
        className={`absolute right-0 translate-y-1/2 text-[11px] tabular-nums ${crossed ? 'text-emerald-400' : 'text-zinc-500'}`}
        style={{ bottom: `${pct(floor)}%` }}
      >
        {floor.toFixed(2)} usable
      </span>
      <span className="absolute right-0 bottom-0 text-[11px] text-zinc-500 tabular-nums">0</span>
    </div>
  )
}

export default function LensMorphScene({ data, step }) {
  const progression = data?.improvement?.lens_progression ?? []
  const labels = data?.lenses?.labels
  const points = data?.field?.points
  const floor = data?.lenses?.floor ?? 0.25

  // Steps 0..3 drive the lens; a button click overrides locally. Any deck-step
  // change clears the override (render-phase adjustment — the sanctioned
  // "derive state from props" pattern, so no state sync in effects).
  const [override, setOverride] = useState(null)
  const [lastSeenStep, setLastSeenStep] = useState(step)
  if (lastSeenStep !== step) {
    setLastSeenStep(step)
    setOverride(null)
  }
  const lastIdx = Math.max(progression.length - 1, 0)
  const stepIdx = Math.min(Math.max(step ?? 0, 0), lastIdx)
  const lensIdx = override != null ? Math.min(override, lastIdx) : stepIdx
  const lens = progression[lensIdx] ?? { name: '—', key: null, silhouette: 0 }
  const lensKey = lens.key

  // id → row index in the label arrays, built once (not indexOf per point).
  const idToIndex = useMemo(() => {
    const m = new Map()
    const ids = labels?.ids ?? []
    for (let i = 0; i < ids.length; i++) m.set(ids[i], i)
    return m
  }, [labels])

  // One group per cluster label; continuum (−1) last so it sits at the legend end.
  // Each cluster is colored by its MAJORITY archetype via the shared archetypeColor
  // mapping, so this scene never disagrees with the archetype/3D scenes about which
  // color means which cluster — and the k-means groups visibly "converge" onto the
  // archetype colors as the lens improves.
  const groups = useMemo(() => {
    const arr = (lensKey && labels?.[lensKey]) || []
    const allArch = (points ?? []).map((p) => p.archetype)
    const byLabel = new Map()
    for (const p of points ?? []) {
      const idx = idToIndex.get(p.id)
      const lab = idx === undefined ? -1 : (arr[idx] ?? -1)
      if (!byLabel.has(lab)) byLabel.set(lab, [])
      byLabel.get(lab).push(p)
    }
    const keys = [...byLabel.keys()].sort((a, b) => a - b)
    const ordered = [...keys.filter((k) => k >= 0), ...keys.filter((k) => k < 0)]
    const isFinalLens = lensKey === 'ordinal_hdbscan'
    return ordered.map((lab) => {
      const pts = byLabel.get(lab)
      const counts = {}
      for (const p of pts) counts[p.archetype] = (counts[p.archetype] || 0) + 1
      const major = Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0]
      return {
        label: lab,
        // The final lens IS the archetype clustering — name its groups honestly.
        name: lab < 0 ? 'continuum' : isFinalLens && major && major !== 'Continuum'
          ? major
          : `cluster ${lab + 1}`,
        color: lab < 0 ? CONTINUUM_COLOR : archetypeColor(major, allArch),
        pts,
      }
    })
  }, [labels, lensKey, points, idToIndex])

  const plotRef = useRef(null)
  useEffect(() => {
    const el = plotRef.current
    if (!el || !groups.length) return
    const traces = groups.map((g) => ({
      type: 'scatter',
      mode: 'markers',
      name: g.name,
      x: g.pts.map((p) => p.cx),
      y: g.pts.map((p) => p.cy),
      text: g.pts.map((p) => `<b>${p.title}</b><br>${g.name}`),
      hoverinfo: 'text',
      marker: g.label < 0
        ? { color: CONTINUUM_COLOR, opacity: 0.35, size: 5 }
        : {
            color: g.color,
            opacity: 0.9,
            size: 9,
            line: { color: 'rgba(255,255,255,0.35)', width: 0.5 },
          },
    }))
    const layout = {
      ...DARK_LAYOUT,
      height: 540,
      uirevision: 'lens-morph',
      hovermode: 'closest',
      showlegend: true,
      legend: {
        orientation: 'h',
        y: 1.02,
        yanchor: 'bottom',
        font: { color: '#d4d4d8', size: 12 },
        bgcolor: 'rgba(0,0,0,0)',
      },
      xaxis: { ...DARK_LAYOUT.xaxis, title: { text: 'PC 1', font: { size: 12, color: '#a1a1aa' } }, zeroline: false },
      yaxis: { ...DARK_LAYOUT.yaxis, title: { text: 'PC 2', font: { size: 12, color: '#a1a1aa' } }, zeroline: false },
      margin: { t: 40, r: 10, b: 45, l: 50 },
    }
    Plotly.react(el, traces, layout, PLOTLY_CONFIG)
  }, [groups])

  useEffect(() => {
    const el = plotRef.current
    return () => {
      if (el) Plotly.purge(el)
    }
  }, [])

  const silVal = useAnimatedNumber(lens.silhouette ?? 0)
  const crossed = silVal >= floor
  // Punchline only when the DECK reached the last step AND the last lens is showing —
  // a curious early button-click must not spoil the ending.
  const done = progression.length > 0 && stepIdx === lastIdx && lensIdx === lastIdx

  return (
    <SlideFrame
      kicker="Improvement · the lens, not the data"
      kickerColor="#10b981"
      title="Same field, four lenses"
      subtitle="120 scenarios, identical coordinates. Only the clustering lens changes."
      wide
    >
      <div className="h-full flex flex-col">
        <div className="flex gap-3 mb-4 shrink-0">
          {progression.map((l, i) => {
            const active = i === lensIdx
            return (
              <button
                key={l.key ?? i}
                onClick={(e) => {
                  setOverride(i)
                  e.currentTarget.blur()
                }}
                className={`px-4 py-2 rounded-xl border text-sm font-semibold transition-colors ${
                  active
                    ? 'border-emerald-400/70 bg-emerald-400/10 text-white'
                    : 'glass border-white/10 text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <span className="mr-2 text-xs text-zinc-500 tabular-nums">{i + 1}</span>
                {l.name}
                <span className={`ml-2 text-xs tabular-nums ${active ? 'text-emerald-300' : 'text-zinc-500'}`}>
                  {(l.silhouette ?? 0).toFixed(2)}
                </span>
              </button>
            )
          })}
        </div>

        <div className="flex-1 min-h-0 flex gap-8">
          <div className="flex-1 min-w-0 glass rounded-2xl px-2 pt-1">
            <div ref={plotRef} className="w-full" />
          </div>

          <div className="w-80 shrink-0 flex flex-col items-center justify-center gap-6">
            <div className="text-center">
              <p className="text-[11px] uppercase tracking-[0.2em] text-zinc-500">silhouette score</p>
              <p
                className={`mt-1 text-7xl font-extrabold tabular-nums tracking-tight ${
                  crossed ? 'text-emerald-300' : 'text-zinc-100'
                }`}
              >
                {silVal.toFixed(3)}
              </p>
              <p className="mt-1 text-xs text-zinc-500">
                {crossed ? 'above' : 'below'} the {floor.toFixed(2)} usable-clusters floor
              </p>
            </div>

            <SilhouetteScale value={silVal} floor={floor} />

            <motion.p
              key={lensIdx}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
              className="min-h-[3rem] text-sm text-zinc-400 text-center leading-relaxed"
            >
              {CAPTIONS[lensIdx] ?? ''}
            </motion.p>

            <div className="h-24 flex items-center">
              <motion.div
                initial={false}
                animate={done ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 1.5 }}
                transition={{ type: 'spring', stiffness: 260, damping: 20 }}
              >
                <p className="text-lg font-bold text-white text-center leading-snug">
                  The structure was always there. We changed the lens.
                </p>
                <p className="mt-1.5 text-sm font-semibold text-emerald-300 text-center">
                  5 archetypes + 33% honest continuum
                </p>
              </motion.div>
            </div>
          </div>
        </div>
      </div>
    </SlideFrame>
  )
}
