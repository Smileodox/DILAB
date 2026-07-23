import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { SCENARIO_TYPE_COLORS, ARCHETYPE_PALETTE, CONTINUUM_COLOR } from '@/utils/colors'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

const TYPES = ['evolutionary', 'disruptive', 'cautionary', 'wildcard']

// Sampled methods carry interpretable PCA coords (cx/cy) + axis labels; the CIB
// fixed-point path has only the legacy UMAP x/y. Prefer the PCA coords when present.
// projection='ordinal' switches to the cluster-space coords (ox/oy: UMAP of the same
// ordinal matrix the archetype HDBSCAN clustered) when the points carry them.
const DEFAULT_AXES = ['UMAP Dimension 1', 'UMAP Dimension 2']

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

export default function UMAPScatter({ points, onPointClick, axisTitles = DEFAULT_AXES, colorBy = 'type', projection = 'pca' }) {
  const ref = useRef(null)
  const hasPca = points?.some((p) => p.cx !== undefined)
  const ordinal = projection === 'ordinal' && points?.some((p) => p.ox !== undefined)
  const X = (p) => (ordinal ? p.ox : hasPca ? p.cx : p.x)
  const Y = (p) => (ordinal ? p.oy : hasPca ? p.cy : p.y)

  useEffect(() => {
    if (!ref.current || !points?.length) return

    // One trace per group. Group either by scenario type or by archetype cluster.
    const groups = []
    if (colorBy === 'archetype') {
      const byArch = {}
      for (const p of points) {
        const key = p.archetype || 'Continuum'
        ;(byArch[key] = byArch[key] || []).push(p)
      }
      const named = Object.keys(byArch).filter((k) => k !== 'Continuum').sort()
      named.forEach((name, i) =>
        groups.push({ name, color: ARCHETYPE_PALETTE[i % ARCHETYPE_PALETTE.length], pts: byArch[name] }))
      if (byArch['Continuum'])
        groups.push({ name: 'Continuum', color: CONTINUUM_COLOR, continuum: true, pts: byArch['Continuum'] })
    } else {
      for (const t of TYPES) {
        const pts = points.filter((p) => (p.type || 'evolutionary') === t)
        if (pts.length) {
          const c = SCENARIO_TYPE_COLORS[t]
          groups.push({ name: t, color: c.dot, border: c.border, pts })
        }
      }
    }

    // Representatives of named clusters get a size bump + ring; the continuum stays a
    // quiet backdrop so cluster boundaries survive 120 points on one plot.
    const ringed = (p, g) => p.is_representative && !g.continuum

    // Cluster-space extras: draw the continuum behind the named clusters and outline
    // each archetype with a faint convex hull, so the dense cores read as islands.
    const drawOrder = ordinal
      ? [...groups].sort((a, b) => (b.continuum ? 1 : 0) - (a.continuum ? 1 : 0))
      : groups
    const hullTraces = ordinal && colorBy === 'archetype'
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

    const traces = [...hullTraces, ...drawOrder.map((g) => ({
      type: 'scatter',
      mode: 'markers',
      name: g.name,
      x: g.pts.map(X),
      y: g.pts.map(Y),
      text: g.pts.map((p) =>
        `<b>${p.title}</b><br>${colorBy === 'archetype' ? (p.archetype || 'Continuum') : p.type}` +
        `<br>Consistency ${(p.consistency_score ?? 0).toFixed(0)}`),
      hoverinfo: 'text',
      customdata: g.pts.map((p) => p.scenario_id),
      marker: {
        color: g.color,
        opacity: g.continuum ? (ordinal ? 0.18 : 0.45) : (ordinal ? 0.9 : 0.85),
        size: g.pts.map((p) => (ringed(p, g) ? 16 : g.continuum ? (ordinal ? 4 : 6) : 9)),
        symbol: g.pts.map((p) => (p.is_fixed_point ? 'circle' : 'diamond')),
        line: { color: g.border || 'rgba(255,255,255,0.35)',
                width: g.pts.map((p) => (ringed(p, g) ? 2.5 : 0.5)) },
      },
    }))]

    const layout = {
      ...DARK_LAYOUT,
      height: 500,
      // Keep zoom/pan state across data-independent re-renders (e.g. point selection),
      // but reset it when the projection switches — the coordinate scales differ.
      uirevision: `landscape-${ordinal ? 'ordinal' : 'pca'}`,
      xaxis: { ...DARK_LAYOUT.xaxis, title: { text: axisTitles[0], font: { size: 12, color: '#a1a1aa' } } },
      yaxis: { ...DARK_LAYOUT.yaxis, title: { text: axisTitles[1], font: { size: 12, color: '#a1a1aa' } } },
      legend: { font: { color: '#d4d4d8', size: 11 }, bgcolor: 'rgba(0,0,0,0)' },
    }

    Plotly.react(ref.current, traces, layout, PLOTLY_CONFIG)

    const handler = (eventData) => {
      if (!eventData?.points?.length || !onPointClick) return
      const id = eventData.points[0].customdata
      if (id) onPointClick(id)
    }
    ref.current.on('plotly_click', handler)

    return () => {
      if (ref.current) {
        ref.current.removeAllListeners('plotly_click')
        Plotly.purge(ref.current)
      }
    }
  }, [points, onPointClick, axisTitles, colorBy, ordinal])

  return <div ref={ref} />
}
