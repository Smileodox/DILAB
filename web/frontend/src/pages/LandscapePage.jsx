import { useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Map, Crosshair } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import MetricCard from '@/components/ui/MetricCard'
import Card from '@/components/ui/Card'
import { TypeBadge } from '@/components/ui/Badge'
import UMAPScatter from '@/components/viz/UMAPScatter'
import SimilarityHeatmap from '@/components/viz/SimilarityHeatmap'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

export default function LandscapePage() {
  const { data: landscape, loading: lLoading } = useApi('/api/landscape')
  const { data: scenarios, loading: sLoading } = useApi('/api/scenarios')
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
      {/* Header */}
      <motion.h1 variants={fadeUp} className="text-2xl font-bold text-white">
        Scenario Landscape
      </motion.h1>

      {/* Stats */}
      <motion.div variants={staggerContainer} className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard label="Scenarios" value={nScenarios} icon={Map} />
        <MetricCard label="Fixed Points" value={nFixedPoints} icon={Crosshair} />
      </motion.div>

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
              <span>Rank #{selectedScenario.rank}</span>
              <span>TOPSIS {(selectedScenario.topsis_closeness * 100).toFixed(0)}%</span>
              <span>Coverage {(selectedScenario.coverage_ratio * 100).toFixed(0)}%</span>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Similarity heatmap */}
      <motion.div variants={fadeIn}>
        <h2 className="text-lg font-semibold text-white mb-4">Pairwise Similarity</h2>
        <SimilarityHeatmap
          matrix={landscape.similarity_matrix}
          scenarioIds={landscape.scenario_ids}
          scenarioTitles={scenarioTitles}
        />
      </motion.div>
    </motion.div>
  )
}
