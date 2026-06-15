import { useRef, useEffect, useCallback, useMemo } from 'react'
import Plotly from 'plotly.js-dist-min'
import { CIB_QUADRANT_COLORS } from '@/utils/colors'

function getQuadrant(inf, dep, medInf, medDep) {
  if (inf >= medInf && dep >= medDep) return 'critical'
  if (inf >= medInf && dep < medDep) return 'enabler'
  if (inf < medInf && dep >= medDep) return 'dependent'
  return 'isolated'
}

function median(arr) {
  const sorted = [...arr].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function shortName(name, len = 24) {
  return name.length > len ? name.slice(0, len) + '...' : name
}

const EDGE_TIERS = [
  { min: 3, width: 5 },
  { min: 2, width: 3 },
  { min: 1, width: 1.5 },
]

const SCENE = {
  xaxis: { showgrid: true, gridcolor: 'rgba(161,161,170,0.06)', showticklabels: false, title: '', zeroline: false, showspikes: false },
  yaxis: { showgrid: true, gridcolor: 'rgba(161,161,170,0.06)', showticklabels: false, title: '', zeroline: false, showspikes: false },
  zaxis: { showgrid: true, gridcolor: 'rgba(161,161,170,0.06)', showticklabels: false, title: '', zeroline: false, showspikes: false },
  bgcolor: 'rgba(0,0,0,0)',
}

export default function ForceNetwork3D({ nodes, edges, selectedId, onNodeClick }) {
  const ref = useRef(null)
  const rotatingRef = useRef(true)
  const rafRef = useRef(null)

  const posById = useMemo(() => {
    const m = {}
    for (const n of nodes) m[n.id] = n
    return m
  }, [nodes])

  const infValues = useMemo(() => nodes.map(n => n.influence), [nodes])
  const depValues = useMemo(() => nodes.map(n => n.dependence), [nodes])
  const medInf = useMemo(() => median(infValues), [infValues])
  const medDep = useMemo(() => median(depValues), [depValues])
  const maxInf = useMemo(() => Math.max(...infValues, 1), [infValues])

  const buildTraces = useCallback(() => {
    const quadrants = {}
    for (const n of nodes) {
      const q = getQuadrant(n.influence, n.dependence, medInf, medDep)
      if (!quadrants[q]) quadrants[q] = []
      quadrants[q].push(n)
    }

    const traces = []

    Object.entries(quadrants).forEach(([q, qNodes]) => {
      traces.push({
        type: 'scatter3d',
        mode: 'markers+text',
        name: q.charAt(0).toUpperCase() + q.slice(1),
        x: qNodes.map(n => n.x),
        y: qNodes.map(n => n.y),
        z: qNodes.map(n => n.z),
        text: qNodes.map(n => shortName(n.name)),
        customdata: qNodes.map(n => n.id),
        hovertext: qNodes.map(n => `${n.name}\nInfluence: ${n.influence}\nDependence: ${n.dependence}`),
        hoverinfo: 'text',
        textposition: 'top center',
        textfont: { size: 9, color: '#a1a1aa' },
        marker: {
          size: qNodes.map(n => 8 + (n.influence / maxInf) * 18),
          color: CIB_QUADRANT_COLORS[q],
          opacity: qNodes.map(n => (selectedId && n.id !== selectedId) ? 0.15 : 0.9),
          line: { color: CIB_QUADRANT_COLORS[q], width: 1 },
        },
      })
    })

    if (selectedId) {
      const sel = posById[selectedId]
      if (sel) {
        traces.push({
          type: 'scatter3d',
          mode: 'markers',
          x: [sel.x],
          y: [sel.y],
          z: [sel.z],
          marker: {
            size: 20 + (sel.influence / maxInf) * 14,
            color: 'rgba(59,130,246,0.3)',
            line: { color: '#3b82f6', width: 2 },
          },
          hoverinfo: 'skip',
          showlegend: false,
        })
      }
    }

    const connectedIds = selectedId
      ? new Set(edges.filter(e => e.source === selectedId || e.target === selectedId).flatMap(e => [e.source, e.target]))
      : null

    for (const tier of EDGE_TIERS) {
      for (const polarity of ['promoting', 'inhibiting']) {
        const filtered = edges.filter(e => {
          const abs = Math.abs(e.score)
          const nextTier = EDGE_TIERS[EDGE_TIERS.indexOf(tier) - 1]
          const inTier = nextTier ? abs >= tier.min && abs < nextTier.min : abs >= tier.min
          return inTier && (polarity === 'promoting' ? e.score > 0 : e.score < 0)
        })
        if (!filtered.length) continue

        const x = [], y = [], z = []
        for (const e of filtered) {
          const s = posById[e.source], t = posById[e.target]
          if (!s || !t) continue
          x.push(s.x, t.x, null)
          y.push(s.y, t.y, null)
          z.push(s.z, t.z, null)
        }

        const isConnected = !selectedId || filtered.some(e => connectedIds?.has(e.source) && connectedIds?.has(e.target))
        const baseColor = polarity === 'promoting' ? '#10b981' : '#ef4444'

        traces.push({
          type: 'scatter3d',
          mode: 'lines',
          x, y, z,
          line: {
            color: baseColor,
            width: tier.width,
          },
          opacity: selectedId ? (isConnected ? 0.7 : 0.04) : 0.35,
          hoverinfo: 'skip',
          showlegend: false,
        })
      }
    }

    return traces
  }, [nodes, edges, selectedId, posById, medInf, medDep, maxInf])

  useEffect(() => {
    if (!ref.current || !nodes.length) return

    const traces = buildTraces()
    const layout = {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#a1a1aa', family: 'Inter, system-ui, sans-serif', size: 11 },
      scene: {
        ...SCENE,
        camera: { eye: { x: 2.0, y: 2.0, z: 1.2 } },
      },
      legend: {
        font: { color: '#d4d4d8', size: 11 },
        bgcolor: 'rgba(0,0,0,0)',
        x: 0.01,
        y: 0.99,
      },
      margin: { t: 0, r: 0, b: 0, l: 0 },
      height: 650,
    }

    Plotly.react(ref.current, traces, layout, { displayModeBar: false, responsive: true })

    ref.current.on('plotly_click', (data) => {
      const pt = data.points[0]
      if (pt?.customdata && onNodeClick) {
        onNodeClick(pt.customdata)
      }
    })

    ref.current.on('plotly_relayouting', () => {
      rotatingRef.current = false
    })

    // Auto-rotation
    let angle = 0
    rotatingRef.current = !selectedId

    function rotate() {
      if (!rotatingRef.current || !ref.current) return
      angle += 0.004
      const r = 2.5
      Plotly.relayout(ref.current, {
        'scene.camera.eye': {
          x: r * Math.cos(angle),
          y: r * Math.sin(angle),
          z: 1.0,
        },
      })
      rafRef.current = requestAnimationFrame(rotate)
    }

    if (!selectedId) {
      rafRef.current = requestAnimationFrame(rotate)
    }

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
      if (ref.current) {
        ref.current.removeAllListeners?.('plotly_click')
        ref.current.removeAllListeners?.('plotly_relayouting')
      }
    }
  }, [nodes, edges, selectedId, buildTraces, onNodeClick])

  return <div ref={ref} className="w-full rounded-xl" />
}
