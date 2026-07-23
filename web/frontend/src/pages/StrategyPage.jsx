import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Target, Shield, AlertTriangle, ChevronDown, Trophy, Crosshair,
  Eye, Zap, Clock, TrendingUp, ArrowRight,
} from 'lucide-react'
import { useKbApi } from '@/context/KbContext'
import Card from '@/components/ui/Card'
import LoadError from '@/components/ui/LoadError'
import { TypeBadge } from '@/components/ui/Badge'
import { SCENARIO_TYPE_COLORS } from '@/utils/colors'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

const RANK_COLORS = [
  'from-amber-400 to-amber-600',
  'from-zinc-300 to-zinc-400',
  'from-amber-700 to-amber-800',
]
const RANK_BORDER = ['border-amber-500/30', 'border-zinc-400/20', 'border-amber-800/20']
const RANK_GLOW = ['shadow-amber-500/10', 'shadow-zinc-400/5', '']

export default function StrategyPage() {
  const { data: framing, loading: fLoading, error: fError } = useKbApi('/api/strategic_framing')
  const { data: scenarios, loading: sLoading, error: sError } = useKbApi('/api/scenarios')
  const [expandedStrategy, setExpandedStrategy] = useState(null)

  const loading = fLoading || sLoading

  const sortedStrategies = useMemo(() => {
    if (!framing?.scenario_strategy) return []
    return [...framing.scenario_strategy].sort((a, b) => a.mcda_rank - b.mcda_rank)
  }, [framing])

  const scenarioMap = useMemo(() => {
    if (!Array.isArray(scenarios)) return {}
    const m = {}
    for (const s of scenarios) m[s.title] = s
    return m
  }, [scenarios])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (fError || sError || !framing || framing.unavailable) {
    return <LoadError title="Strategic Framing" />
  }

  const scenarioList = Array.isArray(scenarios) ? scenarios : []
  const priority = framing?.recommended_priority
  const hasFraming = framing?.critical_uncertainties?.length > 0

  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
      className="max-w-6xl mx-auto px-8 py-8 space-y-10"
    >
      {/* Page title */}
      <motion.div variants={fadeUp} className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-blue-500/20 flex items-center justify-center">
          <Target size={20} className="text-blue-400" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Strategic Framing</h1>
          <p className="text-xs text-zinc-500">Decision framework derived from scenario analysis</p>
        </div>
      </motion.div>

      {/* Hero — Recommended Priority */}
      {priority && (
        <motion.div variants={fadeUp}>
          <div className="relative overflow-hidden rounded-2xl border border-blue-500/20 bg-gradient-to-br from-blue-950/40 via-zinc-900/60 to-violet-950/30 p-6">
            <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4" />
            <div className="relative">
              <div className="flex items-center gap-2 mb-3">
                <Crosshair size={14} className="text-blue-400" />
                <span className="text-[10px] font-semibold uppercase tracking-widest text-blue-400">Recommended Priority Scenario</span>
              </div>
              <h2 className="text-lg font-bold text-white mb-3">{priority.scenario_title}</h2>
              <p className="text-sm text-zinc-400 leading-relaxed mb-5">{priority.rationale}</p>

              {priority.immediate_actions?.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Zap size={14} className="text-amber-400" />
                    <span className="text-[10px] font-semibold uppercase tracking-widest text-amber-400">Immediate Actions</span>
                  </div>
                  <div className="space-y-3">
                    {priority.immediate_actions.map((action, i) => (
                      <div key={i} className="flex gap-3">
                        <div className="flex flex-col items-center">
                          <div className="w-6 h-6 rounded-full bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0">
                            <span className="text-xs font-bold text-amber-400">{i + 1}</span>
                          </div>
                          {i < priority.immediate_actions.length - 1 && (
                            <div className="w-px flex-1 bg-gradient-to-b from-amber-500/20 to-transparent mt-1" />
                          )}
                        </div>
                        <p className="text-sm text-zinc-300 leading-relaxed pb-1">{action}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {hasFraming && (
        <>
          {/* Critical Uncertainties */}
          <motion.div variants={fadeIn}>
            <SectionHeader icon={AlertTriangle} color="amber" title="Critical Uncertainties" subtitle={`${framing.critical_uncertainties.length} key axes`} />
            <div className="grid gap-4 md:grid-cols-3">
              {framing.critical_uncertainties.map((cu, i) => (
                <motion.div key={i} variants={fadeUp}>
                  <Card className="h-full">
                    <div className="flex items-start gap-2 mb-2">
                      <div className="w-7 h-7 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0">
                        <span className="text-xs font-bold text-amber-400">{i + 1}</span>
                      </div>
                      <h3 className="text-sm font-semibold text-white leading-snug">
                        {cu.axis || cu.name || cu.title || `Uncertainty ${i + 1}`}
                      </h3>
                    </div>
                    {cu.description && (
                      <p className="text-xs text-zinc-500 leading-relaxed mb-3">{cu.description}</p>
                    )}
                    <div className="space-y-2 mt-auto">
                      {cu.scenarios_high?.length > 0 && (
                        <div>
                          <span className="text-[10px] font-medium text-emerald-500 uppercase tracking-wider">High →</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {cu.scenarios_high.map((s, si) => (
                              <span key={si} title={s} className="text-xs px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/15">{s.length > 40 ? s.slice(0, 38) + '…' : s}</span>
                            ))}
                          </div>
                        </div>
                      )}
                      {cu.scenarios_low?.length > 0 && (
                        <div>
                          <span className="text-[10px] font-medium text-rose-400 uppercase tracking-wider">Low →</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {cu.scenarios_low.map((s, si) => (
                              <span key={si} title={s} className="text-xs px-1.5 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/15">{s.length > 40 ? s.slice(0, 38) + '…' : s}</span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </Card>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* No-Regret Moves */}
          {framing.no_regret_moves?.length > 0 && (
            <motion.div variants={fadeIn}>
              <SectionHeader icon={Shield} color="emerald" title="No-Regret Moves" subtitle={`${framing.no_regret_moves.length} robust actions`} />
              <div className="space-y-3">
                {framing.no_regret_moves.map((move, i) => {
                  const action = typeof move === 'string' ? move : move.action || move.description
                  const rationale = typeof move === 'object' ? move.rationale : null
                  const horizon = typeof move === 'object' ? move.horizon : null
                  const coveredRaw = typeof move === 'object' ? move.scenarios_covered : null
                  const covered = Array.isArray(coveredRaw) ? coveredRaw.length : coveredRaw
                  return (
                    <motion.div key={i} variants={fadeUp}>
                      <Card>
                        <div className="flex gap-3">
                          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0 mt-0.5">
                            <Shield size={16} className="text-emerald-400" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-white font-medium leading-relaxed">{action}</p>
                            {rationale && (
                              <p className="text-xs text-zinc-500 leading-relaxed mt-1.5">{rationale}</p>
                            )}
                            <div className="flex flex-wrap items-center gap-2 mt-2">
                              {horizon && (
                                <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/15">
                                  <Clock size={10} /> {String(horizon).replace(/_/g, ' ')}
                                </span>
                              )}
                              {covered != null && (
                                <span
                                  className="text-[10px] text-zinc-600"
                                  title={Array.isArray(coveredRaw) ? coveredRaw.join('\n') : undefined}
                                >
                                  covers {covered} of {scenarioList.length || '?'} scenarios
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </Card>
                    </motion.div>
                  )
                })}
              </div>
            </motion.div>
          )}

          {/* Scenario Strategies */}
          {sortedStrategies.length > 0 && (
            <motion.div variants={fadeIn}>
              <SectionHeader icon={TrendingUp} color="violet" title="Scenario Strategies" subtitle={`${sortedStrategies.length} scenarios ranked by MCDA`} />
              <div className="space-y-3">
                {sortedStrategies.map((ss, i) => {
                  const expanded = expandedStrategy === i
                  const scenario = scenarioMap[ss.scenario_title]
                  const rankIdx = ss.mcda_rank - 1 // medals only for ranks 1-3; rest fall back to zinc
                  return (
                    <motion.div key={i} variants={fadeUp}>
                      <div
                        onClick={() => setExpandedStrategy(expanded ? null : i)}
                        className={`glass rounded-xl p-5 glass-hover cursor-pointer border ${
                          rankIdx < 3 ? RANK_BORDER[rankIdx] : 'border-transparent'
                        } ${rankIdx < 3 ? RANK_GLOW[rankIdx] : ''} ${rankIdx === 0 ? 'shadow-lg' : ''}`}
                      >
                        <div className="flex items-center gap-4">
                          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${RANK_COLORS[rankIdx] || 'from-zinc-600 to-zinc-700'} flex items-center justify-center shrink-0 shadow-inner`}>
                            <span className="text-sm font-extrabold text-zinc-900">#{ss.mcda_rank}</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <h3 className="text-sm font-semibold text-white truncate">{ss.scenario_title}</h3>
                              {scenario && <TypeBadge type={scenario.type} />}
                            </div>
                            {scenario && (
                              <p className="text-xs text-zinc-500 mt-0.5 truncate">{scenario.narrative}</p>
                            )}
                          </div>
                          {scenario && scenario.topsis_closeness != null && (
                            <span className="text-lg font-mono font-bold text-zinc-400 shrink-0" title="TOPSIS closeness to ideal (1 = best, 0 = worst within set)">
                              {scenario.topsis_closeness.toFixed(2)}
                            </span>
                          )}
                          <ChevronDown
                            size={16}
                            className={`text-zinc-500 transition-transform duration-200 shrink-0 ${expanded ? 'rotate-180' : ''}`}
                          />
                        </div>

                        <AnimatePresence>
                          {expanded && (
                            <motion.div
                              initial={{ height: 0, opacity: 0 }}
                              animate={{ height: 'auto', opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }}
                              transition={{ duration: 0.25 }}
                              className="overflow-hidden"
                            >
                              <div className="mt-4 pt-4 border-t border-white/5 space-y-4">
                                {/* Capability Gaps */}
                                {ss.capability_gaps && (
                                  <DetailBlock
                                    icon={AlertTriangle}
                                    label="Capability Gaps"
                                    color="amber"
                                    content={ss.capability_gaps}
                                  />
                                )}

                                {/* Competitive Exposure */}
                                {ss.competitive_exposure && (
                                  <DetailBlock
                                    icon={Eye}
                                    label="Competitive Exposure"
                                    color="rose"
                                    content={ss.competitive_exposure}
                                  />
                                )}

                                {/* Early Indicators */}
                                {ss.early_indicators?.length > 0 && (
                                  <div>
                                    <div className="flex items-center gap-1.5 mb-2">
                                      <TrendingUp size={12} className="text-emerald-400" />
                                      <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-400">Early Indicators</span>
                                    </div>
                                    <div className="space-y-1.5">
                                      {(Array.isArray(ss.early_indicators) ? ss.early_indicators : [ss.early_indicators]).map((ind, ii) => (
                                        <div key={ii} className="flex gap-2 items-start">
                                          <ArrowRight size={10} className="text-emerald-500 mt-1 shrink-0" />
                                          <p className="text-xs text-zinc-400 leading-relaxed">
                                            {typeof ind === 'string' ? ind : ind.indicator || ind.description || JSON.stringify(ind)}
                                          </p>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* Decision Gate */}
                                {ss.decision_gate && (
                                  <div className="flex gap-2 items-start rounded-lg bg-violet-500/5 border border-violet-500/15 p-3">
                                    <Crosshair size={14} className="text-violet-400 shrink-0 mt-0.5" />
                                    <div>
                                      <span className="text-[10px] font-semibold uppercase tracking-wider text-violet-400 block mb-1">Decision Gate</span>
                                      <p className="text-xs text-zinc-300 leading-relaxed">
                                        {typeof ss.decision_gate === 'string' ? ss.decision_gate : ss.decision_gate.description || JSON.stringify(ss.decision_gate)}
                                      </p>
                                    </div>
                                  </div>
                                )}
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </div>
                    </motion.div>
                  )
                })}
              </div>
            </motion.div>
          )}
        </>
      )}

      {/* Top Scenarios quick reference */}
      {scenarioList.length > 0 && (
        <motion.div variants={fadeIn}>
          <SectionHeader icon={Trophy} color="blue" title="Scenario Rankings"
            subtitle="TOPSIS closeness to ideal (1 = best, 0 = worst within set)" />
          <p className="text-xs text-zinc-600 -mt-2 mb-4">
            Criteria scores are near-uniform across scenarios by design of the grounded auditor;
            the ranking differentiation comes from TOPSIS closeness.
          </p>
          <div className="grid gap-2">
            {[...scenarioList].sort((a, b) => a.rank - b.rank).map((s) => {
              const colors = SCENARIO_TYPE_COLORS[s.type] || SCENARIO_TYPE_COLORS.evolutionary
              const closeness = s.topsis_closeness ?? 0
              return (
                <div key={s.id} className="flex items-center gap-3 glass rounded-lg px-4 py-2.5">
                  <span className="text-sm font-extrabold w-6 text-center" style={{ color: colors.text }}>
                    {s.rank}
                  </span>
                  <div className="flex-1 min-w-0">
                    <span className="text-xs text-white font-medium truncate block">{s.title}</span>
                  </div>
                  <TypeBadge type={s.type} />
                  <div className="w-24 h-1.5 bg-zinc-800 rounded-full overflow-hidden shrink-0">
                    <div
                      className="h-full rounded-full transition-all duration-700"
                      style={{ width: `${Math.max(3, closeness * 100)}%`, backgroundColor: colors.dot }}
                    />
                  </div>
                  <span className="text-xs font-mono text-zinc-400 w-10 text-right">{closeness.toFixed(2)}</span>
                </div>
              )
            })}
          </div>
        </motion.div>
      )}
    </motion.div>
  )
}

function SectionHeader({ icon: Icon, color, title, subtitle }) {
  const colorMap = {
    amber: 'text-amber-400',
    emerald: 'text-emerald-400',
    violet: 'text-violet-400',
    blue: 'text-blue-400',
    rose: 'text-rose-400',
  }
  return (
    <div className="flex items-center gap-2 mb-4">
      <Icon size={18} className={colorMap[color] || 'text-zinc-400'} />
      <h2 className="text-lg font-semibold text-white">{title}</h2>
      {subtitle && <span className="text-xs text-zinc-600 ml-1">· {subtitle}</span>}
    </div>
  )
}

function DetailBlock({ icon: Icon, label, color, content }) {
  const colorMap = {
    amber: { icon: 'text-amber-400', label: 'text-amber-400' },
    rose: { icon: 'text-rose-400', label: 'text-rose-400' },
    blue: { icon: 'text-blue-400', label: 'text-blue-400' },
    violet: { icon: 'text-violet-400', label: 'text-violet-400' },
  }
  const c = colorMap[color] || colorMap.blue

  const renderContent = () => {
    if (typeof content === 'string') {
      return <p className="text-xs text-zinc-400 leading-relaxed">{content}</p>
    }
    if (Array.isArray(content)) {
      return (
        <ul className="space-y-1">
          {content.map((item, i) => (
            <li key={i} className="flex gap-2 items-start">
              <ArrowRight size={10} className={`${c.icon} mt-1 shrink-0`} />
              <span className="text-xs text-zinc-400">{typeof item === 'string' ? item : item.description || JSON.stringify(item)}</span>
            </li>
          ))}
        </ul>
      )
    }
    return <p className="text-xs text-zinc-400">{JSON.stringify(content)}</p>
  }

  return (
    <div>
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon size={12} className={c.icon} />
        <span className={`text-[10px] font-semibold uppercase tracking-wider ${c.label}`}>{label}</span>
      </div>
      {renderContent()}
    </div>
  )
}
