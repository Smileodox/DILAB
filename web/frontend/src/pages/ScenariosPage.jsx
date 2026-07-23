import { useState, useEffect, useCallback } from 'react'
import { AnimatePresence } from 'framer-motion'
import axios from 'axios'
import { useKbApi, useKb } from '@/context/KbContext'
import LoadError from '@/components/ui/LoadError'
import ScenarioList from '@/components/scenarios/ScenarioList'
import ScenarioDetail from '@/components/scenarios/ScenarioDetail'
import NarrativeView from '@/components/scenarios/NarrativeView'
import EvidencePanel from '@/components/scenarios/EvidencePanel'

export default function ScenariosPage() {
  const { data, loading, error } = useKbApi('/api/scenarios')
  const scenarios = Array.isArray(data) ? data : null
  const { kb } = useKb()
  const [selectedId, setSelectedId] = useState(null)
  const [showNarrative, setShowNarrative] = useState(false)
  const [showEvidence, setShowEvidence] = useState(false)
  const [traceData, setTraceData] = useState(null)
  const [traceLoading, setTraceLoading] = useState(false)

  // Select first scenario once data arrives
  useEffect(() => {
    if (scenarios?.length && !selectedId) {
      setSelectedId(scenarios[0].id)
    }
  }, [scenarios, selectedId])

  const selected = scenarios?.find((s) => s.id === selectedId) || null

  const handleSelect = useCallback((id) => {
    setSelectedId(id)
    setShowNarrative(false)
    setShowEvidence(false)
    setTraceData(null)
  }, [])

  const handleShowNarrative = useCallback(() => {
    setShowEvidence(false)
    setShowNarrative(true)
  }, [])

  const handleShowEvidence = useCallback(() => {
    setShowNarrative(false)
    setShowEvidence(true)
    if (!selectedId) return

    setTraceLoading(true)
    axios
      .get(`/api/traceability/${selectedId}?kb=${kb}`)
      .then((res) => setTraceData(res.data))
      .catch(() => setTraceData(null))
      .finally(() => setTraceLoading(false))
  }, [selectedId, kb])

  const handleClosePanel = useCallback(() => {
    setShowNarrative(false)
    setShowEvidence(false)
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[calc(100vh-44px)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error || !scenarios) {
    return <LoadError title="Scenarios" />
  }

  return (
    <div className="h-[calc(100vh-44px)] flex">
      {/* Left zone — scenario list */}
      <div className="w-80 shrink-0 border-r border-white/5 overflow-hidden">
        <ScenarioList
          scenarios={scenarios || []}
          selectedId={selectedId}
          onSelect={handleSelect}
        />
      </div>

      {/* Center zone — detail */}
      <div className="flex-1 overflow-y-auto p-8">
        <ScenarioDetail
          scenario={selected}
          onShowNarrative={handleShowNarrative}
          onShowEvidence={handleShowEvidence}
        />
      </div>

      {/* Right zone — slide-in panels */}
      <AnimatePresence>
        {showNarrative && selected && (
          <NarrativeView
            key="narrative"
            scenario={selected}
            onClose={handleClosePanel}
          />
        )}
        {showEvidence && (
          <EvidencePanel
            key="evidence"
            traceability={traceData}
            loading={traceLoading}
            onClose={handleClosePanel}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
