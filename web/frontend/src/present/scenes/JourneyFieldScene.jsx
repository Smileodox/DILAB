import { useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import Plotly from 'plotly.js-dist-min'
import { TrendingDown } from 'lucide-react'
import SlideFrame from './SlideFrame'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

export const STEPS = 3

/*
 * Journey station 5 — the field of 120 consistent scenarios.
 * Step 0: all survivors as neutral diamonds. Step 1: one Plotly.react recolors
 * them by what each scenario assumes for OUR driver (4 ordinal manifestation
 * colors, optimistic → pessimistic). Step 2: the distribution panel slides in.
 */

// Ordinal ramp for the driver's four manifestations, optimistic → pessimistic.
// Hue AND lightness separated — the two middle colors carry 82 of 120 points
// and must survive a washed-out projector.
const ORDINAL = ['#14b8a6', '#fde047', '#f97316', '#dc2626']
const NEUTRAL = '#71717a'

export default function JourneyFieldScene({ data, step }) {
  const ref = useRef(null)
  const points = data?.field?.points
  const sm = data?.journey?.scenario_manif
  const manifs = data?.journey?.manifestations
  const dist = data?.journey?.distribution ?? []
  const colored = step >= 1
  // Cluster-space coords (UMAP of the ordinal matrix the archetype HDBSCAN ran on) when
  // present — must match Station 7, which calls this "the same 120-point field". Legacy
  // x/y only as fallback for bundles without the backfill.
  const hasOrdinal = points?.some((p) => Number.isFinite(p?.ox)) ?? false

  const total = dist.reduce((s, d) => s + (d?.count ?? 0), 0)
  const maxCount = Math.max(1, ...dist.map((d) => d?.count ?? 0))
  const top = dist.reduce((a, b) => ((b?.count ?? 0) > (a?.count ?? 0) ? b : a), dist[0])

  // ONE Plotly.react per state change: trace-per-manifestation-group once colored.
  useEffect(() => {
    const el = ref.current
    if (!el || !points?.length) return
    let groups
    if (!colored) {
      groups = [{ name: 'consistent scenario', color: NEUTRAL, pts: points }]
    } else {
      groups = (manifs ?? []).map((m, i) => ({
        name: m?.label ?? `manifestation ${i}`,
        color: ORDINAL[i % ORDINAL.length],
        pts: points.filter((p) => sm?.[p.id] === i),
      }))
      const missing = points.filter((p) => sm?.[p.id] === undefined)
      if (missing.length) groups.push({ name: 'unmapped', color: NEUTRAL, pts: missing })
    }
    const traces = groups
      .filter((g) => g.pts.length)
      .map((g) => ({
        type: 'scatter',
        mode: 'markers',
        name: g.name,
        x: g.pts.map((p) => (hasOrdinal ? p.ox : p.x)),
        y: g.pts.map((p) => (hasOrdinal ? p.oy : p.y)),
        text: g.pts.map((p) => `<b>${p.title}</b>`),
        hoverinfo: 'text',
        marker: {
          color: g.color,
          size: 8,
          symbol: 'diamond',
          opacity: 0.85,
          line: { color: 'rgba(255,255,255,0.25)', width: 0.5 },
        },
      }))
    const layout = {
      ...DARK_LAYOUT,
      autosize: true,
      showlegend: false,
      uirevision: 'journey-field',
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
  }, [points, sm, manifs, colored, hasOrdinal])

  // The side panel changes the plot container width — settle Plotly after the slide.
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
      kicker="station 6 · the scenario field"
      kickerColor="#a78bfa"
      title="The consistent survivors of 268 million"
      subtitle="Every diamond is one complete 14-factor future that passed the cross-impact rules. Hover to read one."
      wide
    >
      <div className="h-full flex min-h-0">
        {/* Scatter + legend chips */}
        <div className="flex-1 min-w-0 flex flex-col min-h-0">
          <div ref={ref} className="flex-1 min-h-0" />
          <motion.div
            initial={false}
            animate={{ opacity: colored ? 1 : 0 }}
            transition={{ duration: 0.4 }}
            className="shrink-0 mt-3 min-h-[52px] flex flex-col items-center gap-1.5"
          >
            <p className="text-[11px] uppercase tracking-wider text-zinc-500">
              colored by what each scenario assumes for our driver: optimistic → pessimistic
            </p>
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
              {(manifs ?? []).map((m, i) => (
                <span key={m?.id ?? i} className="flex items-center gap-1.5 text-xs text-zinc-300">
                  <span
                    className="w-2 h-2 rotate-45 shrink-0"
                    style={{ backgroundColor: ORDINAL[i % ORDINAL.length] }}
                  />
                  {m?.label}
                </span>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Step 2: distribution panel slides in */}
        <motion.div
          initial={false}
          animate={{ width: step >= 2 ? 372 : 0, opacity: step >= 2 ? 1 : 0 }}
          transition={{ duration: 0.45, ease: 'easeOut' }}
          className="shrink-0 min-h-0 overflow-hidden"
        >
          <div className="w-[348px] ml-6 h-full glass rounded-2xl p-5 flex flex-col min-h-0">
            <p className="text-[11px] uppercase tracking-wider text-zinc-500 shrink-0">
              how often each future survives
            </p>
            <div className="mt-4 space-y-4 shrink-0">
              {dist.map((d, i) => (
                <div key={d?.label ?? i}>
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-xs text-zinc-300 truncate">{d?.label}</span>
                    <span className="text-sm font-bold tabular-nums text-white shrink-0">{d?.count}</span>
                  </div>
                  <div className="mt-1.5 h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-[width] duration-700 ease-out"
                      style={{
                        width: step >= 2 ? `${((d?.count ?? 0) / maxCount) * 100}%` : '0%',
                        backgroundColor: ORDINAL[i % ORDINAL.length],
                        transitionDelay: `${i * 120}ms`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-auto pt-4 flex items-start gap-2 border-t border-white/5">
              <TrendingDown size={15} className="mt-0.5 shrink-0 text-red-400" />
              <p className="text-xs leading-snug text-zinc-300">
                No single future wins, but consistency leans pessimistic:{' '}
                <span className="font-semibold text-white">
                  fragmentation survives most often ({top?.count ?? 0}/{total || 0})
                </span>
                .
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    </SlideFrame>
  )
}
