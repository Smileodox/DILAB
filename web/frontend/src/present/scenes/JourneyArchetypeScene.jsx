import { useEffect, useMemo, useRef } from 'react'
import { motion } from 'framer-motion'
import Plotly from 'plotly.js-dist-min'
import { Fingerprint } from 'lucide-react'
import SlideFrame from './SlideFrame'
import { archetypeColor, CONTINUUM_COLOR } from '@/utils/colors'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

export const STEPS = 2

/*
 * Journey station 7 — archetypes take a stance.
 * Step 0: the same 120-point field, now colored by archetype. Drawn in cluster space
 * (ox/oy: UMAP of the ordinal matrix the archetype HDBSCAN actually clustered), so the
 * five archetypes read as islands with faint hulls; continuum dimmed behind them.
 * Step 1: the scatter yields ~45% of its width to five stance cards showing which
 * of OUR driver's futures each archetype chooses — or honestly refuses to.
 */

function hexToRgba(hex, alpha) {
  const n = parseInt(hex.replace('#', ''), 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`
}

// Monotone-chain convex hull; returns null for degenerate (<3 vertex) sets.
function convexHull(pts) {
  if (pts.length < 3) return null
  const s = [...pts].sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const cross = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
  const half = (iter) => {
    const out = []
    for (const p of iter) {
      while (out.length >= 2 && cross(out[out.length - 2], out[out.length - 1], p) <= 0) out.pop()
      out.push(p)
    }
    out.pop()
    return out
  }
  const hull = [...half(s), ...half([...s].reverse())]
  return hull.length >= 3 ? hull : null
}

export default function JourneyArchetypeScene({ data, step }) {
  const ref = useRef(null)
  const points = useMemo(() => data?.field?.points ?? [], [data])
  const stances = data?.journey?.archetype_stances ?? []
  const allLabels = points.map((p) => p?.archetype)
  const named = [...new Set(allLabels)].filter((l) => l && l !== 'Continuum').sort()
  const continuumCount = points.length - points.filter((p) => p?.archetype && p.archetype !== 'Continuum').length
  const hasOrdinal = points.some((p) => Number.isFinite(p?.ox))

  useEffect(() => {
    const el = ref.current
    if (!el || !points?.length) return
    const X = (p) => (hasOrdinal ? p.ox : p.x)
    const Y = (p) => (hasOrdinal ? p.oy : p.y)
    const labels = points.map((p) => p?.archetype)
    const namedGroups = [...new Set(labels)].filter((l) => l && l !== 'Continuum').sort()
    const groups = namedGroups.map((nm) => ({
      name: nm,
      color: archetypeColor(nm, labels),
      pts: points.filter((p) => p?.archetype === nm),
    }))
    const continuum = points.filter((p) => !p?.archetype || p.archetype === 'Continuum')
    if (continuum.length) {
      // Cluster space: continuum behind the named clusters, so the islands stay readable.
      groups[hasOrdinal ? 'unshift' : 'push']({
        name: 'Continuum', color: CONTINUUM_COLOR, continuum: true, pts: continuum,
      })
    }
    // Faint convex hull per archetype (cluster space only) — same look as the Landscape tab.
    const hullTraces = hasOrdinal
      ? groups.filter((g) => !g.continuum).flatMap((g) => {
          const hull = convexHull(g.pts.map((p) => [X(p), Y(p)]))
          if (!hull) return []
          return [{
            type: 'scatter',
            mode: 'lines',
            x: [...hull.map((h) => h[0]), hull[0][0]],
            y: [...hull.map((h) => h[1]), hull[0][1]],
            fill: 'toself',
            fillcolor: hexToRgba(g.color, 0.08),
            line: { color: hexToRgba(g.color, 0.35), width: 1 },
            hoverinfo: 'skip',
            showlegend: false,
          }]
        })
      : []
    const traces = [...hullTraces, ...groups.map((g) => ({
      type: 'scatter',
      mode: 'markers',
      name: g.name,
      x: g.pts.map(X),
      y: g.pts.map(Y),
      text: g.pts.map((p) => `<b>${p.title}</b><br>${p.archetype ?? 'Continuum'}`),
      hoverinfo: 'text',
      marker: {
        color: g.color,
        opacity: g.continuum ? (hasOrdinal ? 0.18 : 0.35) : 0.9,
        symbol: 'diamond',
        size: g.pts.map((p) => (g.continuum ? 5 : p.is_representative ? 14 : hasOrdinal ? 10 : 9)),
        line: {
          color: 'rgba(255,255,255,0.35)',
          width: g.pts.map((p) => (!g.continuum && p.is_representative ? 2 : 0.5)),
        },
      },
    }))]
    const layout = {
      ...DARK_LAYOUT,
      autosize: true,
      showlegend: false,
      uirevision: 'journey-archetypes',
      margin: { t: 10, r: 10, b: 34, l: 42 },
      xaxis: {
        ...DARK_LAYOUT.xaxis,
        showticklabels: false,
        zeroline: false,
        title: { text: hasOrdinal ? 'UMAP 1 (ordinal)' : 'UMAP 1', font: { size: 11, color: '#71717a' } },
      },
      yaxis: {
        ...DARK_LAYOUT.yaxis,
        showticklabels: false,
        zeroline: false,
        title: { text: hasOrdinal ? 'UMAP 2 (ordinal)' : 'UMAP 2', font: { size: 11, color: '#71717a' } },
      },
      hoverlabel: { bgcolor: '#18181b', bordercolor: '#3f3f46', font: { color: '#e4e4e7', size: 12 } },
    }
    Plotly.react(el, traces, layout, PLOTLY_CONFIG)
  }, [points, hasOrdinal])

  // The stance panel changes the plot container width — settle Plotly after the slide.
  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    const t = setTimeout(() => {
      if (el.data) Plotly.Plots.resize(el)
    }, 500)
    return () => clearTimeout(t)
  }, [step])

  // Purge only on unmount.
  useEffect(() => {
    const el = ref.current
    return () => {
      if (el) Plotly.purge(el)
    }
  }, [])

  return (
    <SlideFrame
      kicker="station 7 · named archetypes"
      kickerColor="#10b981"
      title="The archetypes take a stance"
      subtitle="Five recurring patterns in the field, and what each of them assumes about our driver."
      wide
    >
      <div className="h-full flex flex-col min-h-0">
        <div className="flex-1 min-h-0 flex">
          {/* Scatter (shrinks left at step 1) + legend chips */}
          <motion.div
            initial={false}
            animate={{ width: step >= 1 ? '55%' : '100%' }}
            transition={{ duration: 0.45, ease: 'easeOut' }}
            className="min-w-0 flex flex-col min-h-0"
          >
            <div ref={ref} className="flex-1 min-h-0" />
            <div className="shrink-0 mt-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
              {named.map((nm) => (
                <span key={nm} className="flex items-center gap-1.5 text-xs text-zinc-300">
                  <span
                    className="w-2 h-2 rotate-45 shrink-0"
                    style={{ backgroundColor: archetypeColor(nm, allLabels) }}
                  />
                  {nm}
                </span>
              ))}
              <span className="flex items-center gap-1.5 text-xs text-zinc-500">
                <span className="w-2 h-2 rotate-45 shrink-0 opacity-50" style={{ backgroundColor: CONTINUUM_COLOR }} />
                Continuum · {continuumCount}
              </span>
            </div>
          </motion.div>

          {/* Step 1: stance cards */}
          <motion.div
            initial={false}
            animate={{ opacity: step >= 1 ? 1 : 0, x: step >= 1 ? 0 : 32 }}
            transition={{ duration: 0.45, ease: 'easeOut' }}
            className={`flex-1 min-w-0 min-h-0 overflow-hidden ${step >= 1 ? '' : 'pointer-events-none'}`}
          >
            <div className="h-full min-w-[360px] pl-6 flex flex-col justify-center gap-2.5 overflow-y-auto">
              {stances.map((s, i) => {
                const color = archetypeColor(s?.archetype, allLabels)
                const size = s?.size ?? 0
                const share = size > 0 ? ((s?.top_count ?? 0) / size) * 100 : 0
                return (
                  <motion.div
                    key={s?.archetype ?? i}
                    initial={{ opacity: 0, y: 12 }}
                    animate={step >= 1 ? { opacity: 1, y: 0 } : { opacity: 0, y: 12 }}
                    transition={{ duration: 0.35, delay: 0.12 + i * 0.09 }}
                    className="glass rounded-xl px-4 py-3 shrink-0"
                  >
                    <div className="flex items-center gap-2.5">
                      <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
                      <span className="flex-1 min-w-0 truncate text-sm font-semibold text-white">
                        {s?.archetype}
                      </span>
                      <span className="shrink-0 text-[11px] tabular-nums text-zinc-500">n={size}</span>
                    </div>
                    {s?.tie ? (
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full border border-amber-500/30 bg-amber-500/10 text-[11px] font-medium text-amber-300">
                          deliberately undecided
                        </span>
                        <span className="text-xs text-zinc-500">no majority: members split across futures</span>
                      </div>
                    ) : (
                      <div className="mt-2">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="text-xs text-zinc-300 min-w-0">
                            chooses: <span className="font-medium text-zinc-100">{s?.top}</span>
                          </span>
                          <span className="shrink-0 text-xs font-semibold tabular-nums text-zinc-400">
                            {s?.top_count}/{size}
                          </span>
                        </div>
                        <div className="mt-1.5 h-1.5 rounded-full bg-white/5 overflow-hidden">
                          <div
                            className="h-full rounded-full transition-[width] duration-700 ease-out"
                            style={{
                              width: step >= 1 ? `${share}%` : '0%',
                              backgroundColor: color,
                              transitionDelay: `${200 + i * 90}ms`,
                            }}
                          />
                        </div>
                      </div>
                    )}
                  </motion.div>
                )
              })}
            </div>
          </motion.div>
        </div>

        {/* Bottom traceability message */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={step >= 1 ? { opacity: 1, y: 0 } : { opacity: 0, y: 10 }}
          transition={{ duration: 0.4, delay: 0.5 }}
          className="mt-4 shrink-0 glass rounded-xl px-5 py-3 flex items-center gap-3"
        >
          <Fingerprint size={16} className="shrink-0 text-emerald-400" />
          <p className="text-sm text-zinc-300">
            Same driver that started as an OECD paragraph is now a defining trait of the archetypes:{' '}
            <span className="font-semibold text-white">every step traceable by ID</span>.
          </p>
        </motion.div>
      </div>
    </SlideFrame>
  )
}
