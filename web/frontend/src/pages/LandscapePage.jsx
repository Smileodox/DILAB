import { useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Map, Crosshair, Layers, Star } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import MetricCard from '@/components/ui/MetricCard'
import Card from '@/components/ui/Card'
import { TypeBadge } from '@/components/ui/Badge'
import UMAPScatter from '@/components/viz/UMAPScatter'
import SimilarityHeatmap from '@/components/viz/SimilarityHeatmap'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

export default function LandscapePage() {
  const [method, setMethod] = useState('morphological')
  const isCombi = method === 'combinatorial'
  const { data: landscape, loading: lLoading } = useApi(isCombi ? '/api/landscape_combi' : '/api/landscape')
  const { data: scenarios, loading: sLoading } = useApi(isCombi ? '/api/scenarios_combi' : '/api/scenarios')
  const [selectedPointId, setSelectedPointId] = useState(null)
  const detailRef = useRef(null)

  const loading = lLoading || sLoading

  const handlePointClick = useCallback((scenarioId) => {
    setSelectedPointId(scenarioId)
    setTimeout(() => {
      detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, 100)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const selectedScenario = scenarios?.find((s) => s.id === selectedPointId) || null

  const nScenarios = landscape.metadata?.n_scenarios ?? landscape.points?.length ?? 0
  const nFixedPoints = landscape.metadata?.n_fixed_points ??
    landscape.points?.filter((p) => p.is_fixed_point).length ?? 0
  const nClusters = landscape.metadata?.n_clusters ?? 0
  const nRepresentatives = landscape.points?.filter((p) => p.is_representative).length ?? 0
  const showHeatmap = !isCombi && (landscape.similarity_matrix?.length ?? 0) > 0
  const selectedPoint = landscape.points?.find((p) => p.scenario_id === selectedPointId) || null

  // Build scenario titles list for heatmap, matching scenario_ids order
  const scenarioTitles = (landscape.scenario_ids || []).map((id) => {
    const s = scenarios?.find((sc) => sc.id === id)
    return s ? s.title : id
  })

  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
      className="max-w-7xl mx-auto px-8 py-8 space-y-8"
    >
      {/* Header + method toggle (A/B: CIB fixed-point vs combinatorial) */}
      <motion.div variants={fadeUp} className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-white">Scenario Landscape</h1>
        <div className="flex gap-2">
          {[
            ['morphological', 'CIB Fixed-Point'],
            ['combinatorial', 'Combinatorial + Clusters'],
          ].map(([m, label]) => (
            <button
              key={m}
              onClick={() => { setMethod(m); setSelectedPointId(null) }}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                method === m
                  ? 'bg-blue-600 text-white'
                  : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Stats */}
      <motion.div variants={staggerContainer} className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard label="Scenarios" value={nScenarios} icon={Map} />
        {isCombi ? (
          <>
            <MetricCard label="Clusters" value={nClusters} icon={Layers} />
            <MetricCard label="Representatives" value={nRepresentatives} icon={Star} />
          </>
        ) : (
          <MetricCard label="Fixed Points" value={nFixedPoints} icon={Crosshair} />
        )}
      </motion.div>

      {/* Hint when combinatorial outputs not generated yet */}
      {isCombi && (landscape.points?.length ?? 0) === 0 && (
        <motion.p variants={fadeIn} className="text-sm text-zinc-400">
          No combinatorial scenarios yet — run{' '}
          <code className="text-zinc-300">uv run python run_combinatorial.py</code> to generate them.
        </motion.p>
      )}

      {/* UMAP scatter */}
      <motion.div variants={fadeIn}>
        <UMAPScatter
          points={landscape.points}
          onPointClick={handlePointClick}
        />
      </motion.div>

      {/* Selected scenario detail */}
      {selectedScenario && (
        <motion.div
          ref={detailRef}
          variants={fadeUp}
          initial="enter"
          animate="center"
        >
          <Card glow="blue">
            <div className="flex items-start justify-between gap-4 mb-3">
              <h3 className="text-lg font-semibold text-white">{selectedScenario.title}</h3>
              <TypeBadge type={selectedScenario.type} />
            </div>
            {selectedScenario.perspective && (
              <p className="text-sm text-zinc-400 italic mb-3">{selectedScenario.perspective}</p>
            )}
            <p className="text-sm text-zinc-300 line-clamp-4">
              {selectedScenario.narrative}
            </p>
            <div className="flex items-center gap-4 mt-4 text-xs text-zinc-500">
              {selectedScenario.rank > 0 && <span>Rank #{selectedScenario.rank}</span>}
              {selectedScenario.topsis_closeness > 0 && (
                <span>TOPSIS {(selectedScenario.topsis_closeness * 100).toFixed(0)}%</span>
              )}
              <span>Coverage {(selectedScenario.coverage_ratio * 100).toFixed(0)}%</span>
              {selectedPoint?.cluster >= 0 && <span>Cluster {selectedPoint.cluster}</span>}
              {selectedPoint?.is_representative && (
                <span className="text-amber-400">★ Representative</span>
              )}
            </div>
          </Card>
        </motion.div>
      )}

      {/* Similarity heatmap (only meaningful for the small fixed-point set) */}
      {showHeatmap && (
        <motion.div variants={fadeIn}>
          <h2 className="text-lg font-semibold text-white mb-4">Pairwise Similarity</h2>
          <SimilarityHeatmap
            matrix={landscape.similarity_matrix}
            scenarioIds={landscape.scenario_ids}
            scenarioTitles={scenarioTitles}
          />
        </motion.div>
      )}
    </motion.div>
  )
}
