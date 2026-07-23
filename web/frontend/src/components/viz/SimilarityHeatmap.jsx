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

    // Off-diagonal similarities all sit near the top of [0,1] (cosine of narratives);
    // anchoring zmin at the real off-diagonal minimum keeps the contrast visible
    // instead of rendering a uniformly green square.
    let offDiagMin = 1
    matrix.forEach((row, i) =>
      row.forEach((val, j) => {
        if (i !== j && val < offDiagMin) offDiagMin = val
      }),
    )
    const zmin = offDiagMin >= 1 ? 0 : Math.max(0, offDiagMin - 0.02)

    const trace = {
      type: 'heatmap',
      z: matrix,
      x: labels,
      y: labels,
      text: hoverText,
      hoverinfo: 'text',
      // Small matrix (fixed-point set) — print the values right on the cells.
      texttemplate: n <= 12 ? '%{z:.2f}' : undefined,
      textfont: { size: 10, color: '#e4e4e7' },
      colorscale: [
        [0, '#1e1b4b'],
        [0.5, '#3b82f6'],
        [1, '#10b981'],
      ],
      zmin,
      zmax: 1,
      colorbar: {
        tickfont: { color: '#a1a1aa', size: 10 },
        title: { text: 'cosine similarity', side: 'right', font: { color: '#a1a1aa', size: 11 } },
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
