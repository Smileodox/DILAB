import { motion } from 'framer-motion'
import { useKbApi } from '@/context/KbContext'
import MorphGrid from '@/components/viz/MorphGrid'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

export default function MorphBoxPage() {
  const { data: morphData, loading: morphLoading } = useKbApi('/api/morphbox')
  const { data: scenarios, loading: scenariosLoading } = useKbApi('/api/scenarios')

  const loading = morphLoading || scenariosLoading

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
      className="max-w-7xl mx-auto px-8 py-8"
    >
      {/* Header */}
      <motion.div variants={fadeUp} className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <h1 className="text-2xl font-bold text-white">Morphological Box</h1>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-300">
            {morphData.total_manifestations} manifestations
          </span>
        </div>
        <p className="text-sm text-zinc-400 max-w-2xl leading-relaxed">
          The morphological box (Zwicky box) decomposes each technology driver into discrete
          manifestations representing plausible future states. Scenarios are constructed by
          selecting one manifestation per driver, forming internally consistent configurations.
        </p>
      </motion.div>

      {/* Grid */}
      <motion.div variants={fadeIn}>
        <MorphGrid drivers={morphData.drivers} scenarios={scenarios || []} />
      </motion.div>
    </motion.div>
  )
}
