import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { SCENARIO_TYPE_COLORS } from '@/utils/colors'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

const TYPES = ['evolutionary', 'disruptive', 'cautionary', 'wildcard']

export default function UMAPScatter({ points, onPointClick }) {
  const ref = useRef(null)

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
        x: pts.map(p => p.x),
        y: pts.map(p => p.y),
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
          size: pts.map(p => 10 + p.consistency_score / 10),
          symbol: pts.map(p => (p.is_fixed_point ? 'circle' : 'diamond')),
          line: { color: colors.border, width: 1 },
        },
      }
    })

    const layout = {
      ...DARK_LAYOUT,
      height: 500,
      xaxis: {
        ...DARK_LAYOUT.xaxis,
        title: { text: 'UMAP Dimension 1', font: { size: 12, color: '#a1a1aa' } },
      },
      yaxis: {
        ...DARK_LAYOUT.yaxis,
        title: { text: 'UMAP Dimension 2', font: { size: 12, color: '#a1a1aa' } },
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
  }, [points, onPointClick])

  return <div ref={ref} />
}
