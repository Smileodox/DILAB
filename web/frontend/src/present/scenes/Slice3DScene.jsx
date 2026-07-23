import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Plotly from 'plotly.js-dist-min'
import { motion } from 'framer-motion'
import { Rotate3d } from 'lucide-react'
import SlideFrame from './SlideFrame'
import { archetypeColor, CONTINUUM_COLOR } from '@/utils/colors'
import { PLOTLY_CONFIG } from '@/utils/plotly'

export const STEPS = 2

/*
 * "Slicing the result space" — the 120-scenario field as a rotatable 3D point
 * cloud (PCA components 1-3), one trace per named archetype + a gray continuum.
 * Step 0: the cloud + legend. Step 1: a PC1 slab slicer — scenarios inside the
 * slab keep full color, the rest fade out, and a live panel shows who lives
 * there plus the slice's dominant factor recipe.
 */

const SLAB_FRACTION = 0.15 // slab width as share of the PC1 range

function hexToRgba(hex, alpha) {
  const h = hex.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const n = parseInt(full, 16)
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`
}

// Ordinal manifestation scale: optimistic (teal) -> middling (amber) -> pessimistic (red).
const RECIPE_ANCHORS = [
  [20, 184, 166],
  [245, 158, 11],
  [239, 68, 68],
]

function recipeColor(t) {
  const x = Math.min(Math.max(t, 0), 1) * (RECIPE_ANCHORS.length - 1)
  const i = Math.min(Math.floor(x), RECIPE_ANCHORS.length - 2)
  const f = x - i
  const [a, b] = [RECIPE_ANCHORS[i], RECIPE_ANCHORS[i + 1]]
  const c = a.map((v, k) => Math.round(v + (b[k] - v) * f))
  return `rgb(${c[0]},${c[1]},${c[2]})`
}

// Most frequent non-missing value; ties break toward the lower (more optimistic) index.
function modeOf(values) {
  const counts = new Map()
  let best = null
  let bestN = 0
  for (const v of values) {
    const n = (counts.get(v) ?? 0) + 1
    counts.set(v, n)
    if (n > bestN || (n === bestN && best != null && v < best)) {
      best = v
      bestN = n
    }
  }
  return best
}

const AXIS_NAMES = ['PC1', 'PC2', 'PC3']

export default function Slice3DScene({ data, step }) {
  const plotRef = useRef(null)
  const active = step >= 1

  // -- data prep ------------------------------------------------------------
  const points = useMemo(
    () =>
      (data?.field?.points ?? []).filter(
        (p) => Number.isFinite(p?.cx) && Number.isFinite(p?.cy) && Number.isFinite(p?.cz),
      ),
    [data],
  )

  // Cluster-space projection (UMAP of the ordinal matrix HDBSCAN clustered, fields
  // ox3/oy3/oz3) is the DEFAULT — it is the space where the archetypes were actually
  // found, matching Stations 6/7 and the Landscape tab. The toggle keeps PCA one click
  // away for Q&A ("the strategy map with interpretable axes").
  const [proj, setProj] = useState('ordinal')
  const hasOrdinal = useMemo(() => points.some((p) => Number.isFinite(p?.ox3)), [points])
  const ordinal = proj === 'ordinal' && hasOrdinal

  const allLabels = useMemo(() => points.map((p) => p.archetype), [points])
  const namedLabels = useMemo(
    () => [...new Set(allLabels)].filter((l) => l && l !== 'Continuum').sort(),
    [allLabels],
  )
  const labelOrder = useMemo(() => [...namedLabels, 'Continuum'], [namedLabels])

  const groups = useMemo(() => {
    const m = new Map(labelOrder.map((l) => [l, []]))
    for (const p of points) {
      const label = namedLabels.includes(p.archetype) ? p.archetype : 'Continuum'
      m.get(label).push(p)
    }
    return m
  }, [points, labelOrder, namedLabels])

  // Slab axis follows the projection: PC1 in the PCA view, UMAP-1 (ox3) in cluster
  // space — a PC1 slab would read as random scatter in cluster-space coordinates.
  const sliceAxis = ordinal ? 'ox3' : 'cx'
  const sliceAxisLabel = ordinal ? 'UMAP 1' : 'PC1'
  const [cxMin, cxMax] = useMemo(() => {
    if (!points.length) return [0, 1]
    const xs = points.map((p) => p[sliceAxis])
    return [Math.min(...xs), Math.max(...xs)]
  }, [points, sliceAxis])

  const slabW = (cxMax - cxMin) * SLAB_FRACTION
  const [sliceX, setSliceX] = useState(null)
  const sliceCenter = sliceX ?? (cxMin + cxMax) / 2

  // Drag ticks arrive faster than the WebGL scene re-renders its 6 traces —
  // coalesce them to at most one state update per animation frame.
  const pendingSlice = useRef(null)
  const sliceFrame = useRef(null)
  const setSliceXThrottled = useCallback((v) => {
    pendingSlice.current = v
    if (sliceFrame.current == null) {
      sliceFrame.current = requestAnimationFrame(() => {
        sliceFrame.current = null
        setSliceX(pendingSlice.current)
      })
    }
  }, [])
  useEffect(() => () => {
    if (sliceFrame.current != null) cancelAnimationFrame(sliceFrame.current)
  }, [])

  // Projection switch changes the axis range — recentre the slab.
  useEffect(() => {
    setSliceX(null)
  }, [ordinal])

  const sliced = useMemo(
    () => (active ? points.filter((p) => Math.abs(p[sliceAxis] - sliceCenter) <= slabW / 2) : []),
    [active, points, sliceAxis, sliceCenter, slabW],
  )
  const slicedIds = useMemo(() => new Set(sliced.map((p) => p.id)), [sliced])

  const sliceCounts = useMemo(() => {
    const m = new Map(labelOrder.map((l) => [l, 0]))
    for (const p of sliced) {
      const label = namedLabels.includes(p.archetype) ? p.archetype : 'Continuum'
      m.set(label, m.get(label) + 1)
    }
    return m
  }, [sliced, labelOrder, namedLabels])

  const sliceTitles = useMemo(
    () =>
      [...sliced]
        .sort(
          (a, b) =>
            (b.is_representative === true) - (a.is_representative === true) ||
            String(a.title ?? '').localeCompare(String(b.title ?? '')),
        )
        .slice(0, 6),
    [sliced],
  )

  // Modal manifestation index per driver across the sliced scenarios.
  const sliceRecipe = useMemo(() => {
    const drivers = data?.parcoords?.drivers ?? []
    const rows = data?.parcoords?.rows ?? []
    if (!sliced.length || !drivers.length || !rows.length) return null
    const valuesById = new Map(rows.map((r) => [r.scenario_id, r.values]))
    return drivers.map((d, di) => {
      const vals = []
      for (const p of sliced) {
        const v = valuesById.get(p.id)?.[di]
        if (v != null && v >= 0) vals.push(v)
      }
      const m = modeOf(vals)
      const len = d?.manifestations?.length ?? 0
      return {
        key: d?.driver_id ?? di,
        name: d?.name ?? `Factor ${di + 1}`,
        label: m != null ? d?.manifestations?.[m] : null,
        t: m != null && len > 1 ? m / (len - 1) : null,
      }
    })
  }, [data, sliced])

  // -- plot -----------------------------------------------------------------
  const traces = useMemo(
    () =>
      labelOrder.map((label) => {
        const pts = groups.get(label) ?? []
        const isCont = label === 'Continuum'
        const color = isCont ? CONTINUUM_COLOR : archetypeColor(label, allLabels)
        const baseAlpha = isCont ? (ordinal ? 0.15 : 0.35) : 0.9
        return {
          type: 'scatter3d',
          mode: 'markers',
          name: label,
          x: pts.map((p) => (ordinal ? p.ox3 : p.cx)),
          y: pts.map((p) => (ordinal ? p.oy3 : p.cy)),
          z: pts.map((p) => (ordinal ? p.oz3 : p.cz)),
          hovertext: pts.map((p) => `${p.title ?? p.id}<br>${label}`),
          hoverinfo: 'text',
          hoverlabel: {
            bgcolor: '#18181b',
            bordercolor: color,
            font: { color: '#e4e4e7', size: 12, family: 'Inter, system-ui, sans-serif' },
          },
          showlegend: false,
          marker: {
            size: isCont ? 3.5 : ordinal ? 6 : 5,
            // scatter3d has no per-point opacity array, so the fade lives in rgba colors
            color: pts.map((p) =>
              hexToRgba(color, active && !slicedIds.has(p.id) ? 0.06 : baseAlpha),
            ),
            line: { width: 0 },
          },
        }
      }),
    [labelOrder, groups, allLabels, active, slicedIds, ordinal],
  )

  const layout = useMemo(() => {
    const shares = data?.field?.pc_shares_3d ?? []
    const axis = (i) => ({
      title: {
        text: ordinal
          ? `UMAP ${i + 1} (ordinal)`
          : shares[i] != null ? `${AXIS_NAMES[i]} (${(shares[i] * 100).toFixed(1)}% var)` : AXIS_NAMES[i],
        font: { size: 11, color: '#71717a' },
      },
      showgrid: true,
      gridcolor: 'rgba(161,161,170,0.08)',
      showticklabels: false,
      zeroline: false,
      showspikes: false,
      showbackground: false,
    })
    return {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: '#a1a1aa', family: 'Inter, system-ui, sans-serif', size: 11 },
      margin: { t: 0, r: 0, b: 0, l: 0 },
      height: 560,
      showlegend: false,
      // keep the user's rotation/zoom across slider-driven re-renders,
      // but reset when the projection switches (different coordinate scales)
      uirevision: `slice3d-${ordinal ? 'ordinal' : 'pca'}`,
      scene: {
        bgcolor: 'rgba(0,0,0,0)',
        xaxis: axis(0),
        yaxis: axis(1),
        zaxis: axis(2),
        camera: { eye: { x: 1.7, y: 1.35, z: 0.85 } },
      },
    }
  }, [data, ordinal])

  useEffect(() => {
    const el = plotRef.current
    if (!el || !points.length) return
    Plotly.react(el, traces, layout, PLOTLY_CONFIG)
  }, [traces, layout, points.length])

  useEffect(() => {
    const el = plotRef.current
    return () => {
      if (el) Plotly.purge(el)
    }
  }, [])

  // -- render ---------------------------------------------------------------
  return (
    <SlideFrame
      kicker="The result space · 3D"
      title={ordinal
        ? `${points.length || 120} futures, seen where the archetypes were found`
        : `${points.length || 120} futures, three principal axes`}
      subtitle={ordinal
        ? 'Every consistent scenario, placed by UMAP over its ordinal factor recipe: five archetype islands and the honest continuum between them.'
        : 'Every consistent scenario, placed by PCA over its full factor recipe: five archetype clusters and the continuum between them.'}
      wide
    >
      <div className="h-full flex flex-col min-h-0">
        <div className="flex-1 min-h-0 flex gap-6">
          {/* LEFT: the 3D cloud */}
          <div className="w-[62%] glass rounded-2xl p-2 min-h-0 relative">
            {hasOrdinal && (
              <div className="absolute top-3 right-3 z-10 flex gap-1">
                {[['pca', 'PCA'], ['ordinal', 'Cluster space']].map(([m, label]) => (
                  <button
                    key={m}
                    onClick={() => setProj(m)}
                    className={`px-2 py-1 rounded text-[10px] font-medium transition ${
                      proj === m
                        ? 'bg-violet-600 text-white'
                        : 'bg-zinc-800/80 text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
            {points.length ? (
              <div ref={plotRef} className="w-full" style={{ height: 560 }} />
            ) : (
              <div className="h-full flex items-center justify-center text-sm text-zinc-500">
                No 3D field data in this bundle.
              </div>
            )}
          </div>

          {/* RIGHT: legend (step 0) / slicer (step 1) */}
          <div className="w-[38%] min-h-0 flex flex-col gap-3">
            {!active && (
              <>
                <div className="space-y-2.5">
                  {labelOrder.map((label, i) => {
                    const color = label === 'Continuum' ? CONTINUUM_COLOR : archetypeColor(label, allLabels)
                    return (
                      <motion.div
                        key={label}
                        initial={{ opacity: 0, x: 16 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ duration: 0.35, delay: 0.15 + i * 0.07 }}
                        className="glass rounded-xl px-4 py-3 flex items-center gap-3"
                      >
                        <span className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
                        <span className="text-sm font-medium text-zinc-200 flex-1 truncate">{label}</span>
                        <span className="text-sm font-semibold tabular-nums text-zinc-400">
                          {(groups.get(label) ?? []).length}
                        </span>
                      </motion.div>
                    )
                  })}
                </div>
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.7 }}
                  className="mt-2 flex items-center gap-2 text-sm text-zinc-500"
                >
                  <Rotate3d size={16} className="shrink-0" />
                  Drag to rotate · scroll to zoom
                </motion.div>
              </>
            )}

            {active && (
              <>
                {/* Slicer */}
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35 }}
                  className="glass rounded-xl px-4 py-3 shrink-0"
                >
                  <div className="flex items-baseline justify-between mb-2">
                    <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                      Slice along {sliceAxisLabel}
                    </span>
                    <span className="text-xs tabular-nums text-zinc-500">
                      {(sliceCenter - slabW / 2).toFixed(2)} … {(sliceCenter + slabW / 2).toFixed(2)}
                    </span>
                  </div>
                  <input
                    type="range"
                    min={cxMin}
                    max={cxMax}
                    step={(cxMax - cxMin) / 200 || 0.01}
                    value={sliceCenter}
                    onChange={(e) => setSliceXThrottled(Number(e.target.value))}
                    onPointerUp={(e) => e.currentTarget.blur()}
                    className="w-full accent-blue-500 cursor-pointer"
                    aria-label={`${sliceAxisLabel} slice position`}
                  />
                  <div className="flex justify-between text-[10px] text-zinc-600 tabular-nums">
                    <span>{cxMin.toFixed(1)}</span>
                    <span>{cxMax.toFixed(1)}</span>
                  </div>
                </motion.div>

                {/* Live slice panel */}
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35, delay: 0.1 }}
                  className="glass rounded-xl px-4 py-3 flex-1 min-h-0 flex flex-col gap-3 overflow-hidden"
                >
                  <div className="flex items-baseline gap-2 shrink-0">
                    <span className="text-3xl font-extrabold tabular-nums text-white">{sliced.length}</span>
                    <span className="text-sm text-zinc-400">
                      scenario{sliced.length === 1 ? '' : 's'} in slice
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-x-3 gap-y-1 shrink-0">
                    {labelOrder.map((label) => {
                      const color = label === 'Continuum' ? CONTINUUM_COLOR : archetypeColor(label, allLabels)
                      const n = sliceCounts.get(label) ?? 0
                      return (
                        <div
                          key={label}
                          className={`flex items-center gap-1.5 text-xs ${n ? 'text-zinc-300' : 'text-zinc-600'}`}
                        >
                          <span
                            className="w-2 h-2 rounded-full shrink-0"
                            style={{ background: color, opacity: n ? 1 : 0.35 }}
                          />
                          <span className="truncate flex-1">{label}</span>
                          <span className="tabular-nums font-semibold">{n}</span>
                        </div>
                      )
                    })}
                  </div>

                  {sliceTitles.length > 0 && (
                    <div className="space-y-1 min-h-0 overflow-hidden shrink">
                      {sliceTitles.map((p) => (
                        <p key={p.id} className="text-xs text-zinc-400 truncate">
                          <span
                            className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle"
                            style={{
                              background:
                                p.archetype === 'Continuum'
                                  ? CONTINUUM_COLOR
                                  : archetypeColor(p.archetype, allLabels),
                            }}
                          />
                          {p.title ?? p.id}
                        </p>
                      ))}
                      {sliced.length > sliceTitles.length && (
                        <p className="text-[10px] text-zinc-600">
                          + {sliced.length - sliceTitles.length} more
                        </p>
                      )}
                    </div>
                  )}

                  {sliceRecipe && (
                    <div className="shrink-0 mt-auto">
                      <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-1.5">
                        Dominant recipe · modal state per factor
                      </p>
                      <div className="flex gap-1 flex-wrap">
                        {sliceRecipe.map((r) => (
                          <span
                            key={r.key}
                            title={r.label ? `${r.name} · ${r.label}` : r.name}
                            className="w-4 h-4 rounded-[3px] shrink-0"
                            style={{
                              background: r.t != null ? recipeColor(r.t) : 'rgba(63,63,70,0.6)',
                            }}
                          />
                        ))}
                      </div>
                      <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-zinc-600">
                        <span className="w-2 h-2 rounded-sm" style={{ background: recipeColor(0) }} />
                        optimistic
                        <span className="w-2 h-2 rounded-sm ml-2" style={{ background: recipeColor(1) }} />
                        pessimistic
                      </div>
                    </div>
                  )}
                </motion.div>
              </>
            )}
          </div>
        </div>

        {/* Bottom message line */}
        {active && (
          <motion.p
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.35 }}
            className="mt-4 shrink-0 text-center text-base md:text-lg text-zinc-400"
          >
            The continuum is not noise: it is{' '}
            <span className="text-zinc-200 font-medium">the honest in-between</span> where futures blend.
          </motion.p>
        )}
      </div>
    </SlideFrame>
  )
}
