import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'
import { useApi } from '@/hooks/useApi'
import { SCENES } from './scenes'

/*
 * Fullscreen presentation mode. One /api/present bundle, a linear deck of scenes,
 * each scene may have several reveal steps.
 *
 * Keys: → / PageDown / Space = next step (then next scene) · ← / PageUp = back ·
 *       Esc = exit to dashboard · Home = first scene.
 *
 * Scene contract: function Scene({ data, step }) — `data` is the whole bundle,
 * `step` counts 0..steps-1 within the scene. Register in ./scenes/index.js as
 * { id, title, steps, component }.
 */
export default function PresentShell() {
  const { data, loading, error } = useApi('/api/present')
  const navigate = useNavigate()
  const [pos, setPos] = useState({ scene: 0, step: 0 })

  const advance = useCallback((dir) => {
    setPos(({ scene, step }) => {
      const cur = SCENES[scene]
      if (dir > 0) {
        if (step < cur.steps - 1) return { scene, step: step + 1 }
        if (scene < SCENES.length - 1) return { scene: scene + 1, step: 0 }
        return { scene, step }
      }
      if (step > 0) return { scene, step: step - 1 }
      if (scene > 0) return { scene: scene - 1, step: SCENES[scene - 1].steps - 1 }
      return { scene, step }
    })
  }, [])

  useEffect(() => {
    function onKey(e) {
      // Escape must always work — even while a slider/input holds focus.
      if (e.key === 'Escape') {
        navigate('/')
        return
      }
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return
      // Enter would re-trigger whatever button was clicked last (progress dot, exit X).
      if (e.key === 'Enter') {
        e.preventDefault()
        return
      }
      if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') {
        e.preventDefault()
        advance(1)
      } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        e.preventDefault()
        advance(-1)
      } else if (e.key === 'Home') {
        setPos({ scene: 0, step: 0 })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [advance, navigate])

  if (loading) {
    return (
      <div className="fixed inset-0 bg-zinc-950 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !data || data.unavailable) {
    return (
      <div className="fixed inset-0 bg-zinc-950 flex items-center justify-center">
        <div className="text-center">
          <p className="text-zinc-300 mb-4">Presentation data unavailable. Is the backend running?</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-medium text-white"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  const { scene, step } = pos
  const Active = SCENES[scene].component

  return (
    <div className="fixed inset-0 bg-zinc-950 bg-mesh overflow-hidden select-none">
      {/* Scene */}
      <AnimatePresence mode="wait">
        <motion.div
          key={SCENES[scene].id}
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -24 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          className="absolute inset-0 overflow-y-auto"
        >
          <Active data={data} step={step} />
        </motion.div>
      </AnimatePresence>

      {/* Exit */}
      <button
        onClick={() => navigate('/')}
        className="absolute top-5 right-5 z-50 p-2 rounded-lg text-zinc-600 hover:text-zinc-300 hover:bg-white/[0.05] transition-colors"
        title="Exit (Esc)"
      >
        <X size={18} />
      </button>

      {/* Progress: one dot per scene, step ticks under the active dot */}
      <div className="absolute bottom-5 left-1/2 -translate-x-1/2 z-50 flex flex-col items-center gap-1.5">
        <div className="flex gap-2">
          {SCENES.map((s, i) => (
            <button
              key={s.id}
              onClick={(e) => {
                setPos({ scene: i, step: 0 })
                e.currentTarget.blur()
              }}
              title={s.title}
              className={`w-2 h-2 rounded-full transition-all duration-300 ${
                i === scene ? 'bg-blue-400 scale-125' : i < scene ? 'bg-zinc-500' : 'bg-zinc-800'
              }`}
            />
          ))}
        </div>
        {SCENES[scene].steps > 1 && (
          <div className="flex gap-1">
            {Array.from({ length: SCENES[scene].steps }).map((_, i) => (
              <div
                key={i}
                className={`w-1 h-1 rounded-full ${i <= step ? 'bg-blue-500/70' : 'bg-zinc-800'}`}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
