import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

function truncate(str, len = 25) {
  return str.length > len ? str.slice(0, len) + '...' : str
}

export default function SimilarityHeatmap({ matrix, scenarioIds, scenarioTitles }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!ref.current || !matrix?.length) return

    const labels = scenarioTitles.map(t => truncate(t))
    const n = scenarioTitles.length

    const hoverText = matrix.map((row, i) =>
      row.map(
        (val, j) =>
          scenarioTitles[i] + ' vs ' + scenarioTitles[j] + ': ' + val.toFixed(2),
      ),
    )

    const trace = {
      type: 'heatmap',
      z: matrix,
      x: labels,
      y: labels,
      text: hoverText,
      hoverinfo: 'text',
      colorscale: [
        [0, '#1e1b4b'],
        [0.5, '#3b82f6'],
        [1, '#10b981'],
      ],
      zmin: 0,
      zmax: 1,
      colorbar: {
        tickfont: { color: '#a1a1aa', size: 10 },
        titlefont: { color: '#a1a1aa' },
      },
    }

    const layout = {
      ...DARK_LAYOUT,
      height: 500,
      xaxis: {
        ...DARK_LAYOUT.xaxis,
        tickangle: -45,
        tickfont: { size: 10, color: '#a1a1aa' },
      },
      yaxis: {
        ...DARK_LAYOUT.yaxis,
        tickfont: { size: 10, color: '#a1a1aa' },
        autorange: 'reversed',
      },
      margin: { t: 20, r: 80, b: 120, l: 120 },
    }

    Plotly.react(ref.current, [trace], layout, PLOTLY_CONFIG)

    return () => {
      if (ref.current) Plotly.purge(ref.current)
    }
  }, [matrix, scenarioIds, scenarioTitles])

  return <div ref={ref} />
}
