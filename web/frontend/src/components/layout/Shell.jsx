import { useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useLocation } from 'react-router-dom'
import SideNav from './SideNav'
import TopBar from './TopBar'
import { usePresentationMode } from '@/hooks/usePresentationMode'
import { pageVariants } from '@/utils/animation'

export default function Shell({ children }) {
  const location = useLocation()
  const { currentIndex, totalPages } = usePresentationMode()

  // Every page should open at its headline, not wherever the last page was scrolled.
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-zinc-950 bg-mesh">
      <SideNav />
      <div className="ml-16">
        <TopBar />
        <AnimatePresence mode="popLayout">
          <motion.main
            key={location.pathname}
            variants={pageVariants}
            initial="enter"
            animate="center"
            exit="exit"
            className="min-h-[calc(100vh-44px)]"
          >
            {children}
          </motion.main>
        </AnimatePresence>
      </div>

      {currentIndex >= 0 && (
        <div className="fixed bottom-4 right-4 flex gap-1.5 z-40">
          {Array.from({ length: totalPages }).map((_, i) => (
            <div
              key={i}
              className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                i === currentIndex
                  ? 'bg-blue-400 scale-125'
                  : 'bg-zinc-700'
              }`}
            />
          ))}
        </div>
      )}
    </div>
  )
}
