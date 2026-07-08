import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { SCENARIO_TYPE_COLORS } from '@/utils/colors'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

const TYPES = ['evolutionary', 'disruptive', 'cautionary', 'wildcard']

// Sampled methods carry interpretable PCA coords (cx/cy) + axis labels; the CIB
// fixed-point path has only the legacy UMAP x/y. Prefer the PCA coords when present.
const DEFAULT_AXES = ['UMAP Dimension 1', 'UMAP Dimension 2']

// Distinct hues for named archetype clusters; the continuum halo (noise) is muted gray.
const CLUSTER_PALETTE = ['#5B8FF9', '#61DDAA', '#F6BD16', '#F08BB4', '#7262FD',
                         '#78D3F8', '#F6903D', '#008685', '#D95040', '#9FB40F']
const CONTINUUM_COLOR = '#6b7280'

export default function UMAPScatter({ points, onPointClick, axisTitles = DEFAULT_AXES, colorBy = 'type' }) {
  const ref = useRef(null)
  const hasPca = points?.some((p) => p.cx !== undefined)
  const X = (p) => (hasPca ? p.cx : p.x)
  const Y = (p) => (hasPca ? p.cy : p.y)

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
        groups.push({ name, color: CLUSTER_PALETTE[i % CLUSTER_PALETTE.length], pts: byArch[name] }))
      if (byArch['Continuum'])
        groups.push({ name: 'Continuum', color: CONTINUUM_COLOR, pts: byArch['Continuum'] })
    } else {
      for (const t of TYPES) {
        const pts = points.filter((p) => (p.type || 'evolutionary') === t)
        if (pts.length) {
          const c = SCENARIO_TYPE_COLORS[t]
          groups.push({ name: t, color: c.dot, border: c.border, pts })
        }
      }
    }

    const traces = groups.map((g) => ({
      type: 'scatter',
      mode: 'markers',
      name: g.name,
      x: g.pts.map(X),
      y: g.pts.map(Y),
      text: g.pts.map((p) =>
        `${p.title}\n${colorBy === 'archetype' ? (p.archetype || 'Continuum') : p.type}` +
        `\nScore: ${(p.consistency_score ?? 0).toFixed(1)}`),
      hoverinfo: 'text',
      customdata: g.pts.map((p) => p.scenario_id),
      marker: {
        color: g.color,
        // Cluster representatives (combinatorial method) are enlarged and ringed.
        size: g.pts.map((p) => (10 + (p.consistency_score ?? 0) / 10) * (p.is_representative ? 1.8 : 1)),
        symbol: g.pts.map((p) => (p.is_fixed_point ? 'circle' : 'diamond')),
        line: { color: g.border || 'rgba(255,255,255,0.25)',
                width: g.pts.map((p) => (p.is_representative ? 3 : 1)) },
      },
    }))

    const layout = {
      ...DARK_LAYOUT,
      height: 500,
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
  }, [points, onPointClick, axisTitles, colorBy])

  return <div ref={ref} />
}
