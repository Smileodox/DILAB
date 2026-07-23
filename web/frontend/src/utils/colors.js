export const SCENARIO_TYPE_COLORS = {
  evolutionary: { bg: '#1e3a5f', text: '#60a5fa', border: '#3b82f6', dot: '#3b82f6' },
  disruptive: { bg: '#064e3b', text: '#34d399', border: '#10b981', dot: '#10b981' },
  cautionary: { bg: '#78350f', text: '#fbbf24', border: '#f59e0b', dot: '#f59e0b' },
  wildcard: { bg: '#4c1d95', text: '#a78bfa', border: '#8b5cf6', dot: '#8b5cf6' },
}

export const ORIGIN_COLORS = {
  both: { bg: '#164e63', text: '#22d3ee', border: '#06b6d4' },
  bom: { bg: '#0c4a6e', text: '#38bdf8', border: '#0ea5e9' },
  trend: { bg: '#4c1d95', text: '#a78bfa', border: '#8b5cf6' },
}

// Driving-dimension buckets of the trend extraction (kept apart from ORIGIN_COLORS:
// sky/violet already mean bom/trend there, so the four buckets get their own hues).
export const DIMENSION_COLORS = {
  regulatory: { bg: '#78350f', text: '#fbbf24', border: '#f59e0b' },
  market: { bg: '#064e3b', text: '#34d399', border: '#10b981' },
  geopolitical: { bg: '#881337', text: '#fb7185', border: '#f43f5e' },
  technological: { bg: '#1e3a5f', text: '#60a5fa', border: '#3b82f6' },
}

export const CONFIDENCE_COLORS = {
  high: { bg: '#064e3b', text: '#34d399' },
  medium: { bg: '#78350f', text: '#fbbf24' },
  low: { bg: '#4c1d95', text: '#a78bfa' },
}

export const PLAUSIBILITY_COLORS = {
  high: '#10b981',
  medium: '#f59e0b',
  low: '#ef4444',
}

// Deliberately NOT red/green: those are reserved for edge polarity (promoting/inhibiting)
// in the CIB networks, so quadrant roles get their own hue family.
export const CIB_QUADRANT_COLORS = {
  critical: '#a855f7',
  enabler: '#38bdf8',
  dependent: '#f59e0b',
  isolated: '#71717a',
}

export const PIPELINE_COLORS = {
  input: '#3b82f6',
  analysis: '#8b5cf6',
  output: '#10b981',
}

// One shared palette for named archetype clusters — scatter, cards, and heatmaps must
// agree on which color means which archetype. Index = position in the sorted label list.
export const ARCHETYPE_PALETTE = ['#5B8FF9', '#61DDAA', '#F6BD16', '#F08BB4', '#7262FD',
                                  '#78D3F8', '#F6903D', '#008685', '#D95040', '#9FB40F']
export const CONTINUUM_COLOR = '#6b7280'

export function archetypeColor(label, allLabels) {
  if (!label || label === 'Continuum') return CONTINUUM_COLOR
  const named = [...new Set(allLabels)].filter((l) => l && l !== 'Continuum').sort()
  const idx = named.indexOf(label)
  return idx === -1 ? CONTINUUM_COLOR : ARCHETYPE_PALETTE[idx % ARCHETYPE_PALETTE.length]
}
