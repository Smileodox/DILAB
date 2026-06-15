import { useState, useMemo } from 'react'
import { motion } from 'framer-motion'
import { useApi } from '@/hooks/useApi'
import ForceNetwork3D from '@/components/viz/ForceNetwork3D'
import ConnectionPanel from '@/components/viz/ConnectionPanel'
import NetworkStats from '@/components/viz/NetworkStats'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

export default function EmbeddingsLabPage() {
  const { data, loading } = useApi('/api/cib/3d')
  const [selectedId, setSelectedId] = useState(null)

  const selectedNode = useMemo(() => {
    if (!selectedId || !data?.nodes) return null
    return data.nodes.find(n => n.id === selectedId) || null
  }, [selectedId, data])

  const handleNodeClick = (id) => {
    setSelectedId(prev => prev === id ? null : id)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!data?.nodes?.length) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)] text-zinc-500 text-sm">
        No CIB data available
      </div>
    )
  }

  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
      className="max-w-7xl mx-auto px-8 py-8 space-y-6"
    >
      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-center gap-3">
        <h1 className="text-2xl font-extrabold text-white">Embeddings Lab</h1>
        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wider bg-violet-500/15 text-violet-400 border border-violet-500/20">
          Experimental
        </span>
      </motion.div>

      <motion.p variants={fadeUp} className="text-sm text-zinc-400 -mt-2">
        3D UMAP projection of the CIB cross-impact network. 14 technology drivers positioned by interaction strength — closer nodes have stronger mutual influence. Edges colored by polarity.
      </motion.p>

      {/* Stats */}
      <motion.div variants={fadeIn}>
        <NetworkStats stats={data.stats} />
      </motion.div>

      {/* Main content */}
      <motion.div variants={fadeIn} className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 3D scatter */}
        <div className={selectedNode ? 'lg:col-span-2' : 'lg:col-span-3'}>
          <ForceNetwork3D
            nodes={data.nodes}
            edges={data.edges}
            selectedId={selectedId}
            onNodeClick={handleNodeClick}
          />
        </div>

        {/* Connection panel */}
        {selectedNode && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          >
            <ConnectionPanel
              node={selectedNode}
              edges={data.edges}
              nodes={data.nodes}
              onSelectNode={handleNodeClick}
            />
          </motion.div>
        )}
      </motion.div>
    </motion.div>
  )
}
