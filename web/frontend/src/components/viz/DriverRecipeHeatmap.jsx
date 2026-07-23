import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

// Driver-recipe heatmap: rows = scenarios sorted by PC1, columns = drivers, cell colour =
// the scenario's manifestation for that driver, normalised optimistic(0)→pessimistic(1).
// Scales cleanly to many drivers where parallel-coordinates turn into a cable tangle — the
// continuum reads as smooth colour bands shifting as you move down the PC1 axis.
const TRUNC = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

// optimistic → pessimistic: teal → amber → red (good → bad), legible on the dark theme.
const SCALE = [
  [0, '#14b8a6'],
  [0.5, '#fbbf24'],
  [1, '#ef4444'],
]

export default function DriverRecipeHeatmap({ parcoords }) {
  const ref = useRef(null)

  useEffect(() => {
    const drivers = parcoords?.drivers || []
    const rows = parcoords?.rows || []
    if (!ref.current || !drivers.length || !rows.length) return

    // Sort scenarios by PC1 (low at top → high at bottom, matching the axis).
    const ordered = [...rows].sort((a, b) => a.pc1 - b.pc1)
    const spans = drivers.map((d) => Math.max(1, d.manifestations.length - 1))

    const z = ordered.map((r) =>
      r.values.map((v, j) => (v < 0 ? null : v / spans[j])),
    )
    const text = ordered.map((r) =>
      r.values.map((v, j) =>
        v < 0
          ? ''
          : `${drivers[j].name}<br>${drivers[j].manifestations[v]}<br><span style="color:#a1a1aa">${r.scenario_id}</span>`,
      ),
    )

    const trace = {
      type: 'heatmap',
      z,
      text,
      // Numeric x + explicit ticks: categorical labels would silently MERGE two drivers
      // whose names truncate to the same string.
      x: drivers.map((_, j) => j),
      hoverinfo: 'text',
      hoverongaps: false,
      xgap: 1,
      ygap: 0,
      colorscale: SCALE,
      zmin: 0,
      zmax: 1,
      colorbar: {
        title: { text: 'optimistic → pessimistic', side: 'right', font: { color: '#a1a1aa', size: 11 } },
        tickvals: [0, 1],
        ticktext: ['opt.', 'pess.'],
        tickfont: { color: '#a1a1aa', size: 10 },
        thickness: 12,
        len: 0.9,
      },
    }

    const layout = {
      ...DARK_LAYOUT,
      height: Math.min(680, Math.max(320, ordered.length * 4 + 120)),
      margin: { t: 20, r: 30, b: 130, l: 60 },
      xaxis: {
        ...DARK_LAYOUT.xaxis,
        tickangle: -45,
        tickfont: { size: 10, color: '#a1a1aa' },
        ticks: '',
        tickmode: 'array',
        tickvals: drivers.map((_, j) => j),
        ticktext: drivers.map((d) => TRUNC(d.name, 26)),
      },
      yaxis: {
        ...DARK_LAYOUT.yaxis,
        title: { text: 'scenarios — PC1 low → high', font: { size: 12, color: '#a1a1aa' } },
        showticklabels: false,
        ticks: '',
        autorange: 'reversed', // low PC1 at the top
      },
    }

    Plotly.react(ref.current, [trace], layout, PLOTLY_CONFIG)

    const el = ref.current
    return () => {
      if (el) Plotly.purge(el)
    }
  }, [parcoords])

  return <div ref={ref} />
}
