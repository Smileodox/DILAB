import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { fadeUp } from '@/utils/animation'

function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0)
  const frameRef = useRef(null)

  useEffect(() => {
    if (!target) return
    const start = performance.now()
    function tick(now) {
      const elapsed = now - start
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(Math.round(eased * target))
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick)
      }
    }
    frameRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frameRef.current)
  }, [target, duration])

  return value
}

export default function MetricCard({ label, value, icon: Icon, suffix = '' }) {
  const count = useCountUp(value)

  return (
    <motion.div variants={fadeUp} className="glass rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">{label}</p>
          <p className="text-3xl font-extrabold text-white tracking-tight">
            {count.toLocaleString()}{suffix}
          </p>
        </div>
        {Icon && (
          <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <Icon size={20} className="text-blue-400" />
          </div>
        )}
      </div>
    </motion.div>
  )
}
