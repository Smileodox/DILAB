import { motion } from 'framer-motion'

/*
 * Shared slide chrome: kicker (small colored label), big title, optional subtitle,
 * then a content region that fills the rest. Keeps every scene visually consistent
 * and beamer-legible (large type, generous margins).
 */
export default function SlideFrame({ kicker, kickerColor = '#3b82f6', title, subtitle, children, wide = false }) {
  return (
    <div className={`h-full flex flex-col ${wide ? 'max-w-[1500px]' : 'max-w-6xl'} mx-auto px-12 pt-14 pb-16`}>
      <div className="mb-6 shrink-0">
        {kicker && (
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="text-sm font-semibold uppercase tracking-[0.2em] mb-3"
            style={{ color: kickerColor }}
          >
            {kicker}
          </motion.p>
        )}
        <motion.h1
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.05 }}
          className="text-4xl md:text-5xl font-extrabold text-white tracking-tight leading-tight"
        >
          {title}
        </motion.h1>
        {subtitle && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.45, delay: 0.15 }}
            className="mt-3 text-lg text-zinc-400 max-w-3xl"
          >
            {subtitle}
          </motion.p>
        )}
      </div>
      <div className="flex-1 min-h-0">{children}</div>
    </div>
  )
}
