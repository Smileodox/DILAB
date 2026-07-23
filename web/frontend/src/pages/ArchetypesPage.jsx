import { motion } from 'framer-motion'
import { Boxes, Layers, Waves, Crosshair } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import { useKb } from '@/context/KbContext'
import Card from '@/components/ui/Card'
import { archetypeColor } from '@/utils/colors'
import { staggerContainer, fadeUp, fadeIn } from '@/utils/animation'

const truncate = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

// Fractional stat tile (matches LandscapePage's StructStat convention).
function Stat({ label, value, sub, icon: Icon, warn }) {
  return (
    <div className="glass rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">{label}</p>
          <p className={`text-3xl font-extrabold tracking-tight ${warn ? 'text-amber-300' : 'text-white'}`}>
            {value ?? '—'}
          </p>
          {sub && <p className="text-xs text-zinc-500 mt-1">{sub}</p>}
        </div>
        {Icon && (
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <Icon size={20} className="text-blue-400" />
          </div>
        )}
      </div>
    </div>
  )
}

export default function ArchetypesPage() {
  const { kb } = useKb()
  const { data, loading } = useApi(`/api/archetypes?kb=${kb}`)

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const arch = data?.archetypes || []
  if (!data || data.unavailable || arch.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-8 py-8">
        <h1 className="text-2xl font-bold text-white mb-2">Scenario Archetypes</h1>
        <p className="text-sm text-zinc-400">
          No archetypes for this knowledge base yet — run the pipeline's archetype-extraction stage.
        </p>
      </div>
    )
  }

  const maxSize = Math.max(...arch.map((a) => a.size), 1)
  const pct = (v) => (v == null ? '—' : `${(v * 100).toFixed(0)}%`)
  // Same label→color mapping as the Landscape scatter, so the pages tell one story.
  const allLabels = arch.map((a) => a.label)

  return (
    <motion.div variants={staggerContainer} initial="enter" animate="center"
      className="max-w-7xl mx-auto px-8 py-8 space-y-8">
      <motion.div variants={fadeUp}>
        <h1 className="text-2xl font-bold text-white">Scenario Archetypes</h1>
        <p className="text-sm text-zinc-400 mt-1 max-w-3xl">
          Dense-core clusters of the combinatorial field, isolated by HDBSCAN on the ordinal driver
          encoding and auto-named from the states that distinguish each group. The rest of the field is
          an honest continuum — these archetypes describe the core, not the whole space.
        </p>
      </motion.div>

      <motion.div variants={staggerContainer} className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Stat label="Archetypes" value={data.n_archetypes ?? arch.length} icon={Boxes} />
        <Stat label="Continuum halo" value={pct(data.noise_fraction)}
          sub={`${data.continuum?.n_noise}/${data.n_configs} configs`} icon={Waves}
          warn={data.noise_fraction > 0.5} />
        <Stat label="Core silhouette" value={data.hdbscan_silhouette?.toFixed(2) ?? '—'}
          sub="dense subset only" icon={Layers} />
        {data.n_fixed_points > 0 ? (
          <Stat label="Attractors" value={data.n_fixed_points}
            sub="CIB fixed points among sampled configs" icon={Crosshair} />
        ) : (
          <Stat label="Sampled configs" value={data.n_configs ?? '—'}
            sub="soft-CIB field sample" icon={Crosshair} />
        )}
      </motion.div>

      <motion.div variants={staggerContainer} className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {arch.map((a) => {
          const color = archetypeColor(a.label, allLabels)
          return (
          <motion.div key={a.id} variants={fadeUp}>
            <Card>
              <div className="flex items-start justify-between gap-3 mb-2">
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
                  {a.label}
                </h3>
                {a.contains_attractor && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs
                    bg-emerald-500/15 text-emerald-300 shrink-0">
                    <Crosshair size={11} /> attractor
                  </span>
                )}
              </div>
              <p className="text-sm text-zinc-300 mb-3">{a.description}</p>
              <div className="mb-3">
                <div className="flex justify-between text-xs text-zinc-500 mb-1">
                  <span>{a.size} scenarios</span>
                </div>
                <div className="h-1.5 rounded-full bg-white/5 overflow-hidden">
                  <div className="h-full" style={{ width: `${(100 * a.size) / maxSize}%`, background: color, opacity: 0.7 }} />
                </div>
              </div>
              {/* Top distinguishing driver states, with the lift printed — the quantitative
                  "what makes this archetype different" evidence. */}
              <div className="flex flex-wrap gap-1.5">
                {(a.distinguishing_drivers || []).slice(0, 3).map((d, i) => (
                  <span key={i} title={`${d.driver}: ${d.manifestation} (lift +${Math.round(d.lift * 100)}pp vs. field)`}
                    className="inline-flex items-center px-2 py-0.5 rounded text-[11px]
                      bg-white/[0.04] text-zinc-300 border border-white/[0.06]">
                    <span className="text-zinc-500">{truncate(d.driver, 24)}:</span>&nbsp;{truncate(d.manifestation, 32)}
                    <span className="text-emerald-400 ml-1.5 font-medium">+{Math.round(d.lift * 100)}pp</span>
                  </span>
                ))}
              </div>
            </Card>
          </motion.div>
          )
        })}
      </motion.div>

      {data.continuum?.note && (
        <motion.div variants={fadeIn}
          className="flex items-start gap-3 rounded-lg border border-white/[0.06] bg-white/[0.03] px-4 py-3">
          <Waves className="w-4 h-4 text-zinc-400 mt-0.5 shrink-0" />
          <p className="text-sm text-zinc-400">{data.continuum.note}</p>
        </motion.div>
      )}
    </motion.div>
  )
}
