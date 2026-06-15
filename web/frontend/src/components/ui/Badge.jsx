import { SCENARIO_TYPE_COLORS, ORIGIN_COLORS, CONFIDENCE_COLORS } from '@/utils/colors'

export function TypeBadge({ type }) {
  const colors = SCENARIO_TYPE_COLORS[type] || SCENARIO_TYPE_COLORS.evolutionary
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium"
      style={{ backgroundColor: colors.bg, color: colors.text }}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: colors.dot }} />
      {type}
    </span>
  )
}

export function OriginBadge({ origin }) {
  const colors = ORIGIN_COLORS[origin] || ORIGIN_COLORS.bom
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
      style={{ backgroundColor: colors.bg, color: colors.text }}
    >
      {origin === 'both' ? 'BOM+Trend' : origin.toUpperCase()}
    </span>
  )
}

export function ConfidenceBadge({ level }) {
  const colors = CONFIDENCE_COLORS[level] || CONFIDENCE_COLORS.medium
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
      style={{ backgroundColor: colors.bg, color: colors.text }}
    >
      {level}
    </span>
  )
}
