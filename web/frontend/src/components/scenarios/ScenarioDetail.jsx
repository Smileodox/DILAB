import { motion } from 'framer-motion'
import { BookOpen, FileSearch } from 'lucide-react'
import { TypeBadge } from '@/components/ui/Badge'
import RadarChart from '@/components/ui/RadarChart'
import ScoreBar from '@/components/ui/ScoreBar'
import { SCENARIO_TYPE_COLORS } from '@/utils/colors'
import { fadeUp, staggerContainer } from '@/utils/animation'

const CRITERIA = [
  { key: 'impact', label: 'Impact' },
  { key: 'probability', label: 'Probability' },
  { key: 'actionability', label: 'Actionability' },
  { key: 'time_horizon', label: 'Time Horizon' },
  { key: 'risk_severity', label: 'Risk Severity' },
]

function parseAssumption(assumption) {
  const desc = assumption.description || ''
  const colonIdx = desc.indexOf(':')
  if (colonIdx === -1) return { driver: desc, state: '', detail: '' }
  const driver = desc.slice(0, colonIdx).trim()
  const rest = desc.slice(colonIdx + 1).trim()
  const dashIdx = rest.indexOf('—')
  if (dashIdx === -1) return { driver, state: rest, detail: '' }
  return {
    driver,
    state: rest.slice(0, dashIdx).trim(),
    detail: rest.slice(dashIdx + 1).trim(),
  }
}

export default function ScenarioDetail({ scenario, onShowNarrative, onShowEvidence }) {
  if (!scenario) return null

  const colors = SCENARIO_TYPE_COLORS[scenario.type] || SCENARIO_TYPE_COLORS.evolutionary

  return (
    <motion.div
      className="space-y-6"
      variants={staggerContainer}
      initial="enter"
      animate="center"
    >
      {/* Header */}
      <motion.div variants={fadeUp}>
        <h2 className="text-2xl font-bold text-white leading-tight mb-3">
          {scenario.title}
        </h2>
        <div className="flex items-center gap-3 flex-wrap">
          <TypeBadge type={scenario.type} />
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-zinc-800 text-zinc-300">
            Rank #{scenario.rank}
          </span>
          <span className="text-sm font-mono text-zinc-400">
            TOPSIS {(scenario.topsis_closeness * 100).toFixed(0)}%
          </span>
        </div>
      </motion.div>

      {/* Perspective */}
      {scenario.perspective && (
        <motion.blockquote
          variants={fadeUp}
          className="pl-4 py-1 text-zinc-400 italic text-sm leading-relaxed"
          style={{ borderLeft: `2px solid ${colors.border}` }}
        >
          {scenario.perspective}
        </motion.blockquote>
      )}

      {/* Key tensions */}
      {scenario.key_tensions?.length > 0 && (
        <motion.div variants={fadeUp}>
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
            Key Tensions
          </h3>
          <ul className="space-y-1.5">
            {scenario.key_tensions.map((tension, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
                <span
                  className="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0"
                  style={{ backgroundColor: colors.dot }}
                />
                {tension}
              </li>
            ))}
          </ul>
        </motion.div>
      )}

      {/* Radar chart */}
      {scenario.assessment && (
        <motion.div variants={fadeUp}>
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
            Assessment
          </h3>
          <RadarChart assessment={scenario.assessment} color={colors.dot} />
          <div className="space-y-2 mt-4">
            {CRITERIA.map(c => (
              <ScoreBar
                key={c.key}
                label={c.label}
                value={scenario.assessment[c.key] || 0}
                color={colors.dot}
              />
            ))}
          </div>
        </motion.div>
      )}

      {/* Assumption strip */}
      {scenario.assumptions?.length > 0 && (
        <motion.div variants={fadeUp}>
          <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-2">
            Driver Assumptions
          </h3>
          <div className="flex gap-2 overflow-x-auto pb-2 -mx-1 px-1">
            {scenario.assumptions.map((a, i) => {
              const parsed = parseAssumption(a)
              return (
                <div
                  key={i}
                  className="shrink-0 glass rounded-lg p-2.5 min-w-[140px] max-w-[180px]"
                >
                  <p className="text-xs text-zinc-400 truncate" title={parsed.driver}>
                    {parsed.driver}
                  </p>
                  <span
                    className="inline-block mt-1 px-2 py-0.5 rounded text-[11px] font-medium"
                    style={{ backgroundColor: colors.bg, color: colors.text }}
                  >
                    {parsed.state}
                  </span>
                </div>
              )
            })}
          </div>
        </motion.div>
      )}

      {/* Action buttons */}
      <motion.div variants={fadeUp} className="flex gap-3 pt-2">
        <button
          onClick={onShowNarrative}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 transition-colors"
        >
          <BookOpen size={16} />
          Read Narrative
        </button>
        <button
          onClick={onShowEvidence}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-zinc-300 border border-zinc-700 hover:border-zinc-500 hover:text-white transition-colors"
        >
          <FileSearch size={16} />
          View Evidence
        </button>
      </motion.div>
    </motion.div>
  )
}
