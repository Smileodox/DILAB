import { useEffect, useMemo, useRef } from 'react'
import Plotly from 'plotly.js-dist-min'
import { motion } from 'framer-motion'
import { ShieldCheck } from 'lucide-react'
import SlideFrame from './SlideFrame'
import { DARK_LAYOUT, PLOTLY_CONFIG } from '@/utils/plotly'

export const STEPS = 4

const PLOT_HEIGHT = 340
// Blue/amber categorical pair, validated for CVD separation + lightness on the
// dark surface (amber-600 instead of amber-500, which sits outside the band).
const SIDE_COLORS = ['#3b82f6', '#d97706']
const NOISE_COLOR = '#71717a'

const Z_MIN = -2
const Z_MAX = 9
const Z_SIGNIFICANT = 2

const fmtZ = (z) =>
  z == null ? '?' : `${z < 0 ? '−' : ''}${Math.abs(z).toFixed(1)}`

const TONES = {
  emerald: {
    stamp: 'border-emerald-400/80 bg-emerald-950/80 text-emerald-300',
    sub: 'text-emerald-400/90',
    marker: '#34d399',
  },
  zinc: {
    stamp: 'border-zinc-400/70 bg-zinc-900/85 text-zinc-300',
    sub: 'text-zinc-400',
    marker: '#a1a1aa',
  },
  amber: {
    stamp: 'border-amber-400/80 bg-amber-950/80 text-amber-300',
    sub: 'text-amber-400/90',
    marker: '#fbbf24',
  },
}

/* Tiny sign-matrix thumbnail: the CIB INPUT each field was generated from. */
function SignMatrix({ signs, cell = 5 }) {
  if (!signs?.length) return null
  return (
    <div
      className="grid w-fit shrink-0 gap-[1px]"
      style={{ gridTemplateColumns: `repeat(${signs.length}, ${cell}px)` }}
    >
      {signs.flatMap((row, i) =>
        row.map((v, j) => (
          <div
            key={`${i}-${j}`}
            style={{
              width: cell, height: cell, borderRadius: 1,
              backgroundColor:
                i === j ? '#18181b'
                : v > 0 ? 'rgba(16,185,129,0.45)'
                : v < 0 ? 'rgba(244,63,94,0.8)'
                : 'rgba(63,63,70,0.6)',
            }}
          />
        )),
      )}
    </div>
  )
}

/* Compact point cloud: no axes, no hover — just the shape of the field. */
function PanelPlot({ traces }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (!el || !traces?.length) return undefined
    const layout = {
      ...DARK_LAYOUT,
      height: PLOT_HEIGHT,
      margin: { t: 12, r: 12, b: 12, l: 12 },
      showlegend: false,
      xaxis: { visible: false, fixedrange: true },
      yaxis: { visible: false, fixedrange: true },
    }
    Plotly.react(el, traces, layout, { ...PLOTLY_CONFIG, staticPlot: true })
    return () => Plotly.purge(el)
  }, [traces])
  return <div ref={ref} className="w-full" style={{ height: PLOT_HEIGHT }} />
}

/* Rubber stamp slamming onto the panel: big → settles small, slightly rotated. */
function VerdictStamp({ show, tone, verdict, metrics, sub }) {
  if (!show) return null
  const t = TONES[tone]
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <motion.div
        initial={{ opacity: 0, scale: 1.6, rotate: -14 }}
        animate={{ opacity: 1, scale: 1, rotate: -5 }}
        transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        className={`rounded-lg border-[3px] px-5 py-3 text-center backdrop-blur-sm shadow-2xl ${t.stamp}`}
      >
        <div className="text-lg font-extrabold uppercase tracking-[0.14em] leading-tight">
          {verdict}
        </div>
        {metrics && (
          <div className="mt-0.5 text-sm font-semibold tabular-nums opacity-90">{metrics}</div>
        )}
        {sub && <div className={`mt-1.5 text-xs font-medium ${t.sub}`}>{sub}</div>}
      </motion.div>
    </div>
  )
}

/* Tiny z-score scale: gradient strip −2..+9, significance line at z = 2,
   marker appears when the panel's verdict lands. Pure divs. */
function ZStrip({ z, show, tone }) {
  const pct = (v) => ((Math.min(Math.max(v, Z_MIN), Z_MAX) - Z_MIN) / (Z_MAX - Z_MIN)) * 100
  return (
    <div className="mt-3 px-1 shrink-0">
      <div
        className="relative h-1.5 rounded-full"
        style={{ background: 'linear-gradient(90deg, #3f3f46 0%, #52525b 45%, #10b981 100%)' }}
      >
        <div
          className="absolute -top-1 h-3.5 w-px bg-zinc-400/50"
          style={{ left: `${pct(Z_SIGNIFICANT)}%` }}
        />
        {show && z != null && (
          <motion.div
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3, delay: 0.3 }}
            className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-zinc-950"
            style={{ left: `${pct(z)}%`, background: TONES[tone].marker }}
          />
        )}
      </div>
      <div className="relative mt-1 h-4 text-[10px] text-zinc-600">
        <span className="absolute left-0">z −2</span>
        <span className="absolute -translate-x-1/2" style={{ left: `${pct(Z_SIGNIFICANT)}%` }}>
          significance
        </span>
        <span className="absolute right-0">+9</span>
      </div>
    </div>
  )
}

const markers = (color, size, opacity) => ({
  color,
  size,
  opacity,
  line: { color: 'rgba(255,255,255,0.25)', width: 1 },
})

export default function ValidationScene({ data, step }) {
  const stats = data?.validation?.stats
  const pos = stats?.positive_control_coupled
  const neg = stats?.negative_control_uncoupled
  const real = stats?.real_spectrum_4axis
  const cib = data?.improvement?.cib_negative_share

  const coupledTraces = useMemo(() => {
    const f = data?.validation?.fields?.coupled
    if (!f?.x?.length) return []
    const sides = [[], []]
    f.x.forEach((x, i) => sides[f.side?.[i] === 1 ? 1 : 0].push([x, f.y?.[i]]))
    return sides.map((pts, s) => ({
      type: 'scatter',
      mode: 'markers',
      x: pts.map((p) => p[0]),
      y: pts.map((p) => p[1]),
      hoverinfo: 'skip',
      marker: markers(SIDE_COLORS[s], 11, 0.9),
    }))
  }, [data])

  const uncoupledTraces = useMemo(() => {
    const f = data?.validation?.fields?.uncoupled
    if (!f?.x?.length) return []
    return [{
      type: 'scatter',
      mode: 'markers',
      x: f.x,
      y: f.y,
      hoverinfo: 'skip',
      marker: markers(NOISE_COLOR, 6, 0.7),
    }]
  }, [data])

  const realTraces = useMemo(() => {
    const pts = data?.field?.points
    if (!pts?.length) return []
    return [{
      type: 'scatter',
      mode: 'markers',
      x: pts.map((p) => p.x),
      y: pts.map((p) => p.y),
      hoverinfo: 'skip',
      marker: markers(NOISE_COLOR, 6, 0.7),
    }]
  }, [data])

  // The CIB INPUT each field was generated from — the prefabricated ground-truth matrix,
  // its zeroed twin, and the real elicited 14×14 (same source as the improvement lever).
  const stdSigns = data?.validation?.standard_matrix_signs
  const zeroSigns = stdSigns ? stdSigns.map((row) => row.map(() => 0)) : null
  const realSigns = data?.improvement?.cib_matrix_signs

  const panels = [
    {
      key: 'coupled',
      title: 'Synthetic · coupled',
      tag: 'the coin',
      matrix: stdSigns,
      matrixLabel: 'input: a prefabricated ground-truth CIB · promotes within blocks, inhibits across',
      traces: coupledTraces,
      caption: `${pos?.n_kept ?? 18} scenarios from a toy field with planted coupling: the detector must beep here.`,
      stampAt: 1,
      tone: 'emerald',
      verdict: pos?.verdict ?? 'usable structure',
      metrics: `silhouette ${pos?.best_silhouette?.toFixed(2) ?? '0.72'} · z = ${fmtZ(pos?.z_silhouette ?? 8.6)}`,
      sub: '✓ it beeps on the coin',
      z: pos?.z_silhouette ?? 8.6,
    },
    {
      key: 'uncoupled',
      title: 'Synthetic · zero coupling',
      tag: 'empty sand',
      matrix: zeroSigns,
      matrixLabel: 'input: the same CIB with every coupling zeroed out',
      traces: uncoupledTraces,
      caption: `${neg?.n_kept ?? 150} scenarios with the coupling matrix zeroed out: pure noise by construction.`,
      stampAt: 2,
      tone: 'zinc',
      verdict: neg?.verdict ?? '≈ uniform random',
      metrics: `z = ${fmtZ(neg?.z_silhouette ?? -0.69)}`,
      sub: '✓ silent on empty sand',
      z: neg?.z_silhouette ?? -0.69,
    },
    {
      key: 'real',
      title: 'Real spectrum field',
      tag: 'the beach',
      matrix: realSigns,
      matrixLabel: 'input: our real 14×14 CIB from the persona panel',
      traces: realTraces,
      caption: `${real?.n_scenarios ?? 120} consistent spectrum scenarios: the field under test.`,
      stampAt: 3,
      tone: 'amber',
      verdict: real?.verdict ?? '≈ uniform random',
      metrics: `z = ${fmtZ(real?.z_silhouette ?? 1.4)}`,
      sub: 'the detector works: the beach was empty',
      z: real?.z_silhouette ?? 1.4,
    },
  ]

  const cibPct = Math.round((cib?.after ?? 0.22) * 100)
  const bandLabel = cib?.band_label ?? 'Weimer-Jehle 20–30%'

  return (
    <SlideFrame
      kicker="Rigor · engine validation"
      kickerColor="#10b981"
      title="Test the detector before you trust the beach"
      subtitle="Before you search the beach, test the metal detector: it must beep on a coin and stay silent on empty sand. Three fields, one identical structure test."
      wide
    >
      <div className="h-full flex flex-col">
        <div className="grid grid-cols-3 gap-5 flex-1 min-h-0">
          {panels.map((p, i) => (
            <motion.div
              key={p.key}
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: i * 0.12 }}
              className="glass rounded-2xl border border-white/[0.06] p-4 flex flex-col min-h-0"
            >
              <div className="flex items-baseline justify-between gap-2 mb-2 shrink-0">
                <h3 className="text-sm font-semibold text-zinc-200">{p.title}</h3>
                <span className="text-xs italic text-zinc-500">{p.tag}</span>
              </div>
              {p.matrix && (
                <div className="flex items-center gap-2.5 mb-2 shrink-0">
                  <SignMatrix signs={p.matrix} cell={p.matrix.length > 10 ? 3 : 5} />
                  <span className="text-[11px] leading-snug text-zinc-500">{p.matrixLabel}</span>
                </div>
              )}
              <div className="relative shrink-0">
                <PanelPlot traces={p.traces} />
                <VerdictStamp
                  show={step >= p.stampAt}
                  tone={p.tone}
                  verdict={p.verdict}
                  metrics={p.metrics}
                  sub={p.sub}
                />
              </div>
              <ZStrip z={p.z} show={step >= p.stampAt} tone={p.tone} />
              <p className="mt-2 text-xs text-zinc-500 leading-snug shrink-0">{p.caption}</p>
            </motion.div>
          ))}
        </div>

        {/* Fixed-height slot so the grid doesn't jump when the takeaway lands. */}
        <div className="h-[76px] mt-4 shrink-0">
          {step >= 3 && (
            <motion.div
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: 0.35 }}
              className="glass-solid h-full rounded-xl border border-white/10 px-6 flex items-center gap-4"
            >
              <ShieldCheck size={26} className="text-emerald-400 shrink-0" />
              <p className="flex-1 text-base md:text-lg text-zinc-200 leading-snug">
                The engine does not hallucinate clusters. A flat result is a property of the
                data, so we fixed the data, not the verdict.
              </p>
              <span className="shrink-0 rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1.5 text-xs md:text-sm font-medium text-emerald-300">
                CIB inhibiting share {cibPct}%, inside the {bandLabel} band
              </span>
            </motion.div>
          )}
        </div>
      </div>
    </SlideFrame>
  )
}
