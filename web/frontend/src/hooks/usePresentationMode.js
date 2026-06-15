import { useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'

const PAGE_ORDER = [
  '/',
  '/pipeline',
  '/drivers',
  '/bom',
  '/morphbox',
  '/cib',
  '/scenarios',
  '/landscape',
  '/embeddings',
  '/strategy',
]

export function usePresentationMode() {
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    function handleKey(e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return

      const idx = PAGE_ORDER.indexOf(location.pathname)
      if (idx === -1) return

      if (e.key === 'ArrowRight' && idx < PAGE_ORDER.length - 1) {
        e.preventDefault()
        navigate(PAGE_ORDER[idx + 1])
      } else if (e.key === 'ArrowLeft' && idx > 0) {
        e.preventDefault()
        navigate(PAGE_ORDER[idx - 1])
      }
    }

    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [navigate, location.pathname])

  const currentIndex = PAGE_ORDER.indexOf(location.pathname)
  return { currentIndex, totalPages: PAGE_ORDER.length, pages: PAGE_ORDER }
}
