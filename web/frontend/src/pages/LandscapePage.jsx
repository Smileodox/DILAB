import { useState, useRef, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Map, Crosshair, Layers, Star, Activity, TrendingUp } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import { useKb } from '@/context/KbContext'
import MetricCard from '@/components/ui/MetricCard'
import Card from '@/components/ui/Card'
import { TypeBadge } from '@/components/ui/Badge'
import UMAPScatter from '@/components/viz/UMAPScatter'
import DriverRecipeHeatmap from '@/components/viz/DriverRecipeHeatmap'
import SimilarityHeatmap from '@/components/viz/SimilarityHeatmap'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

const METHOD_LABELS = { cib: 'CIB Fixed-Point', combi: 'Combinatorial', zwicky: 'Functional · CCA' }

// Fractional metric tile (PC1 share, silhouette, effective dim). MetricCard animates an
// integer count-up, which mangles fractional values — this just shows the value + a sub.
function StructStat({ label, value, sub, icon: Icon, warn }) {
  return (
    <div className="glass rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">{label}</p>
          <p className={`text-3xl font-extrabold tracking-tight ${warn ? 'text-amber-300' : 'text-white'}`}>
            {value ?? '—'}
          </p>
          {sub && <p className="text-xs text-zinc-500 mt-1">{sub}</p>}
        </div>
        {Icon && (
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <Icon size={20} className="text-blue-400" />
          </div>
        )}
      </div>
    </div>
  )
}

export default function LandscapePage() {
  const { kb, kbs } = useKb()  // KB is the global selection (TopBar); method stays local
  const [method, setMethod] = useState('cib')
  const [colorMode, setColorMode] = useState('archetype')  // colour scatter by cluster or type
  const [selectedPointId, setSelectedPointId] = useState(null)
  const detailRef = useRef(null)

  // Method options are data-driven: a KB only offers methods it has outputs for.
  const currentKb = kbs.find((k) => k.id === kb)
  const methods = currentKb?.methods || ['cib']
  const activeMethod = methods.includes(method) ? method : methods[0]
  const isSampled = activeMethod !== 'cib'

  const q = `kb=${kb}&method=${activeMethod}`
  const { data: landscape, loading: lLoading } = useApi(`/api/landscape?${q}`)
  const { data: scenarios, loading: sLoading } = useApi(`/api/scenarios?${q}`)

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
  const showHeatmap = !isSampled && (landscape.similarity_matrix?.length ?? 0) > 0
  const selectedPoint = landscape.points?.find((p) => p.scenario_id === selectedPointId) || null

  // Cluster colouring: the combinatorial landscape points carry an `archetype` label.
  const hasArchetypes = (landscape.points || []).some((p) => p.archetype)
  const colorBy = hasArchetypes ? colorMode : 'type'

  // Interpretable PCA projection (sampled methods): axis labels + honest structure verdict.
  const axes = landscape.axes
  const structure = landscape.structure
  const axisTitles = axes ? [axes.pc1?.label, axes.pc2?.label] : undefined
  const hasParcoords = (landscape.parcoords?.rows?.length ?? 0) > 0
  const pct = (v) => (v == null ? '—' : `${(v * 100).toFixed(0)}%`)

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
      {/* Header + KB selector + data-driven method toggle */}
      <motion.div variants={fadeUp} className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-bold text-white">Scenario Landscape</h1>
        <div className="flex flex-wrap items-center gap-3">
          {/* Method toggle — only methods this KB has outputs for */}
          <div className="flex gap-2">
            {methods.map((m) => (
              <button
                key={m}
                onClick={() => { setMethod(m); setSelectedPointId(null) }}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                  activeMethod === m
                    ? 'bg-blue-600 text-white'
                    : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {METHOD_LABELS[m] || m}
              </button>
            ))}
          </div>
          {/* Colour the scatter by named cluster (archetype) or by scenario type. */}
          {hasArchetypes && (
            <div className="flex gap-2">
              {[['archetype', 'Clusters'], ['type', 'Type']].map(([mode, label]) => (
                <button
                  key={mode}
                  onClick={() => setColorMode(mode)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                    colorMode === mode
                      ? 'bg-emerald-600 text-white'
                      : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      </motion.div>

      {/* Stats — for sampled methods we show the honest geometry (PC1 / spread /
          separability vs. a uniform-random null), not a cluster count that implies
          structure the null test rejects. */}
      <motion.div variants={staggerContainer} className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard label="Scenarios" value={nScenarios} icon={Map} />
        {isSampled && structure ? (
          <>
            <StructStat label="Dominant axis (PC1)" value={pct(structure.pc1_share)}
              sub={`null ${pct(structure.null?.pc1_mean)}`} icon={TrendingUp} />
            <StructStat label="Effective dimensions" value={structure.effective_dim}
              sub="higher = more isotropic" icon={Layers} />
            <StructStat label="Silhouette vs. null" value={structure.best_silhouette}
              sub={`null ${structure.null?.silhouette_mean}`} icon={Activity}
              warn={!structure.has_usable_clusters} />
          </>
        ) : isSampled ? (
          <>
            <MetricCard label="Clusters" value={nClusters} icon={Layers} />
            <MetricCard label="Representatives" value={nRepresentatives} icon={Star} />
          </>
        ) : (
          <MetricCard label="Fixed Points" value={nFixedPoints} icon={Crosshair} />
        )}
      </motion.div>


      {/* Multi-method structure — several geometric lenses side by side. KMeans forces every
          point into a cluster (all-points silhouette); HDBSCAN permits a continuum halo and
          reports the silhouette of the dense subset only; ordinal keeps the manifestation
          ordering. Shows the archetypal core IS clusterable even when the default is near-zero. */}
      {isSampled && structure?.lenses && (
        <motion.div variants={fadeIn}>
          <h2 className="text-lg font-semibold text-white mb-1">Structure — method comparison</h2>
          <p className="text-sm text-zinc-500 mb-3">
            HDBSCAN silhouettes are on the dense subset only (see continuum %), NOT comparable to the
            all-points KMeans value. “Usable” floor = {structure.floor ?? 0.25}.
          </p>
          <div className="glass rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-zinc-500 uppercase tracking-wider border-b border-white/[0.06]">
                  <th className="text-left px-4 py-2 font-medium">Encoding · method</th>
                  <th className="text-right px-4 py-2 font-medium">Silhouette</th>
                  <th className="text-right px-4 py-2 font-medium">Clusters</th>
                  <th className="text-right px-4 py-2 font-medium">Continuum</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(structure.lenses).map(([name, l]) => {
                  const usable = l.silhouette != null && l.silhouette >= (structure.floor ?? 0.25)
                  return (
                    <tr key={name} className="border-b border-white/[0.03]">
                      <td className="px-4 py-2 text-zinc-300">{l.encoding} · {l.method}</td>
                      <td className={`px-4 py-2 text-right font-semibold ${usable ? 'text-emerald-300' : 'text-zinc-400'}`}>
                        {l.silhouette ?? '—'}
                      </td>
                      <td className="px-4 py-2 text-right text-zinc-400">{l.n_clusters}</td>
                      <td className="px-4 py-2 text-right text-zinc-400">
                        {l.noise_fraction ? `${(l.noise_fraction * 100).toFixed(0)}%` : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}

      {/* Hint when the selected KB/method has no generated outputs */}
      {isSampled && (landscape.points?.length ?? 0) === 0 && (
        <motion.p variants={fadeIn} className="text-sm text-zinc-400">
          No scenarios for this knowledge base / method yet.
        </motion.p>
      )}

      {/* Scatter — PCA config-space axes (sampled) or legacy UMAP (CIB) */}
      <motion.div variants={fadeIn}>
        {isSampled && (colorBy === 'archetype' ? (
          <h2 className="text-lg font-semibold text-white mb-1">
            Scenario clusters — named archetypes + continuum
          </h2>
        ) : axes && (
          <h2 className="text-lg font-semibold text-white mb-1">Config space (PCA)</h2>
        ))}
        <UMAPScatter
          points={landscape.points}
          onPointClick={handlePointClick}
          axisTitles={axisTitles}
          colorBy={colorBy}
        />
      </motion.div>

      {/* Driver recipe — scenarios sorted by PC1 (rows) × drivers (columns),
          cell colour = the chosen manifestation, optimistic → pessimistic. */}
      {isSampled && hasParcoords && (
        <motion.div variants={fadeIn}>
          <h2 className="text-lg font-semibold text-white mb-1">Driver recipe</h2>
          <p className="text-sm text-zinc-500 mb-3">
            Rows = scenarios sorted by PC1, columns = drivers, colour = the chosen
            manifestation (optimistic → pessimistic). The continuum shows as colour bands.
          </p>
          <DriverRecipeHeatmap parcoords={landscape.parcoords} />
        </motion.div>
      )}

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
