import { useState, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { OriginBadge, TypeBadge } from '@/components/ui/Badge'
import { PLAUSIBILITY_COLORS } from '@/utils/colors'

function ManifestationCell({ manifestation, highlighted, dimmed }) {
  // Tooltip rendered through a portal: an absolutely-positioned child would be
  // clipped by the grid's overflow-x-auto container.
  const [tooltip, setTooltip] = useState(null)
  const cellRef = useRef(null)
  const level = (manifestation.plausibility || 'medium').toLowerCase()
  const borderColor = PLAUSIBILITY_COLORS[level]

  const openTooltip = () => {
    const r = cellRef.current?.getBoundingClientRect()
    if (!r) return
    const openUp = r.bottom + 300 > window.innerHeight
    setTooltip({
      left: Math.min(r.left, window.innerWidth - 340),
      ...(openUp ? { bottom: window.innerHeight - r.top + 8 } : { top: r.bottom + 8 }),
    })
  }

  return (
    <div
      ref={cellRef}
      className="relative flex-shrink-0 w-52 rounded-lg p-3 transition-all duration-200"
      style={{
        background: highlighted
          ? 'rgba(255,255,255,0.06)'
          : 'rgba(255,255,255,0.02)',
        borderLeft: `3px solid ${borderColor}`,
        border: highlighted
          ? `1px solid rgba(255,255,255,0.2)`
          : '1px solid rgba(255,255,255,0.04)',
        borderLeftWidth: 3,
        borderLeftColor: borderColor,
        opacity: dimmed ? 0.3 : 1,
        boxShadow: highlighted
          ? `0 0 16px ${borderColor}20, 0 0 4px ${borderColor}10`
          : 'none',
      }}
      onMouseEnter={openTooltip}
      onMouseLeave={() => setTooltip(null)}
    >
      <div className="text-xs font-semibold text-zinc-100 leading-tight mb-1">
        {manifestation.label}
      </div>
      {manifestation.description && (
        <div className="text-[11px] text-zinc-400 leading-snug line-clamp-2">
          {manifestation.description}
        </div>
      )}
      <div className="mt-1.5 flex items-center gap-1.5">
        <div
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: borderColor }}
        />
        <span className="text-[10px] text-zinc-500 capitalize">{level}</span>
      </div>

      {/* Full description tooltip */}
      {tooltip && manifestation.description && createPortal(
        <div
          className="fixed z-[100] glass-solid rounded-md px-3 py-2 text-xs text-zinc-300 leading-relaxed pointer-events-none whitespace-normal shadow-xl border border-white/10"
          style={{ ...tooltip, maxWidth: 330, maxHeight: 280, overflowY: 'auto' }}
        >
          <div className="font-semibold text-zinc-100 mb-1">
            {manifestation.label}
          </div>
          {manifestation.description}
        </div>,
        document.body,
      )}
    </div>
  )
}

export default function MorphGrid({ drivers, scenarios }) {
  const [selectedScenarioId, setSelectedScenarioId] = useState(null)

  const selectedScenario = useMemo(
    () =>
      scenarios?.find((s) => s.id === selectedScenarioId) || null,
    [scenarios, selectedScenarioId],
  )

  // Build a lookup: driver_id -> manifestation_id for the selected scenario
  const highlightMap = useMemo(() => {
    if (!selectedScenario) return null
    const map = {}
    for (const assumption of selectedScenario.assumptions || []) {
      map[assumption.driver_id] = assumption.manifestation_id
    }
    return map
  }, [selectedScenario])

  const hasOverlay = highlightMap !== null
  const maxManifestations = useMemo(
    () => Math.max(...(drivers || []).map((d) => d.manifestations?.length || 0), 0),
    [drivers],
  )

  if (!drivers || drivers.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-zinc-500 text-sm">
        No morphological data available
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Scenario overlay controls */}
      {scenarios && scenarios.length > 0 && (
        <div className="flex items-center gap-3 flex-wrap">
          <select
            className="glass rounded-lg px-3 py-1.5 text-sm text-zinc-200 bg-transparent outline-none cursor-pointer min-w-[200px]"
            value={selectedScenarioId || ''}
            onChange={(e) =>
              setSelectedScenarioId(e.target.value || null)
            }
          >
            <option value="" className="bg-zinc-900">
              No scenario overlay
            </option>
            {scenarios.map((s) => (
              <option key={s.id} value={s.id} className="bg-zinc-900">
                {s.title}
              </option>
            ))}
          </select>

          {selectedScenario && (
            <div className="flex items-center gap-2">
              <TypeBadge type={selectedScenario.type} />
              <span className="text-xs text-zinc-400">{selectedScenario.title}</span>
            </div>
          )}
        </div>
      )}

      {/* Plausibility legend */}
      <div className="flex items-center gap-4 text-xs text-zinc-400">
        <span className="text-zinc-500">Plausibility:</span>
        {Object.entries(PLAUSIBILITY_COLORS).map(([level, color]) => (
          <span key={level} className="flex items-center gap-1.5 capitalize">
            <span className="w-2 h-2 rounded-full" style={{ background: color }} />
            {level}
          </span>
        ))}
      </div>

      {/* Scrollable grid */}
      <div className="glass rounded-xl overflow-x-auto">
        <table className="w-full border-collapse" style={{ minWidth: maxManifestations * 220 + 200 }}>
          <thead>
            <tr>
              <th className="sticky left-0 z-10 glass-solid text-left px-4 py-3 text-xs font-semibold text-zinc-400 uppercase tracking-wider w-48 min-w-[192px]">
                Driver
              </th>
              {Array.from({ length: maxManifestations }, (_, i) => (
                <th
                  key={i}
                  className="text-left px-3 py-3 text-[10px] font-medium text-zinc-500 uppercase tracking-wider"
                  style={{ minWidth: 208 }}
                >
                  Manifestation {i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {drivers.map((driver) => {
              const highlightedManifId = highlightMap?.[driver.id]

              return (
                <tr
                  key={driver.id}
                  className="border-t border-white/[0.04] hover:bg-white/[0.02] transition-colors"
                >
                  {/* Sticky driver name column */}
                  <td className="sticky left-0 z-10 glass-solid px-4 py-3 align-top">
                    <div className="flex flex-col gap-1.5">
                      <span className="text-sm font-semibold text-zinc-100 leading-tight">
                        {driver.name}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <OriginBadge origin={driver.origin} />
                        {driver.confidence && (
                          <span className="text-[10px] text-zinc-500 capitalize">
                            {driver.confidence}
                          </span>
                        )}
                      </div>
                    </div>
                  </td>

                  {/* Manifestation cells */}
                  {driver.manifestations?.map((manif) => {
                    const isHighlighted = hasOverlay && highlightedManifId === manif.id
                    const isDimmed = hasOverlay && highlightedManifId !== manif.id

                    return (
                      <td key={manif.id} className="px-3 py-3 align-top">
                        <ManifestationCell
                          manifestation={manif}
                          highlighted={isHighlighted}
                          dimmed={isDimmed}
                        />
                      </td>
                    )
                  })}

                  {/* Fill empty cells */}
                  {Array.from(
                    { length: maxManifestations - (driver.manifestations?.length || 0) },
                    (_, i) => (
                      <td key={`empty-${i}`} className="px-3 py-3" />
                    ),
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
