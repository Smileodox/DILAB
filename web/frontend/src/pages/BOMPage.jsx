import { motion } from 'framer-motion'
import { Boxes, GitBranch } from 'lucide-react'
import { useKbApi } from '@/context/KbContext'
import MetricCard from '@/components/ui/MetricCard'
import LoadError from '@/components/ui/LoadError'
import BOMTree from '@/components/viz/BOMTree'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

export default function BOMPage() {
  const { data, loading, error } = useKbApi('/api/bom')

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !data || data.unavailable || !data.tree) {
    return <LoadError title="Bill of Materials — Product Architecture" />
  }

  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
      className="max-w-5xl mx-auto px-8 py-8"
    >
      {/* Header */}
      <motion.h1 variants={fadeUp} className="text-2xl font-bold text-white mb-6">
        Bill of Materials — Product Architecture
      </motion.h1>

      {/* Stats */}
      <motion.div variants={staggerContainer} className="grid grid-cols-2 gap-4 mb-8">
        <MetricCard label="Total Nodes" value={data.total_nodes} icon={Boxes} />
        <MetricCard label="BOM Driver Candidates" value={data.total_drivers} icon={GitBranch}
          sub="pre-merge" />
      </motion.div>

      {/* Tree */}
      <motion.div variants={fadeIn}>
        <div className="flex items-center gap-2 text-xs text-zinc-400 mb-2">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          technology-driver candidate ({data.total_drivers} of {data.total_nodes} components)
        </div>
        <BOMTree tree={data.tree} />
      </motion.div>
    </motion.div>
  )
}
