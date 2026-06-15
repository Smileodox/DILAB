import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import { TypeBadge } from '@/components/ui/Badge'
import { SCENARIO_TYPE_COLORS } from '@/utils/colors'

export default function NarrativeView({ scenario, onClose }) {
  if (!scenario) return null

  const colors = SCENARIO_TYPE_COLORS[scenario.type] || SCENARIO_TYPE_COLORS.evolutionary
  const paragraphs = (scenario.narrative || '').split('\n\n').filter(Boolean)

  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 30, stiffness: 300 }}
      className="fixed top-0 right-0 h-full w-full max-w-[720px] z-50 bg-zinc-950/95 backdrop-blur-xl border-l border-white/5 shadow-2xl"
    >
      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-2 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-white/5 transition-colors z-10"
      >
        <X size={20} />
      </button>

      {/* Content */}
      <div className="h-full overflow-y-auto p-8 pt-6">
        {/* Header */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-white leading-tight pr-10 mb-3">
            {scenario.title}
          </h2>
          <TypeBadge type={scenario.type} />
        </div>

        {/* Perspective */}
        {scenario.perspective && (
          <blockquote
            className="mb-8 pl-4 py-1 text-zinc-400 italic text-sm leading-relaxed"
            style={{ borderLeft: `2px solid ${colors.border}` }}
          >
            {scenario.perspective}
          </blockquote>
        )}

        {/* Narrative body */}
        <div
          className="pl-4"
          style={{ borderLeft: `2px solid ${colors.border}20` }}
        >
          {paragraphs.map((para, i) => (
            <p
              key={i}
              className="text-[15px] leading-relaxed text-zinc-300 mb-5 last:mb-0"
            >
              {para}
            </p>
          ))}
        </div>
      </div>
    </motion.div>
  )
}
