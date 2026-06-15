import { useEffect, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { RADAR_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

const CRITERIA_LABELS = {
  impact: 'Impact',
  probability: 'Probability',
  actionability: 'Actionability',
  time_horizon: 'Time Horizon',
  risk_severity: 'Risk Severity',
}

export default function RadarChart({ assessment, color = '#3b82f6', height = 280 }) {
  const ref = useRef(null)

  useEffect(() => {
    if (!ref.current || !assessment) return

    const keys = Object.keys(CRITERIA_LABELS)
    const values = keys.map(k => assessment[k] || 0)
    const labels = keys.map(k => CRITERIA_LABELS[k])

    Plotly.react(ref.current, [{
      type: 'scatterpolar',
      r: [...values, values[0]],
      theta: [...labels, labels[0]],
      fill: 'toself',
      fillcolor: color + '15',
      line: { color, width: 2 },
      marker: { size: 5, color },
    }], {
      ...RADAR_LAYOUT,
      height,
    }, PLOTLY_CONFIG)

    return () => {
      if (ref.current) Plotly.purge(ref.current)
    }
  }, [assessment, color, height])

  return <div ref={ref} />
}
