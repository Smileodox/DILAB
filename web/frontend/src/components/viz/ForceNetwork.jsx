import { useRef, useEffect, useState, useCallback } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force'
import { scaleLinear } from 'd3-scale'
import { color as d3color } from 'd3-color'
import { CIB_QUADRANT_COLORS } from '@/utils/colors'

function getQuadrant(inf, dep, medInf, medDep) {
  if (inf >= medInf && dep >= medDep) return 'critical'
  if (inf >= medInf && dep < medDep) return 'enabler'
  if (inf < medInf && dep >= medDep) return 'dependent'
  return 'isolated'
}

function median(arr) {
  const sorted = [...arr].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

function truncate(str, len = 20) {
  return str.length > len ? str.slice(0, len) + '...' : str
}

export default function ForceNetwork({ matrix, driverNames, driverIds, influence, dependence }) {
  const containerRef = useRef(null)
  const svgRef = useRef(null)
  const simulationRef = useRef(null)
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 })
  const [tooltip, setTooltip] = useState(null)
  const [hoveredNode, setHoveredNode] = useState(null)
  const [showWeak, setShowWeak] = useState(false)

  // Observe container size
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect
      if (width > 0) setDimensions({ width, height: 500 })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Build and run simulation
  useEffect(() => {
    if (!matrix || !driverNames || driverNames.length === 0) return
    const svg = svgRef.current
    if (!svg) return

    const { width, height } = dimensions
    const n = driverNames.length

    // Compute medians for quadrant classification
    const infValues = driverIds.map((id) => influence[id] || 0)
    const depValues = driverIds.map((id) => dependence[id] || 0)
    const medInf = median(infValues)
    const medDep = median(depValues)

    // Scale for node radius based on influence — contrastive CIB yields negative values,
    // so the domain must span the real min or low-influence nodes get a negative radius.
    const maxInf = Math.max(...infValues, 1)
    const minInf = Math.min(...infValues, 0)
    const radiusScale = scaleLinear().domain([minInf, maxInf]).range([7, 24]).clamp(true)

    // Build nodes
    const nodes = driverNames.map((name, i) => {
      const id = driverIds[i]
      const inf = influence[id] || 0
      const dep = dependence[id] || 0
      return {
        id: i,
        driverId: id,
        name,
        inf,
        dep,
        radius: radiusScale(inf),
        quadrant: getQuadrant(inf, dep, medInf, medDep),
      }
    })

    // Build links — weak couplings (|score| < 2) hidden by default so the strong
    // structure stays readable; draw weak-first / negatives-last so an inhibiting
    // edge is never painted over by its promoting counterpart.
    const links = []
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (i !== j && matrix[i][j] !== 0 && (showWeak || Math.abs(matrix[i][j]) >= 2)) {
          links.push({
            source: i,
            target: j,
            value: matrix[i][j],
          })
        }
      }
    }
    links.sort((a, b) => (Math.abs(a.value) - Math.abs(b.value)) || ((a.value < 0) - (b.value < 0)))

    // Simulation
    if (simulationRef.current) simulationRef.current.stop()

    const sim = forceSimulation(nodes)
      .force(
        'link',
        forceLink(links)
          .id((d) => d.id)
          .distance(100)
          .strength((d) => Math.abs(d.value) / 6),
      )
      .force('charge', forceManyBody().strength(-200))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collide', forceCollide((d) => d.radius + 6))

    simulationRef.current = sim

    // Clear SVG and build groups
    while (svg.firstChild) svg.removeChild(svg.firstChild)

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs')
    svg.appendChild(defs)

    const linkGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
    const nodeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
    const labelGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g')
    svg.appendChild(linkGroup)
    svg.appendChild(nodeGroup)
    svg.appendChild(labelGroup)

    // Create SVG link elements
    const linkElements = links.map((l) => {
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line')
      const positive = l.value > 0
      const absVal = Math.abs(l.value)
      const baseColor = positive ? '#10b981' : '#ef4444'
      const opacity = absVal / 3
      line.setAttribute('stroke', baseColor)
      line.setAttribute('stroke-opacity', String(opacity))
      line.setAttribute('stroke-width', String(1 + absVal * 1.5))
      line.setAttribute('stroke-linecap', 'round')
      line.dataset.source = l.source.id ?? l.source
      line.dataset.target = l.target.id ?? l.target
      linkGroup.appendChild(line)
      return line
    })

    // Create SVG node elements
    const nodeElements = nodes.map((nd) => {
      const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle')
      circle.setAttribute('r', String(nd.radius))
      const fill = CIB_QUADRANT_COLORS[nd.quadrant]
      const c = d3color(fill)
      if (c) c.opacity = 0.85
      circle.setAttribute('fill', c ? c.formatRgb() : fill)
      circle.setAttribute('stroke', fill)
      circle.setAttribute('stroke-width', '1.5')
      circle.setAttribute('cursor', 'pointer')
      circle.dataset.index = String(nd.id)
      nodeGroup.appendChild(circle)
      return circle
    })

    // Create labels
    const labelElements = nodes.map((nd) => {
      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text')
      text.setAttribute('fill', '#e4e4e7')
      text.setAttribute('font-size', '10')
      text.setAttribute('text-anchor', 'middle')
      text.setAttribute('dy', '0.35em')
      text.setAttribute('pointer-events', 'none')
      text.setAttribute('font-family', 'Inter, system-ui, sans-serif')
      text.textContent = truncate(nd.name)
      labelGroup.appendChild(text)
      return text
    })

    // Tick handler
    sim.on('tick', () => {
      linkElements.forEach((line, i) => {
        const s = links[i].source
        const t = links[i].target
        line.setAttribute('x1', s.x)
        line.setAttribute('y1', s.y)
        line.setAttribute('x2', t.x)
        line.setAttribute('y2', t.y)
      })
      nodeElements.forEach((circle, i) => {
        const nd = nodes[i]
        nd.x = Math.max(nd.radius, Math.min(width - nd.radius, nd.x))
        nd.y = Math.max(nd.radius, Math.min(height - nd.radius, nd.y))
        circle.setAttribute('cx', nd.x)
        circle.setAttribute('cy', nd.y)
      })
      labelElements.forEach((text, i) => {
        text.setAttribute('x', nodes[i].x)
        text.setAttribute('y', nodes[i].y + nodes[i].radius + 12)
      })
    })

    return () => {
      sim.stop()
    }
  }, [matrix, driverNames, driverIds, influence, dependence, dimensions, showWeak])

  // Hover interactions via event delegation
  const handleMouseMove = useCallback(
    (e) => {
      const svg = svgRef.current
      if (!svg || !matrix || !driverNames) return

      const target = e.target
      if (target.tagName === 'circle' && target.dataset.index != null) {
        const idx = parseInt(target.dataset.index, 10)
        setHoveredNode(idx)

        const rect = containerRef.current.getBoundingClientRect()
        setTooltip({
          x: e.clientX - rect.left + 12,
          y: e.clientY - rect.top - 8,
          text: driverNames[idx],
        })

        // Highlight connected links
        const lines = svg.querySelectorAll('line')
        lines.forEach((line) => {
          const src = parseInt(line.dataset.source, 10)
          const tgt = parseInt(line.dataset.target, 10)
          if (src === idx || tgt === idx) {
            line.setAttribute('stroke-opacity', '1')
          } else {
            line.setAttribute('stroke-opacity', '0.05')
          }
        })

        // Dim unconnected nodes
        const circles = svg.querySelectorAll('circle')
        const connected = new Set([idx])
        lines.forEach((line) => {
          const src = parseInt(line.dataset.source, 10)
          const tgt = parseInt(line.dataset.target, 10)
          if (src === idx) connected.add(tgt)
          if (tgt === idx) connected.add(src)
        })
        circles.forEach((c) => {
          const ci = parseInt(c.dataset.index, 10)
          c.setAttribute('opacity', connected.has(ci) ? '1' : '0.2')
        })
      }
    },
    [matrix, driverNames],
  )

  const handleMouseLeave = useCallback(() => {
    setHoveredNode(null)
    setTooltip(null)

    const svg = svgRef.current
    if (!svg || !matrix) return

    // Reset link opacities
    const lines = svg.querySelectorAll('line')
    lines.forEach((line) => {
      const absVal = (() => {
        const src = parseInt(line.dataset.source, 10)
        const tgt = parseInt(line.dataset.target, 10)
        return Math.abs(matrix[src]?.[tgt] ?? 0)
      })()
      line.setAttribute('stroke-opacity', String(absVal / 3))
    })

    // Reset node opacities
    const circles = svg.querySelectorAll('circle')
    circles.forEach((c) => c.setAttribute('opacity', '1'))
  }, [matrix])

  if (!matrix || !driverNames || driverNames.length === 0) {
    return (
      <div className="flex items-center justify-center h-[500px] text-zinc-500 text-sm">
        No CIB matrix data available
      </div>
    )
  }

  return (
    <div ref={containerRef} className="relative w-full" style={{ height: 500 }}>
      <svg
        ref={svgRef}
        width={dimensions.width}
        height={dimensions.height}
        className="w-full"
        style={{ background: 'transparent' }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-50 glass rounded-md px-2.5 py-1.5 text-xs text-zinc-100 font-medium"
          style={{ left: tooltip.x, top: tooltip.y }}
        >
          {tooltip.text}
        </div>
      )}

      {/* Edge-strength toggle */}
      <button
        onClick={() => setShowWeak((v) => !v)}
        className={`absolute top-3 right-3 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
          showWeak ? 'bg-blue-600/20 text-blue-400' : 'bg-zinc-800 text-zinc-400 hover:text-zinc-200'
        }`}
      >
        {showWeak ? 'All couplings' : 'Strong couplings (|score| ≥ 2)'}
      </button>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 flex flex-col gap-1.5 text-[10px] text-zinc-400">
        <div className="flex items-center gap-2">
          <div className="w-5 h-0.5 rounded" style={{ background: '#10b981' }} />
          <span>Promoting</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-5 h-0.5 rounded" style={{ background: '#ef4444' }} />
          <span>Inhibiting</span>
        </div>
        <div className="mt-1 flex items-center gap-2 flex-wrap">
          {Object.entries(CIB_QUADRANT_COLORS).map(([key, col]) => (
            <div key={key} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full" style={{ background: col }} />
              <span className="capitalize">{key}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
