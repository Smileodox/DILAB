import { useState } from 'react'
import { motion } from 'framer-motion'
import { SCENARIO_TYPE_COLORS } from '@/utils/colors'
import { staggerContainer, fadeUp } from '@/utils/animation'

const FILTERS = ['all', 'disruptive', 'cautionary', 'wildcard', 'evolutionary']

export default function ScenarioList({ scenarios, selectedId, onSelect }) {
  const [filter, setFilter] = useState('all')

  const filtered =
    filter === 'all'
      ? scenarios
      : scenarios.filter(s => s.type === filter)

  return (
    <div className="flex flex-col h-full">
      {/* Filter pills */}
      <div className="flex flex-wrap gap-1.5 p-3 border-b border-white/5">
        {FILTERS.map(f => {
          const active = filter === f
          const colors = f !== 'all' ? SCENARIO_TYPE_COLORS[f] : null
          return (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                active
                  ? 'text-white'
                  : 'text-zinc-500 hover:text-zinc-300'
              }`}
              style={
                active
                  ? {
                      backgroundColor: colors ? colors.bg : 'rgba(255,255,255,0.1)',
                      color: colors ? colors.text : '#fff',
                    }
                  : undefined
              }
            >
              {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          )
        })}
      </div>

      {/* Scenario list */}
      <motion.div
        className="flex-1 overflow-y-auto p-2 space-y-1"
        variants={staggerContainer}
        initial="enter"
        animate="center"
      >
        {filtered.map(s => {
          const selected = s.id === selectedId
          const colors = SCENARIO_TYPE_COLORS[s.type] || SCENARIO_TYPE_COLORS.evolutionary
          return (
            <motion.div
              key={s.id}
              variants={fadeUp}
              whileHover={{ scale: 1.01 }}
              onClick={() => onSelect(s.id)}
              className={`
                flex items-center gap-3 p-3 rounded-lg cursor-pointer
                transition-colors
                glass glass-hover
                ${selected ? 'border-l-[3px]' : 'border-l-[3px] border-transparent'}
              `}
              style={
                selected
                  ? {
                      borderLeftColor: '#3b82f6',
                      boxShadow: '0 0 12px rgba(59,130,246,0.25)',
                    }
                  : undefined
              }
            >
              {/* Rank */}
              <span className="text-lg font-bold text-zinc-400 w-7 text-center shrink-0">
                {s.rank}
              </span>

              {/* Title + meta */}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-zinc-200 font-medium line-clamp-2 leading-snug">
                  {s.title}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: colors.dot }}
                  />
                  <span className="text-[11px] text-zinc-500 capitalize">
                    {s.type}
                  </span>
                </div>
              </div>

              {/* TOPSIS score */}
              <span className="text-xs font-mono text-zinc-400 shrink-0">
                {(s.topsis_closeness * 100).toFixed(0)}%
              </span>
            </motion.div>
          )
        })}
      </motion.div>
    </div>
  )
}
