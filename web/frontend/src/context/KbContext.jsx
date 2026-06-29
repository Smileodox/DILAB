import { createContext, useContext, useState } from 'react'
import { useApi } from '@/hooks/useApi'

const KbContext = createContext(null)

/**
 * Global knowledge-base selection. Loads the available KBs (+ their available methods and
 * page-views) once, holds the active KB, and exposes it app-wide so every page fetches the
 * selected KB's data.
 */
export function KbProvider({ children }) {
  const { data: kbsData } = useApi('/api/kbs')
  const kbs = kbsData || []
  const [kb, setKb] = useState('spectrum')
  return (
    <KbContext.Provider value={{ kb, setKb, kbs }}>
      {children}
    </KbContext.Provider>
  )
}

export function useKb() {
  return useContext(KbContext) || { kb: 'spectrum', setKb: () => {}, kbs: [] }
}

/** Like useApi, but transparently scopes the request to the active KB (?kb=...). */
export function useKbApi(path) {
  const { kb } = useKb()
  const url = path ? `${path}${path.includes('?') ? '&' : '?'}kb=${encodeURIComponent(kb)}` : path
  return useApi(url)
}
