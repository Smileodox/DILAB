import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import SlideFrame from './SlideFrame'

export const STEPS = 2

function useCountUp(target, active, duration = 1400) {
  const [value, setValue] = useState(0)
  useEffect(() => {
    if (!active || !target) return
    let frame
    const start = performance.now()
    function tick(now) {
      const p = Math.min((now - start) / duration, 1)
      setValue(Math.round((1 - Math.pow(1 - p, 3)) * target))
      if (p < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, active, duration])
  return value
}

function ChainStop({ value, label, sub, color, active, delay }) {
  const n = useCountUp(value, active)
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={active ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
      transition={{ duration: 0.5, delay }}
      className="flex flex-col items-center text-center"
    >
      <span className="text-4xl md:text-5xl font-extrabold tabular-nums tracking-tight" style={{ color }}>
        {n.toLocaleString('en-US')}
      </span>
      <span className="mt-2 text-sm font-semibold text-zinc-200">{label}</span>
      {sub && <span className="mt-0.5 text-xs text-zinc-500">{sub}</span>}
    </motion.div>
  )
}

export default function HookScene({ data, step }) {
  const m = data.meta
  const stops = [
    { value: m.sources, label: 'sources', sub: `${m.chunks.toLocaleString('en-US')} text chunks`, color: '#3b82f6' },
    { value: m.cib_drivers, label: 'key factors', sub: `selected from ${m.drivers_total}`, color: '#60a5fa' },
    { value: m.combinations, label: 'possible futures', sub: '4 states per factor', color: '#8b5cf6' },
    { value: m.scenarios, label: 'consistent scenarios', sub: `${m.mc_samples.toLocaleString('en-US')} MC samples`, color: '#a78bfa' },
    { value: m.archetypes, label: 'named archetypes', sub: '+ honest continuum', color: '#10b981' },
  ]

  return (
    <SlideFrame
      kicker="R&S Horizon 35 · Technology Foresight"
      title="How do you see 2035 coming, before your competitors do?"
      subtitle="An AI pipeline that turns a pile of documents into a navigable map of futures. Every step traceable, every claim tested against chance."
      wide
    >
      <div className="h-full flex items-center">
        <div className="w-full flex items-center justify-between gap-2">
          {stops.map((s, i) => (
            <div key={s.label} className="flex items-center gap-2 flex-1 justify-center">
              <ChainStop {...s} active={step >= 1} delay={i * 0.35} />
              {i < stops.length - 1 && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={step >= 1 ? { opacity: 0.5 } : { opacity: 0 }}
                  transition={{ delay: i * 0.35 + 0.3 }}
                >
                  <ArrowRight size={22} className="text-zinc-600 shrink-0" />
                </motion.div>
              )}
            </div>
          ))}
        </div>
      </div>
    </SlideFrame>
  )
}
