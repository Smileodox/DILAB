import { useState, useMemo, useCallback, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import Plotly from 'plotly.js-dist-min'
import { useKbApi } from '@/context/KbContext'
import ForceNetwork from '@/components/viz/ForceNetwork'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'
import { CIB_QUADRANT_COLORS } from '@/utils/colors'
import Card from '@/components/ui/Card'
import LoadError from '@/components/ui/LoadError'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

const TABS = [
  { key: 'network', label: 'Network' },
  { key: 'heatmap', label: 'Heatmap' },
  { key: 'influence', label: 'Influence' },
]

function median(arr) {
  const sorted = [...arr].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

/* ── Scatter sub-component ── */
function QuadrantScatter({ driverIds, driverNames, influence, dependence }) {
  const plotRef = useRef(null)

  const infVals = driverIds.map((id) => influence[id] || 0)
  const depVals = driverIds.map((id) => dependence[id] || 0)
  const medInf = median(infVals)
  const medDep = median(depVals)
  // Contrastive CIB yields negative influence/dependence too — axes must not clip below 0.
  const shortNames = driverNames.map((n) => (n.length > 20 ? n.slice(0, 19) + '…' : n))

  useEffect(() => {
    if (!plotRef.current) return

    const colors = driverIds.map((id) => {
      const inf = influence[id] || 0
      const dep = dependence[id] || 0
      if (inf >= medInf && dep < medDep) return CIB_QUADRANT_COLORS.enabler
      if (inf >= medInf && dep >= medDep) return CIB_QUADRANT_COLORS.critical
      if (inf < medInf && dep >= medDep) return CIB_QUADRANT_COLORS.dependent
      return CIB_QUADRANT_COLORS.isolated
    })

    const trace = {
      x: depVals,
      y: infVals,
      text: shortNames,
      hovertext: driverNames,
      hoverinfo: 'text+x+y',
      mode: 'markers+text',
      textposition: 'top center',
      textfont: { size: 10, color: '#a1a1aa' },
      marker: { size: 10, color: colors, opacity: 0.85 },
      type: 'scatter',
    }

    const minDep = Math.min(0, Math.min(...depVals)) * 1.15
    const maxDep = Math.max(...depVals) * 1.15
    const minInf = Math.min(0, Math.min(...infVals)) * 1.15
    const maxInf = Math.max(...infVals) * 1.15
    const posDep = (f) => minDep + (maxDep - minDep) * f
    const posInf = (f) => minInf + (maxInf - minInf) * f

    const layout = {
      ...DARK_LAYOUT,
      xaxis: {
        ...DARK_LAYOUT.xaxis,
        title: { text: 'Dependence', font: { size: 12, color: '#71717a' } },
        range: [minDep, maxDep],
      },
      yaxis: {
        ...DARK_LAYOUT.yaxis,
        title: { text: 'Influence', font: { size: 12, color: '#71717a' } },
        range: [minInf, maxInf],
      },
      shapes: [
        { type: 'line', x0: medDep, x1: medDep, y0: minInf, y1: maxInf, line: { color: 'rgba(161,161,170,0.2)', dash: 'dash' } },
        { type: 'line', x0: minDep, x1: maxDep, y0: medInf, y1: medInf, line: { color: 'rgba(161,161,170,0.2)', dash: 'dash' } },
      ],
      annotations: [
        { x: posDep(0.05), y: posInf(0.95), text: 'Enabler', showarrow: false, font: { color: CIB_QUADRANT_COLORS.enabler, size: 11 } },
        { x: posDep(0.95), y: posInf(0.95), text: 'Critical', showarrow: false, font: { color: CIB_QUADRANT_COLORS.critical, size: 11 } },
        { x: posDep(0.95), y: posInf(0.05), text: 'Dependent', showarrow: false, font: { color: CIB_QUADRANT_COLORS.dependent, size: 11 } },
        { x: posDep(0.05), y: posInf(0.05), text: 'Isolated', showarrow: false, font: { color: CIB_QUADRANT_COLORS.isolated, size: 11 } },
      ],
      height: 400,
      margin: { t: 20, r: 30, b: 50, l: 50 },
    }

    Plotly.react(plotRef.current, [trace], layout, PLOTLY_CONFIG)

    return () => {
      if (plotRef.current) Plotly.purge(plotRef.current)
    }
  }, [driverIds, driverNames, influence, dependence, infVals, depVals, medInf, medDep])

  return <div ref={plotRef} className="w-full" />
}

/* ── Heatmap sub-component ── */
function HeatmapTab({ matrix, stdMatrix, driverNames }) {
  const plotRef = useRef(null)
  const [showStd, setShowStd] = useState(false)

  const truncated = driverNames.map((n) =>
    n.length > 18 ? n.slice(0, 16) + '...' : n
  )
  const activeMatrix = showStd ? stdMatrix : matrix

  useEffect(() => {
    if (!plotRef.current || !activeMatrix) return

    const trace = {
      z: activeMatrix,
      x: truncated,
      y: truncated,
      type: 'heatmap',
      colorscale: showStd ? 'YlOrRd' : 'RdBu',
      zmin: showStd ? 0 : -3,
      zmax: showStd ? undefined : 3,
      reversescale: !showStd,
      colorbar: {
        tickfont: { color: '#a1a1aa', size: 10 },
        title: { text: showStd ? 'Std Dev' : 'Impact', font: { color: '#a1a1aa', size: 11 } },
      },
    }

    const layout = {
      ...DARK_LAYOUT,
      height: 520,
      margin: { t: 20, r: 20, b: 120, l: 120 },
      xaxis: { ...DARK_LAYOUT.xaxis, tickangle: -45, tickfont: { size: 10, color: '#a1a1aa' } },
      yaxis: { ...DARK_LAYOUT.yaxis, tickfont: { size: 10, color: '#a1a1aa' }, autorange: 'reversed' },
    }

    Plotly.react(plotRef.current, [trace], layout, PLOTLY_CONFIG)

    return () => {
      if (plotRef.current) Plotly.purge(plotRef.current)
    }
  }, [activeMatrix, showStd, truncated])

  return (
    <div>
      <div className="flex justify-end mb-3">
        <button
          onClick={() => setShowStd(!showStd)}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            showStd
              ? 'bg-amber-600/20 text-amber-400'
              : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
          }`}
        >
          {showStd ? 'Disagreement (Std Dev)' : 'Impact Scores'}
        </button>
      </div>
      <div ref={plotRef} className="w-full" />
    </div>
  )
}

/* ── Influence tab sub-component ── */
function InfluenceTab({ matrix, panelMetadata }) {
  const plotRef = useRef(null)

  const nonZero = useMemo(() => {
    if (!matrix) return []
    const vals = []
    for (const row of matrix) {
      for (const v of row) {
        if (v !== 0) vals.push(v)
      }
    }
    return vals
  }, [matrix])

  useEffect(() => {
    if (!plotRef.current || nonZero.length === 0) return

    const trace = {
      x: nonZero,
      type: 'histogram',
      marker: { color: 'rgba(59,130,246,0.6)', line: { color: 'rgba(59,130,246,0.9)', width: 1 } },
      nbinsx: 13,
    }

    const layout = {
      ...DARK_LAYOUT,
      height: 320,
      xaxis: {
        ...DARK_LAYOUT.xaxis,
        title: { text: 'Impact Score', font: { size: 12, color: '#71717a' } },
        dtick: 1,
      },
      yaxis: {
        ...DARK_LAYOUT.yaxis,
        title: { text: 'Frequency', font: { size: 12, color: '#71717a' } },
      },
      margin: { t: 20, r: 20, b: 50, l: 50 },
    }

    Plotly.react(plotRef.current, [trace], layout, PLOTLY_CONFIG)

    return () => {
      if (plotRef.current) Plotly.purge(plotRef.current)
    }
  }, [nonZero])

  return (
    <div className="space-y-6">
      <div ref={plotRef} className="w-full" />
      {panelMetadata && (
        <Card>
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
            Panel Metadata
          </h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-xs text-zinc-500 mb-1">Panel Mode</p>
              <p className="text-sm font-medium text-white capitalize">{(panelMetadata.panel_mode || 'N/A').replace(/_/g, ' ')}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-1">Personas</p>
              <p className="text-sm font-medium text-white">{panelMetadata.n_personas ?? 'N/A'}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-1">Pairs Evaluated</p>
              <p className="text-sm font-medium text-white">{panelMetadata.total_pairs ?? 'N/A'}</p>
            </div>
          </div>
        </Card>
      )}
    </div>
  )
}

/* ── Main page ── */
export default function CIBPage() {
  const { data, loading, error } = useKbApi('/api/cib')
  const [tab, setTab] = useState('network')

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !data || data.unavailable || !data.matrix) {
    return <LoadError title="Cross-Impact Balance Analysis" />
  }

  const panelMeta = {
    panel_mode: data.panel_metadata?.panel_mode || data.panel_metadata?.mode || data.panel_mode,
    n_personas: data.panel_metadata?.n_personas ?? data.panel_metadata?.personas?.length ?? data.n_personas,
    total_pairs: data.panel_metadata?.total_pairs ?? (Array.isArray(data.entries) ? data.entries.length : data.entries),
  }

  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
      className="max-w-7xl mx-auto px-8 py-8"
    >
      {/* Header + tabs */}
      <motion.div variants={fadeUp} className="mb-6">
        <h1 className="text-2xl font-bold text-white mb-4">Cross-Impact Balance Analysis</h1>
        <div className="flex gap-1.5 bg-zinc-900/60 rounded-lg p-1 w-fit">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-1.5 rounded-md text-xs font-medium transition-colors ${
                tab === t.key
                  ? 'bg-zinc-800 text-white shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Tab content */}
      <motion.div variants={fadeIn}>
        {tab === 'network' && (
          <div className="space-y-8">
            <ForceNetwork
              matrix={data.matrix}
              driverNames={data.driver_names}
              driverIds={data.driver_ids}
              influence={data.influence}
              dependence={data.dependence}
            />
            <div>
              <h3 className="text-sm font-semibold text-zinc-400 mb-3">
                Influence vs Dependence Quadrant Map
              </h3>
              <QuadrantScatter
                driverIds={data.driver_ids}
                driverNames={data.driver_names}
                influence={data.influence}
                dependence={data.dependence}
              />
            </div>
          </div>
        )}

        {tab === 'heatmap' && (
          <HeatmapTab
            matrix={data.matrix}
            stdMatrix={data.std_matrix}
            driverNames={data.driver_names}
          />
        )}

        {tab === 'influence' && (
          <InfluenceTab
            matrix={data.matrix}
            panelMetadata={panelMeta}
          />
        )}
      </motion.div>
    </motion.div>
  )
}
