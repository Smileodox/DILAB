import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { SCENARIO_TYPE_COLORS } from '@/utils/colors'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

const TYPES = ['evolutionary', 'disruptive', 'cautionary', 'wildcard']

// Sampled methods carry interpretable PCA coords (cx/cy) + axis labels; the CIB
// fixed-point path has only the legacy UMAP x/y. Prefer the PCA coords when present.
const DEFAULT_AXES = ['UMAP Dimension 1', 'UMAP Dimension 2']

export default function UMAPScatter({ points, onPointClick, axisTitles = DEFAULT_AXES }) {
  const ref = useRef(null)
  const hasPca = points?.some((p) => p.cx !== undefined)
  const X = (p) => (hasPca ? p.cx : p.x)
  const Y = (p) => (hasPca ? p.cy : p.y)

  useEffect(() => {
    if (!ref.current || !points?.length) return

    const grouped = {}
    for (const t of TYPES) grouped[t] = []
    for (const p of points) {
      const bucket = grouped[p.type] || grouped.evolutionary
      bucket.push(p)
    }

    const traces = TYPES.filter(t => grouped[t].length > 0).map(type => {
      const pts = grouped[type]
      const colors = SCENARIO_TYPE_COLORS[type]
      return {
        type: 'scatter',
        mode: 'markers',
        name: type,
        x: pts.map(X),
        y: pts.map(Y),
        text: pts.map(
          p =>
            p.title +
            '\n' +
            p.type +
            '\nScore: ' +
            p.consistency_score.toFixed(1),
        ),
        hoverinfo: 'text',
        customdata: pts.map(p => p.scenario_id),
        marker: {
          color: colors.dot,
          // Cluster representatives (combinatorial method) are enlarged and ringed.
          // Baseline points have no is_representative flag → unchanged rendering.
          size: pts.map(p => (10 + p.consistency_score / 10) * (p.is_representative ? 1.8 : 1)),
          symbol: pts.map(p => (p.is_fixed_point ? 'circle' : 'diamond')),
          line: { color: colors.border, width: pts.map(p => (p.is_representative ? 3 : 1)) },
        },
      }
    })

    const layout = {
      ...DARK_LAYOUT,
      height: 500,
      xaxis: {
        ...DARK_LAYOUT.xaxis,
        title: { text: axisTitles[0], font: { size: 12, color: '#a1a1aa' } },
      },
      yaxis: {
        ...DARK_LAYOUT.yaxis,
        title: { text: axisTitles[1], font: { size: 12, color: '#a1a1aa' } },
      },
      legend: {
        font: { color: '#d4d4d8', size: 11 },
        bgcolor: 'rgba(0,0,0,0)',
      },
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
  }, [points, onPointClick, axisTitles])

  return <div ref={ref} />
}
