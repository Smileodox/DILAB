import { motion } from 'framer-motion'
import { X } from 'lucide-react'
import { TypeBadge } from '@/components/ui/Badge'
import { SCENARIO_TYPE_COLORS } from '@/utils/colors'

// The generator leaves raw chunk-id citations in the prose — both "(abc…, def…)" lists and
// "[abc…][def…]" chains. Strip them for display; the evidence panel is the real source view.
function stripChunkIds(text) {
  return (text || '')
    .replace(/\s*\((?:[0-9a-f]{12}(?:,\s*)?)+\)/g, '')
    .replace(/(?:\[[0-9a-f]{12}\])+/g, '')
}

// Render "[Extrapolation]" markers as a small amber badge instead of raw brackets.
function NarrativeParagraph({ text }) {
  const parts = text.split('[Extrapolation]')
  return (
    <p className="text-[15px] leading-relaxed text-zinc-300 mb-5 last:mb-0">
      {parts.map((part, i) => (
        <span key={i}>
          {part}
          {i < parts.length - 1 && (
            <span className="inline-block align-middle mx-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/15 text-amber-400 border border-amber-500/25">
              Extrapolation
            </span>
          )}
        </span>
      ))}
    </p>
  )
}

export default function NarrativeView({ scenario, onClose }) {
  if (!scenario) return null

  const colors = SCENARIO_TYPE_COLORS[scenario.type] || SCENARIO_TYPE_COLORS.evolutionary
  const paragraphs = stripChunkIds(scenario.narrative).split('\n\n').filter(Boolean)

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
            <NarrativeParagraph key={i} text={para} />
          ))}
        </div>
      </div>
    </motion.div>
  )
}
