import { motion } from 'framer-motion'
import { useKbApi } from '@/context/KbContext'
import MorphGrid from '@/components/viz/MorphGrid'
import LoadError from '@/components/ui/LoadError'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

export default function MorphBoxPage() {
  const { data: morphData, loading: morphLoading, error: morphError } = useKbApi('/api/morphbox')
  const { data: scenarios, loading: scenariosLoading } = useKbApi('/api/scenarios')

  const loading = morphLoading || scenariosLoading

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (morphError || !morphData || morphData.unavailable) {
    return <LoadError title="Morphological Box" />
  }

  const drivers = morphData.drivers || []
  const scenarioList = Array.isArray(scenarios) ? scenarios : []
  // The full combination space: one manifestation per driver → product over all drivers.
  const combinations = drivers.reduce((p, d) => p * (d.manifestations?.length || 1), 1)

  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
      className="max-w-7xl mx-auto px-8 py-8"
    >
      {/* Header */}
      <motion.div variants={fadeUp} className="mb-6">
        <div className="flex items-center gap-3 mb-2 flex-wrap">
          <h1 className="text-2xl font-bold text-white">Morphological Box</h1>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-300">
            {drivers.length} drivers
          </span>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-300">
            {morphData.total_manifestations} manifestations
          </span>
          {combinations > 1000 && (
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-violet-500/15 text-violet-300 border border-violet-500/25">
              {combinations.toLocaleString()} possible configurations
            </span>
          )}
        </div>
        <p className="text-sm text-zinc-400 max-w-2xl leading-relaxed">
          The morphological box (Zwicky box) decomposes each technology driver into discrete
          manifestations representing plausible future states. Scenarios are constructed by
          selecting one manifestation per driver, forming internally consistent configurations
          {scenarioList.length > 0 && (
            <> — CIB consistency filtering reduces the full space to{' '}
            <span className="text-zinc-200 font-medium">{scenarioList.length} consistent scenarios</span></>
          )}.
        </p>
      </motion.div>

      {/* Grid */}
      <motion.div variants={fadeIn}>
        <MorphGrid drivers={morphData.drivers} scenarios={scenarios || []} />
      </motion.div>
    </motion.div>
  )
}
