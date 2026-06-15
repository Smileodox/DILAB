import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import {
  Database, Boxes, TrendingUp, Merge, Grid3x3,
  ArrowLeftRight, CheckCircle, FileText, BarChart3,
  ChevronRight, ExternalLink, ArrowRight,
} from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import Card from '@/components/ui/Card'
import { staggerContainer, fadeUp } from '@/utils/animation'
import { PIPELINE_COLORS } from '@/utils/colors'

function FlowArrow({ color = '#3b82f6' }) {
  return <ArrowRight size={14} style={{ color }} className="shrink-0 mx-1 opacity-50" />
}

function FlowBox({ label, sub, color = '#3b82f6', accent }) {
  return (
    <div className="flex flex-col items-center gap-0.5">
      <div
        className="px-2.5 py-1.5 rounded-md text-[10px] font-semibold leading-tight text-center whitespace-nowrap"
        style={{ background: `${accent || color}15`, border: `1px solid ${accent || color}30`, color: accent || color }}
      >
        {label}
      </div>
      {sub && <span className="text-[9px] text-zinc-500">{sub}</span>}
    </div>
  )
}

function KBVisual({ data }) {
  return (
    <div className="flex items-center justify-center gap-1 flex-wrap">
      <FlowBox label="45 PDFs" sub="R&S docs" color="#3b82f6" />
      <FlowArrow />
      <FlowBox label="Split" sub="1500 tok" color="#3b82f6" accent="#60a5fa" />
      <FlowArrow />
      <FlowBox label="2,850 Chunks" sub="+ metadata" color="#3b82f6" accent="#93c5fd" />
      <FlowArrow />
      <FlowBox label="Vector DB" sub="RAG-ready" color="#10b981" />
    </div>
  )
}

function BOMVisual() {
  const nodes = [
    { label: 'R&S Product', depth: 0 },
    { label: 'RF Frontend', depth: 1 },
    { label: 'ADC', depth: 2, driver: true },
    { label: 'Preselection', depth: 2, driver: true },
    { label: 'Digital Processing', depth: 1 },
    { label: 'FFT Engine', depth: 2, driver: true },
    { label: 'DDC', depth: 2, driver: true },
  ]
  return (
    <div className="space-y-1">
      {nodes.map((n, i) => (
        <div key={i} className="flex items-center gap-1.5" style={{ paddingLeft: n.depth * 20 }}>
          {n.depth > 0 && <span className="text-zinc-700 text-[10px]">└</span>}
          <div className={`px-2 py-0.5 rounded text-[10px] font-medium ${
            n.driver
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'bg-zinc-800/60 text-zinc-400 border border-zinc-700/30'
          }`}>
            {n.label}
          </div>
          {n.driver && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
        </div>
      ))}
    </div>
  )
}

function TrendVisual() {
  const trends = [
    { label: '5G/6G spectrum sharing', rel: 0.9 },
    { label: 'ITU harmonization', rel: 0.85 },
    { label: 'Sovereign reservations', rel: 0.7 },
    { label: 'AI-based monitoring', rel: 0.65 },
    { label: 'Security frameworks', rel: 0.6 },
  ]
  return (
    <div className="space-y-1.5">
      {trends.map((t, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-[10px] text-zinc-500 w-3 text-right">{i + 1}</span>
          <div className="flex-1 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <motion.div
              className="h-full rounded-full bg-violet-500"
              initial={{ width: 0 }}
              animate={{ width: `${t.rel * 100}%` }}
              transition={{ duration: 0.6, delay: i * 0.08 }}
            />
          </div>
          <span className="text-[10px] text-zinc-400 w-32 truncate">{t.label}</span>
        </div>
      ))}
    </div>
  )
}

function MergeVisual({ data }) {
  const bom = data?.drivers_by_origin?.bom || 19
  const trend = data?.drivers_by_origin?.trend || 5
  const total = data?.drivers_total || 24
  return (
    <div className="flex items-center justify-center gap-2">
      <div className="flex flex-col items-center gap-1">
        <div className="w-20 h-20 rounded-full border-2 border-sky-500/40 bg-sky-500/10 flex flex-col items-center justify-center">
          <span className="text-lg font-bold text-sky-400">{bom}</span>
          <span className="text-[9px] text-sky-400/60">BOM</span>
        </div>
      </div>
      <div className="flex flex-col items-center gap-1">
        <svg width="40" height="24" viewBox="0 0 40 24">
          <path d="M4 6 L20 12 L4 18" fill="none" stroke="#6b7280" strokeWidth="1" strokeDasharray="3 2" />
          <path d="M36 6 L20 12 L36 18" fill="none" stroke="#6b7280" strokeWidth="1" strokeDasharray="3 2" />
        </svg>
        <span className="text-[9px] text-zinc-500">cosine 0.85</span>
      </div>
      <div className="flex flex-col items-center gap-1">
        <div className="w-20 h-20 rounded-full border-2 border-violet-500/40 bg-violet-500/10 flex flex-col items-center justify-center">
          <span className="text-lg font-bold text-violet-400">{trend}</span>
          <span className="text-[9px] text-violet-400/60">Trends</span>
        </div>
      </div>
      <ArrowRight size={16} className="text-zinc-600 mx-2" />
      <div className="flex flex-col items-center gap-1">
        <div className="w-20 h-20 rounded-full border-2 border-blue-500/40 bg-blue-500/10 flex flex-col items-center justify-center">
          <span className="text-lg font-bold text-blue-400">{total}</span>
          <span className="text-[9px] text-blue-400/60">Unified</span>
        </div>
      </div>
    </div>
  )
}

function MorphVisual() {
  const rows = ['Driver A', 'Driver B', 'Driver C']
  const cols = [
    ['Optimistic', 'Moderate', 'Pessimistic', 'Extreme'],
    ['Growth', 'Stable', 'Decline'],
    ['Integrated', 'Regional', 'Fragmented', 'Stagnant'],
  ]
  const plaus = { 'high': '#10b981', 'medium': '#f59e0b', 'low': '#ef4444' }
  const plausMap = [
    ['high', 'medium', 'medium', 'low'],
    ['medium', 'high', 'low'],
    ['high', 'high', 'medium', 'low'],
  ]
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-1" style={{ gridTemplateColumns: '80px repeat(4, 1fr)' }}>
        <div />
        {['M1', 'M2', 'M3', 'M4'].map(h => (
          <div key={h} className="text-[9px] text-zinc-500 text-center font-medium">{h}</div>
        ))}
        {rows.map((r, ri) => (
          <>
            <div key={r} className="text-[10px] text-zinc-400 flex items-center">{r}</div>
            {(cols[ri] || []).map((c, ci) => (
              <div
                key={ci}
                className="px-1.5 py-1 rounded text-[9px] text-center font-medium truncate"
                style={{
                  background: `${plaus[plausMap[ri]?.[ci] || 'medium']}12`,
                  border: `1px solid ${plaus[plausMap[ri]?.[ci] || 'medium']}25`,
                  color: plaus[plausMap[ri]?.[ci] || 'medium'],
                }}
              >
                {c}
              </div>
            ))}
            {cols[ri].length < 4 && <div />}
          </>
        ))}
      </div>
    </div>
  )
}

function CIBVisual() {
  const size = 5
  const scores = [
    [0, 2, 1, -1, 1],
    [1, 0, 2, 0, 1],
    [0, 1, 0, 2, -2],
    [1, 1, 1, 0, 1],
    [2, 0, 1, 1, 0],
  ]
  const colorFor = (v) => {
    if (v > 0) return `rgba(16,185,129,${v / 3})`
    if (v < 0) return `rgba(239,68,68,${Math.abs(v) / 3})`
    return 'rgba(63,63,70,0.3)'
  }
  return (
    <div className="flex items-start gap-4">
      <div>
        <div className="grid gap-[2px]" style={{ gridTemplateColumns: `repeat(${size}, 24px)` }}>
          {scores.flat().map((v, i) => (
            <div
              key={i}
              className="w-6 h-6 rounded-sm flex items-center justify-center text-[9px] font-mono text-zinc-300"
              style={{ background: colorFor(v) }}
            >
              {v !== 0 ? (v > 0 ? `+${v}` : v) : ''}
            </div>
          ))}
        </div>
        <div className="mt-1.5 flex items-center gap-3 text-[9px] text-zinc-500">
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-500/60" /> promoting</span>
          <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-red-500/60" /> inhibiting</span>
        </div>
      </div>
      <div className="space-y-3">
        {/* Delphi panel */}
        <div className="text-[9px] text-zinc-500 font-medium uppercase tracking-wider mb-1">Simulated Delphi Panel</div>
        <div className="space-y-1.5">
          {[
            { name: 'RF Systems Engineer', model: 'gpt-4.1', color: '#3b82f6', scores: ['+2', '+1', '+1', '+2'] },
            { name: 'Regulatory Analyst', model: 'gpt-4.1-mini', color: '#f59e0b', scores: ['+2', '0', '+1', '+2'] },
            { name: 'R&D Strategy Manager', model: 'gpt-4.1-mini', color: '#8b5cf6', scores: ['+1', '+1', '+2', '+1'] },
            { name: 'Academic Researcher', model: 'gpt-4.1', color: '#10b981', scores: ['+1', '0', '+1', '+1'] },
          ].map((p) => (
            <div key={p.name} className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ background: p.color }} />
              <span className="text-[10px] text-zinc-300 w-28 truncate">{p.name}</span>
              <div className="flex gap-[2px]">
                {p.scores.map((s, i) => (
                  <div
                    key={i}
                    className="w-5 h-4 rounded-sm flex items-center justify-center text-[8px] font-mono"
                    style={{
                      background: s.startsWith('+') && s !== '+0' ? 'rgba(16,185,129,0.2)' : s.startsWith('-') ? 'rgba(239,68,68,0.2)' : 'rgba(63,63,70,0.3)',
                      color: s.startsWith('+') && s !== '+0' ? '#10b981' : s.startsWith('-') ? '#ef4444' : '#71717a',
                    }}
                  >
                    {s}
                  </div>
                ))}
              </div>
              <span className="text-[8px] text-zinc-600 font-mono">{p.model}</span>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-1 mt-1">
          <svg width="60" height="16" viewBox="0 0 60 16">
            <path d="M0 4 L15 8 L0 12" fill="none" stroke="#6b7280" strokeWidth="0.8" strokeDasharray="2 1.5" />
            <path d="M0 4 L15 8" fill="none" stroke="#6b7280" strokeWidth="0.8" strokeDasharray="2 1.5" />
            <path d="M0 8 L15 8" fill="none" stroke="#6b7280" strokeWidth="0.8" strokeDasharray="2 1.5" />
            <path d="M0 12 L15 8" fill="none" stroke="#6b7280" strokeWidth="0.8" strokeDasharray="2 1.5" />
            <rect x="17" y="3" width="26" height="10" rx="2" fill="rgba(139,92,246,0.15)" stroke="rgba(139,92,246,0.3)" strokeWidth="0.8" />
            <text x="30" y="10.5" textAnchor="middle" fill="#a78bfa" fontSize="6" fontFamily="monospace">MC agg</text>
            <path d="M45 8 L58 8 M54 5 L58 8 L54 11" fill="none" stroke="#6b7280" strokeWidth="0.8" />
          </svg>
          <span className="text-[9px] text-zinc-500">2,000 samples → median score</span>
        </div>
      </div>
    </div>
  )
}

function FunnelVisual({ data }) {
  const stages = [
    { label: 'Combinatorial space', value: '268M+', width: 100, color: '#3f3f46' },
    { label: 'Fixed points (CIB)', value: data?.total_fixed_points || 106, width: 40, color: '#8b5cf6' },
    { label: 'Scenario seeds', value: data?.consistency_seeds || 20, width: 20, color: '#10b981' },
  ]
  return (
    <div className="flex flex-col items-center gap-1.5">
      {stages.map((s, i) => (
        <div key={i} className="flex flex-col items-center">
          <motion.div
            className="rounded-md flex items-center justify-center gap-2 py-1.5"
            style={{
              width: `${s.width * 2.5 + 60}px`,
              background: `${s.color}20`,
              border: `1px solid ${s.color}40`,
            }}
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: `${s.width * 2.5 + 60}px`, opacity: 1 }}
            transition={{ duration: 0.4, delay: i * 0.15 }}
          >
            <span className="text-xs font-bold" style={{ color: s.color === '#3f3f46' ? '#a1a1aa' : s.color }}>{s.value}</span>
            <span className="text-[9px] text-zinc-500">{s.label}</span>
          </motion.div>
          {i < stages.length - 1 && (
            <svg width="12" height="12" viewBox="0 0 12 12" className="my-0.5 text-zinc-700">
              <path d="M6 0 L6 12 M3 8 L6 12 L9 8" fill="none" stroke="currentColor" strokeWidth="1" />
            </svg>
          )}
        </div>
      ))}
    </div>
  )
}

function ScenarioGenVisual() {
  const types = [
    { label: 'Evolutionary', color: '#3b82f6', count: 8 },
    { label: 'Disruptive', color: '#10b981', count: 5 },
    { label: 'Cautionary', color: '#f59e0b', count: 4 },
    { label: 'Wildcard', color: '#8b5cf6', count: 3 },
  ]
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1">
        <FlowBox label="Config Seed" color="#8b5cf6" />
        <FlowArrow color="#8b5cf6" />
        <FlowBox label="RAG Retrieval" color="#8b5cf6" accent="#a78bfa" />
        <FlowArrow color="#8b5cf6" />
        <FlowBox label="LLM Narrative" color="#10b981" />
        <FlowArrow color="#10b981" />
        <FlowBox label="Typed Scenario" color="#10b981" accent="#34d399" />
      </div>
      <div className="flex gap-2 mt-2">
        {types.map(t => (
          <div key={t.label} className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full" style={{ background: t.color }} />
            <span className="text-[9px] text-zinc-500">{t.label}</span>
            <span className="text-[9px] font-bold" style={{ color: t.color }}>{t.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function MCDAVisual() {
  const criteria = [
    { label: 'Impact', weight: 0.35 },
    { label: 'Probability', weight: 0.25 },
    { label: 'Actionability', weight: 0.20 },
    { label: 'Time Horizon', weight: 0.12 },
    { label: 'Risk Severity', weight: 0.08 },
  ]
  return (
    <div className="space-y-2">
      <div className="text-[9px] text-zinc-500 mb-1">AHP-Derived Criteria Weights</div>
      {criteria.map((c, i) => (
        <div key={c.label} className="flex items-center gap-2">
          <span className="text-[10px] text-zinc-400 w-20 text-right">{c.label}</span>
          <div className="flex-1 h-2.5 rounded-full bg-zinc-800 overflow-hidden">
            <motion.div
              className="h-full rounded-full"
              style={{ background: `hsl(${160 - i * 25}, 70%, 50%)` }}
              initial={{ width: 0 }}
              animate={{ width: `${c.weight * 100 * 2.5}%` }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
            />
          </div>
          <span className="text-[10px] font-mono text-zinc-300 w-8">{(c.weight * 100).toFixed(0)}%</span>
        </div>
      ))}
      <div className="flex items-center gap-1 mt-1.5">
        <FlowBox label="AHP Weights" color="#f59e0b" />
        <span className="text-[10px] text-zinc-600 mx-1">+</span>
        <FlowBox label="LLM Scores" color="#3b82f6" />
        <FlowArrow />
        <FlowBox label="TOPSIS Rank" color="#10b981" />
      </div>
    </div>
  )
}

function StepVisual({ stepId, data }) {
  switch (stepId) {
    case 'kb': return <KBVisual data={data} />
    case 'bom': return <BOMVisual />
    case 'trends': return <TrendVisual />
    case 'merge': return <MergeVisual data={data} />
    case 'morph': return <MorphVisual />
    case 'cib': return <CIBVisual />
    case 'consistency': return <FunnelVisual data={data} />
    case 'scenarios': return <ScenarioGenVisual />
    case 'mcda': return <MCDAVisual />
    default: return null
  }
}

const STEPS = [
  {
    id: 'kb',
    label: 'Knowledge Base',
    icon: Database,
    category: 'input',
    link: '/',
    description: 'Ingest and chunk R&S product documentation, ITU regulatory frameworks, and technology whitepapers into a structured, searchable corpus.',
    methodology: 'PDF/HTML parsing → recursive text splitting (1500 tokens, 200 overlap) → metadata extraction (source, date, section) → vector storage for downstream RAG retrieval.',
    metricsFn: (d) => [
      { label: 'Documents', value: d.sources },
      { label: 'Chunks', value: d.chunks?.toLocaleString() },
    ],
  },
  {
    id: 'bom',
    label: 'BOM Decomposition',
    icon: Boxes,
    category: 'input',
    link: '/bom',
    description: 'Decompose the R&S product into a hierarchical Bill of Materials tree, identifying functional components and subsystems.',
    methodology: 'LLM-guided hierarchical extraction from product specs → parent-child relationship mapping → driver candidate identification at leaf nodes → confidence scoring per component.',
    metricsFn: (d) => [
      { label: 'BOM Drivers', value: d.drivers_by_origin?.bom },
    ],
  },
  {
    id: 'trends',
    label: 'Trend Scanning',
    icon: TrendingUp,
    category: 'input',
    link: '/drivers',
    description: 'Scan regulatory and technology landscape for external trends that could impact spectrum monitoring capabilities by 2035.',
    methodology: 'RAG-powered extraction from regulatory corpus → trend identification with evidence grounding → relevance scoring against product domain → deduplication via embedding similarity.',
    metricsFn: (d) => [
      { label: 'Trend Drivers', value: d.drivers_by_origin?.trend },
    ],
  },
  {
    id: 'merge',
    label: 'Driver Merge',
    icon: Merge,
    category: 'analysis',
    link: '/drivers',
    description: 'Unify BOM-derived and trend-derived drivers into a single, deduplicated set of technology drivers with clear provenance.',
    methodology: 'Pairwise embedding similarity (text-embedding-3-small, cosine threshold 0.85) → LLM-assisted merge decisions → provenance tracking (BOM, Trend, or Both) → confidence consolidation.',
    metricsFn: (d) => [
      { label: 'Unified Drivers', value: d.drivers_total },
      { label: 'From BOM', value: d.drivers_by_origin?.bom },
      { label: 'From Trends', value: d.drivers_by_origin?.trend },
    ],
  },
  {
    id: 'morph',
    label: 'Morphological Box',
    icon: Grid3x3,
    category: 'analysis',
    link: '/morphbox',
    description: 'For each driver, generate 3–4 discrete future manifestations spanning the plausibility spectrum from optimistic to pessimistic.',
    methodology: 'Zwicky morphological analysis → LLM generates manifestation variants per driver → plausibility assessment (high/medium/low) → source chunk grounding → manifestation ordering by optimism gradient.',
    metricsFn: (d) => [
      { label: 'Drivers', value: d.cib_drivers },
      { label: 'Manifestations', value: d.manifestations },
      { label: 'Avg per Driver', value: d.manifestations && d.cib_drivers ? (d.manifestations / d.cib_drivers).toFixed(1) : '–' },
    ],
  },
  {
    id: 'cib',
    label: 'CIB Analysis',
    icon: ArrowLeftRight,
    category: 'analysis',
    link: '/cib',
    description: 'Assess pairwise cross-impact relationships between all drivers using a simulated expert panel, producing a scored interaction matrix.',
    methodology: 'Weimer-Jehle Cross-Impact Balance method → simulated Delphi panel (4 personas × LLM) → pairwise scoring (-3 to +3) → Monte Carlo aggregation (2000 samples) → influence/dependence profiling.',
    metricsFn: (d) => [
      { label: 'Driver Pairs', value: d.cib_pairs },
      { label: 'Personas', value: d.n_personas },
      { label: 'MC Samples', value: d.mc_samples?.toLocaleString() },
    ],
  },
  {
    id: 'consistency',
    label: 'Consistency Filter',
    icon: CheckCircle,
    category: 'analysis',
    link: '/cib',
    description: 'Apply the CIB consistency algorithm to filter the combinatorial configuration space down to internally coherent scenario seeds.',
    methodology: 'Full combinatorial space enumeration → CIB fixed-point iteration per configuration → consistency score = sum of supporting interactions → retain configurations exceeding threshold → deduplicate near-identical seeds.',
    metricsFn: (d) => [
      { label: 'Combinatorial Space', value: '268M+' },
      { label: 'Fixed Points', value: d.total_fixed_points },
      { label: 'Seeds Retained', value: d.consistency_seeds },
    ],
  },
  {
    id: 'scenarios',
    label: 'Scenario Generation',
    icon: FileText,
    category: 'output',
    link: '/scenarios',
    description: 'Transform each consistent configuration seed into a full narrative scenario with title, perspective, tensions, and evidence-grounded assumptions.',
    methodology: 'RAG retrieval per driver-manifestation pair → LLM narrative synthesis with structured output → scenario typing (evolutionary/disruptive/cautionary/wildcard) → key tensions extraction → source traceability chain.',
    metricsFn: (d) => [
      { label: 'Scenarios', value: d.scenarios },
      { label: 'From Seeds', value: d.consistency_seeds },
    ],
  },
  {
    id: 'mcda',
    label: 'MCDA Evaluation',
    icon: BarChart3,
    category: 'output',
    link: '/scenarios',
    description: 'Rank and prioritize scenarios using multi-criteria decision analysis with expert-derived weights and standardized scoring.',
    methodology: 'AHP pairwise comparison → criteria weights (impact, probability, actionability, time horizon, risk severity) → LLM-scored criteria per scenario (1–10) → TOPSIS ideal/anti-ideal distance → final closeness ranking.',
    metricsFn: (d) => [
      { label: 'Criteria', value: 5 },
      { label: 'Scenarios Ranked', value: d.scenarios },
    ],
  },
]

function StepCard({ step, metrics, index, isExpanded, onToggle, onNavigate, overviewData }) {
  const Icon = step.icon
  const color = PIPELINE_COLORS[step.category]
  const isLeft = index % 2 === 0

  return (
    <div className={`relative flex items-start gap-6 ${isLeft ? 'flex-row' : 'flex-row-reverse'} group`}>
      {/* Card */}
      <motion.div
        variants={fadeUp}
        className={`flex-1 ${isLeft ? 'text-right' : 'text-left'}`}
        style={{ maxWidth: 520 }}
      >
        <Card
          hover
          onClick={onToggle}
          className={`relative overflow-hidden transition-all duration-300 ${isExpanded ? 'ring-1' : ''}`}
          style={isExpanded ? { '--tw-ring-color': `${color}40` } : undefined}
        >
          {/* Category accent */}
          <div
            className={`absolute top-0 ${isLeft ? 'right-0' : 'left-0'} w-1 h-full`}
            style={{ background: color, opacity: isExpanded ? 0.8 : 0.3 }}
          />

          <div className={isLeft ? 'pr-3' : 'pl-3'}>
            {/* Header */}
            <div className={`flex items-center gap-3 mb-2 ${isLeft ? 'justify-end' : ''}`}>
              {!isLeft && (
                <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${color}20` }}>
                  <Icon size={18} style={{ color }} />
                </div>
              )}
              <div className={isLeft ? 'text-right' : ''}>
                <div className="text-[10px] font-medium uppercase tracking-wider mb-0.5" style={{ color }}>
                  Step {index + 1} · {step.category}
                </div>
                <h3 className="text-base font-bold text-white">{step.label}</h3>
              </div>
              {isLeft && (
                <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${color}20` }}>
                  <Icon size={18} style={{ color }} />
                </div>
              )}
            </div>

            {/* Description */}
            <p className={`text-xs text-zinc-400 leading-relaxed mb-3 ${isLeft ? 'text-right' : ''}`}>
              {step.description}
            </p>

            {/* Metrics */}
            {metrics?.length > 0 && (
              <div className={`flex gap-4 flex-wrap ${isLeft ? 'justify-end' : ''}`}>
                {metrics.map((m) => (
                  <div key={m.label} className={isLeft ? 'text-right' : ''}>
                    <div className="text-lg font-bold text-white">{m.value}</div>
                    <div className="text-[10px] text-zinc-500">{m.label}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Expanded methodology + visual */}
            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                  className="overflow-hidden"
                >
                  <div className="mt-4 pt-4 border-t border-white/5 space-y-4">
                    {/* Visual */}
                    <div className={`rounded-lg bg-zinc-900/50 border border-white/[0.04] p-3 ${isLeft ? 'text-left' : ''}`}>
                      <StepVisual stepId={step.id} data={overviewData} />
                    </div>

                    {/* Methodology text */}
                    <div>
                      <div className={`text-[10px] font-medium text-zinc-500 uppercase tracking-wider mb-1.5 ${isLeft ? 'text-right' : ''}`}>
                        Methodology
                      </div>
                      <p className={`text-xs text-zinc-300 leading-relaxed ${isLeft ? 'text-right' : ''}`}>
                        {step.methodology}
                      </p>
                    </div>

                    <button
                      onClick={(e) => { e.stopPropagation(); onNavigate(step.link) }}
                      className={`flex items-center gap-1.5 text-xs font-medium transition-colors hover:text-white ${isLeft ? 'ml-auto' : ''}`}
                      style={{ color }}
                    >
                      View Results <ExternalLink size={12} />
                    </button>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </Card>
      </motion.div>

      {/* Timeline node */}
      <div className="relative z-10 flex flex-col items-center shrink-0" style={{ width: 40 }}>
        <div
          className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 ${
            isExpanded ? 'scale-110' : 'group-hover:scale-105'
          }`}
          style={{
            borderColor: color,
            background: isExpanded ? `${color}30` : 'rgba(9,9,11,0.9)',
            boxShadow: isExpanded ? `0 0 20px ${color}40` : 'none',
          }}
        >
          <span className="text-xs font-bold" style={{ color }}>{index + 1}</span>
        </div>
      </div>

      {/* Spacer for opposite side */}
      <div className="flex-1" style={{ maxWidth: 520 }} />
    </div>
  )
}

export default function PipelinePage() {
  const { data, loading } = useApi('/api/overview')
  const [expandedStep, setExpandedStep] = useState(null)
  const navigate = useNavigate()

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <motion.div
      variants={staggerContainer}
      initial="enter"
      animate="center"
      className="max-w-6xl mx-auto px-8 py-8"
    >
      {/* Header */}
      <motion.div variants={fadeUp} className="text-center mb-12">
        <h1 className="text-3xl font-extrabold text-white mb-2">Pipeline Architecture</h1>
        <p className="text-sm text-zinc-400 max-w-xl mx-auto">
          Nine-stage AI pipeline transforming raw product documentation and regulatory intelligence
          into ranked, evidence-grounded technology scenarios for Horizon 2035.
        </p>
      </motion.div>

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-1/2 -translate-x-px top-0 bottom-0 w-[2px] bg-gradient-to-b from-blue-500/40 via-violet-500/30 to-emerald-500/40" />

        {/* Animated pulse dot */}
        <div className="absolute left-1/2 -translate-x-1 top-0 w-2 h-2 rounded-full bg-blue-400 animate-pulse-dot" style={{ animationDuration: '3s' }} />

        <div className="space-y-8">
          {STEPS.map((step, i) => {
            const metrics = step.metricsFn(data || {})
            return (
              <StepCard
                key={step.id}
                step={step}
                metrics={metrics}
                index={i}
                isExpanded={expandedStep === step.id}
                onToggle={() => setExpandedStep(expandedStep === step.id ? null : step.id)}
                onNavigate={navigate}
                overviewData={data}
              />
            )
          })}
        </div>

        {/* Bottom cap */}
        <div className="flex justify-center mt-6">
          <div className="w-3 h-3 rounded-full bg-emerald-500/60 ring-4 ring-emerald-500/10" />
        </div>
      </div>
    </motion.div>
  )
}
