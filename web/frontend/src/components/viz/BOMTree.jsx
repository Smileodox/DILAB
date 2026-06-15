import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight, ChevronDown } from 'lucide-react'

function TreeNode({ node, level = 0, defaultExpanded }) {
  const hasChildren = node.children && node.children.length > 0
  const [expanded, setExpanded] = useState(
    defaultExpanded != null ? defaultExpanded : level <= 1,
  )
  const [showTooltip, setShowTooltip] = useState(false)

  const toggle = useCallback(() => {
    if (hasChildren) setExpanded((e) => !e)
  }, [hasChildren])

  return (
    <div className="relative">
      {/* Vertical indent guide lines */}
      {level > 0 && (
        <div
          className="absolute top-0 bottom-0"
          style={{
            left: level * 24 - 12,
            width: 1,
            background: 'rgba(161,161,170,0.1)',
          }}
        />
      )}

      {/* Node row */}
      <div
        className="group relative flex items-center gap-2 py-1.5 px-2 rounded-md transition-colors duration-150 hover:bg-white/[0.03] cursor-default"
        style={{ paddingLeft: level * 24 + 8 }}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onClick={toggle}
      >
        {/* Expand / collapse toggle */}
        <div className="w-4 h-4 flex items-center justify-center shrink-0">
          {hasChildren ? (
            <button
              className="text-zinc-500 hover:text-zinc-300 transition-colors"
              aria-label={expanded ? 'Collapse' : 'Expand'}
            >
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
          ) : (
            <span className="block w-1 h-1 rounded-full bg-zinc-700" />
          )}
        </div>

        {/* Driver indicator dot */}
        {node.is_driver && (
          <span className="pulse-dot w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
        )}

        {/* Node name */}
        <span
          className={`text-sm leading-tight truncate ${
            node.is_driver
              ? 'text-emerald-400 font-semibold'
              : level === 0
                ? 'text-zinc-100 font-semibold'
                : 'text-zinc-300'
          }`}
        >
          {node.name}
        </span>

        {/* Level indicator */}
        <span className="text-[10px] text-zinc-600 ml-auto shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
          L{node.level}
        </span>

        {/* Tooltip */}
        {showTooltip && node.description && (
          <div
            className="absolute left-full top-0 ml-2 z-50 glass rounded-md px-3 py-2 text-xs text-zinc-300 max-w-xs leading-relaxed pointer-events-none"
            style={{ minWidth: 160 }}
          >
            {node.description.length > 200
              ? node.description.slice(0, 200) + '...'
              : node.description}
          </div>
        )}
      </div>

      {/* Children with animation */}
      <AnimatePresence initial={false}>
        {expanded && hasChildren && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            {node.children.map((child) => (
              <TreeNode key={child.id} node={child} level={level + 1} />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default function BOMTree({ tree }) {
  if (!tree) {
    return (
      <div className="flex items-center justify-center h-40 text-zinc-500 text-sm">
        No BOM tree data available
      </div>
    )
  }

  return (
    <div className="glass rounded-xl p-4 overflow-y-auto max-h-[600px]">
      <TreeNode node={tree} level={0} defaultExpanded />
    </div>
  )
}
