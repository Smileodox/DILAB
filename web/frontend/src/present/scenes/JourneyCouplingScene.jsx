import { useState } from 'react'
import { motion } from 'framer-motion'
import { MousePointerClick, Scale, Sparkles } from 'lucide-react'
import SlideFrame from './SlideFrame'

export const STEPS = 2

/*
 * Journey station 4 — the cross-impact "sudoku rules".
 * Left: radial network of our driver vs. the 13 coupled drivers (fixed angles by
 * index — fully deterministic). Right: click any node/edge to see the five
 * persona votes behind that judgment. The one coupling with a preserved
 * contradiction (+2 out / −2 back) pulses amber: that's the payoff click.
 */

const W = 700
const H = 520
const CX = 350
const CY = 260
const R = 186

const edgeColor = (s) => (s > 0 ? '#10b981' : s < 0 ? '#ef4444' : '#71717a')
const fmtScore = (v) => (v > 0 ? `+${v}` : `${v}`)
const truncate = (s, n = 22) => ((s ?? '').length > n ? `${s.slice(0, n - 1)}…` : (s ?? ''))
const prettyPersona = (id) =>
  (id || '').split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
const firstSentence = (s) => {
  const m = (s || '').match(/^[^.]*\./)
  return m ? m[0] : (s || '').slice(0, 160)
}
const isDissent = (c) => c?.score_out === 2 && c?.score_in === -2

function ScoreChip({ label, value }) {
  const cls =
    value > 0
      ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
      : value < 0
        ? 'bg-red-500/10 text-red-300 border-red-500/30'
        : 'bg-white/5 text-zinc-400 border-white/10'
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs ${cls}`}>
      <span className="text-zinc-500">{label}</span>
      <span className="font-bold tabular-nums">{fmtScore(value)}</span>
    </span>
  )
}

function PersonaRow({ p }) {
  const net = p?.net_score ?? 0
  const netCls =
    net > 0
      ? 'bg-emerald-500/15 text-emerald-300'
      : net < 0
        ? 'bg-red-500/15 text-red-300'
        : 'bg-white/5 text-zinc-400'
  return (
    <div className="py-2 border-b border-white/5 last:border-0">
      <div className="flex items-center gap-2">
        <span className="flex-1 min-w-0 truncate text-xs font-medium text-zinc-200">
          {prettyPersona(p?.persona_id)}
        </span>
        <span className="shrink-0 text-[11px] text-zinc-500">
          pro <span className="font-semibold text-emerald-400 tabular-nums">{p?.promoting_score ?? 0}</span>
          {' · '}
          inh <span className="font-semibold text-red-400 tabular-nums">{p?.inhibiting_score ?? 0}</span>
        </span>
        <span className={`shrink-0 px-1.5 py-0.5 rounded text-[11px] font-bold tabular-nums ${netCls}`}>
          {fmtScore(net)}
        </span>
      </div>
      <p className="mt-1 text-xs text-zinc-500 leading-snug">{firstSentence(p?.reasoning)}</p>
    </div>
  )
}

export default function JourneyCouplingScene({ data, step }) {
  const [selectedId, setSelectedId] = useState(null)
  const driver = data?.journey?.driver
  const couplings = data?.journey?.couplings ?? []
  // Panel-honesty numbers come from the live matrix via the bundle (see app.py).
  const nPairs = data?.improvement?.cib_counts?.pairs ?? 182
  const inhibPct = Math.round((data?.improvement?.cib_negative_share?.after ?? 0.29) * 100)
  const n = couplings.length || 1
  const sel = couplings.find((c) => c?.other_id === selectedId)

  return (
    <SlideFrame
      kicker="station 5 · cross-impact balance"
      kickerColor="#8b5cf6"
      title="Its futures must fit everyone else's"
      subtitle={`Five expert personas score how “${driver?.name ?? 'our driver'}” pushes or blocks each of the other 13 drivers, in both directions.`}
      wide
    >
      <div className="h-full flex flex-col min-h-0">
        <div className="flex-1 min-h-0 flex gap-6">
          {/* Radial coupling network */}
          <div className="w-[58%] min-w-0 flex items-center justify-center">
            <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full" preserveAspectRatio="xMidYMid meet">
              {/* Edges first so nodes sit on top */}
              {couplings.map((c, i) => {
                const a = -Math.PI / 2 + (i * 2 * Math.PI) / n
                const cos = Math.cos(a)
                const sin = Math.sin(a)
                const nx = CX + R * cos
                const ny = CY + R * sin
                const active = c?.other_id === selectedId
                return (
                  <g key={`e-${c?.other_id ?? i}`} onClick={() => setSelectedId(c?.other_id)} className="cursor-pointer">
                    <line
                      x1={CX + 38 * cos}
                      y1={CY + 38 * sin}
                      x2={nx - 12 * cos}
                      y2={ny - 12 * sin}
                      stroke={edgeColor(c?.score_out ?? 0)}
                      strokeWidth={1 + Math.abs(c?.score_out ?? 0) * 1.5 + (active ? 1 : 0)}
                      strokeOpacity={active ? 1 : 0.65}
                      strokeLinecap="round"
                      strokeDasharray={(c?.score_out ?? 0) < 0 ? '6 4' : undefined}
                    />
                    {/* fat invisible hit target */}
                    <line
                      x1={CX + 38 * cos}
                      y1={CY + 38 * sin}
                      x2={nx - 12 * cos}
                      y2={ny - 12 * sin}
                      stroke="transparent"
                      strokeWidth={16}
                    />
                  </g>
                )
              })}

              {/* Center: our driver */}
              <circle cx={CX} cy={CY} r={36} fill="rgba(59,130,246,0.12)" stroke="#3b82f6" strokeWidth={1.5} />
              <text x={CX} y={CY - 2} textAnchor="middle" fontSize="11" fontWeight="600" fill="#93c5fd">
                our
              </text>
              <text x={CX} y={CY + 12} textAnchor="middle" fontSize="11" fontWeight="600" fill="#93c5fd">
                driver
              </text>

              {/* Nodes + labels */}
              {couplings.map((c, i) => {
                const a = -Math.PI / 2 + (i * 2 * Math.PI) / n
                const cos = Math.cos(a)
                const sin = Math.sin(a)
                const nx = CX + R * cos
                const ny = CY + R * sin
                const lx = CX + (R + 15) * cos
                const ly = CY + (R + 15) * sin
                const anchor = Math.abs(cos) < 0.35 ? 'middle' : cos > 0 ? 'start' : 'end'
                const dy = sin > 0.6 ? 13 : sin < -0.6 ? -6 : 4
                const active = c?.other_id === selectedId
                const special = isDissent(c)
                const color = edgeColor(c?.score_out ?? 0)
                return (
                  <g
                    key={`n-${c?.other_id ?? i}`}
                    onClick={() => setSelectedId(c?.other_id)}
                    className="cursor-pointer"
                  >
                    {special && (
                      <motion.circle
                        cx={nx}
                        cy={ny}
                        fill="none"
                        stroke="#f59e0b"
                        strokeWidth={1.5}
                        initial={false}
                        animate={{ r: [11, 20, 11], opacity: [0.7, 0, 0.7] }}
                        transition={{ duration: 2.2, repeat: Infinity, ease: 'easeOut' }}
                      />
                    )}
                    {active && <circle cx={nx} cy={ny} r={13} fill="none" stroke="#e4e4e7" strokeWidth={1.5} />}
                    <circle
                      cx={nx}
                      cy={ny}
                      r={9}
                      fill="#18181b"
                      stroke={special ? '#f59e0b' : color}
                      strokeWidth={2}
                    />
                    <text
                      x={lx}
                      y={ly + dy}
                      textAnchor={anchor}
                      fontSize="12"
                      fill={active ? '#fafafa' : '#a1a1aa'}
                      fontWeight={active ? 600 : 400}
                    >
                      {truncate(c?.other_name)}
                    </text>
                    {special && (
                      <g
                        transform={`translate(${CX + (R - 54) * cos}, ${CY + (R - 54) * sin})`}
                        pointerEvents="none"
                      >
                        <rect x={-56} y={-10} width={112} height={20} rx={10} fill="#451a03" fillOpacity={0.92} stroke="rgba(245,158,11,0.5)" />
                        <text textAnchor="middle" dy="3.5" fontSize="10" fill="#fbbf24" letterSpacing="0.04em">
                          preserved dissent
                        </text>
                      </g>
                    )}
                  </g>
                )
              })}
            </svg>
          </div>

          {/* Detail panel */}
          <div className="flex-1 min-w-0 glass rounded-2xl p-5 flex flex-col min-h-0">
            {!sel ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center gap-3">
                <MousePointerClick size={28} className="text-zinc-600" />
                <p className="text-sm text-zinc-500 max-w-[26ch]">
                  Click a coupling to see the panel argue.
                </p>
              </div>
            ) : (
              <>
                <div className="shrink-0">
                  {isDissent(sel) && (
                    <div className="mb-3 flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2.5">
                      <Sparkles size={14} className="mt-0.5 shrink-0 text-amber-300" />
                      <p className="text-xs leading-snug text-amber-200">
                        <span className="font-semibold">Preserved dissent.</span> Our driver promotes this
                        one (+2 out) while it pushes back (−2 in). The pipeline keeps the contradiction:
                        it is signal, not noise to average away.
                      </p>
                    </div>
                  )}
                  <h3 className="text-base font-semibold text-white leading-snug">{sel?.other_name}</h3>
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    <ScoreChip label="out →" value={sel?.score_out ?? 0} />
                    <ScoreChip label="← back" value={sel?.score_in ?? 0} />
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full border border-white/10 bg-white/5 text-xs text-zinc-400">
                      consensus: <span className="ml-1 font-medium text-zinc-200">{sel?.consensus ?? '—'}</span>
                    </span>
                  </div>
                </div>
                <div className="mt-3 flex-1 min-h-0 overflow-y-auto pr-1">
                  <p className="text-[11px] uppercase tracking-wider text-zinc-500 mb-1">
                    how the {data?.journey?.personas?.length ?? 5} personas voted (outgoing)
                  </p>
                  {(sel?.persona_scores ?? []).map((p, i) => (
                    <PersonaRow key={p?.persona_id ?? i} p={p} />
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Step 1: the balance stat bar stamps in */}
        <motion.div
          initial={{ opacity: 0, y: 10, scale: 1.04 }}
          animate={step >= 1 ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 10, scale: 1.04 }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
          className="mt-4 shrink-0 glass rounded-xl px-5 py-3 flex flex-wrap items-center gap-x-3 gap-y-1"
        >
          <Scale size={16} className="shrink-0 text-amber-300" />
          <span className="text-sm text-zinc-300">
            <span className="font-semibold text-white tabular-nums">{nPairs}</span> pairwise judgments ·{' '}
            <span className="font-semibold text-white">{inhibPct}% inhibiting</span>, inside the Weimer-Jehle
            20–30% band for real systems
          </span>
          <span className="text-zinc-600">·</span>
          <span className="text-sm font-semibold text-amber-200">Contradictory combinations die here.</span>
        </motion.div>
      </div>
    </SlideFrame>
  )
}
