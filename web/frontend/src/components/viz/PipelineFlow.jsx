import { useCallback, useMemo } from 'react'
import { ReactFlow, Handle, Position } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import {
  Database,
  Boxes,
  TrendingUp,
  Merge,
  Grid3x3,
  ArrowLeftRight,
  CheckCircle,
  FileText,
  BarChart3,
} from 'lucide-react'
import { PIPELINE_COLORS } from '@/utils/colors'

const ICONS = {
  kb: Database,
  bom: Boxes,
  trends: TrendingUp,
  merge: Merge,
  morph: Grid3x3,
  cib: ArrowLeftRight,
  consistency: CheckCircle,
  scenarios: FileText,
  mcda: BarChart3,
}

const PATHS = {
  kb: '/',
  bom: '/bom',
  trends: '/drivers',
  merge: '/drivers',
  morph: '/morphbox',
  cib: '/cib',
  consistency: '/cib',
  scenarios: '/scenarios',
  mcda: '/scenarios',
}

function PipelineNode({ data }) {
  const Icon = ICONS[data.key]
  const color = PIPELINE_COLORS[data.category]
  const big = data.expanded

  return (
    <div
      onClick={() => data.onClick?.(PATHS[data.key])}
      className={`flex items-center rounded-lg cursor-pointer transition-all duration-200 hover:scale-105 ${big ? 'gap-3 px-5 py-3.5' : 'gap-2 px-3 py-2'}`}
      style={{
        background: `${color}18`,
        border: `1px solid ${color}40`,
        minWidth: big ? 200 : 120,
      }}
    >
      <Handle type="target" position={Position.Left} className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Top} id="top" className="!bg-transparent !border-0 !w-0 !h-0" />
      <div
        className={`flex items-center justify-center rounded-md shrink-0 ${big ? 'w-10 h-10' : 'w-7 h-7'}`}
        style={{ background: `${color}30` }}
      >
        <Icon size={big ? 20 : 14} style={{ color }} />
      </div>
      <div className="flex flex-col min-w-0">
        <span className={`font-semibold text-zinc-100 leading-tight truncate ${big ? 'text-sm' : 'text-[11px]'}`}>
          {data.label}
        </span>
        {data.metric != null && (
          <span className={`font-medium mt-0.5 ${big ? 'text-xs' : 'text-[10px]'}`} style={{ color }}>
            {data.metric}
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Right} className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} id="bottom" className="!bg-transparent !border-0 !w-0 !h-0" />
    </div>
  )
}

const nodeTypes = { pipeline: PipelineNode }

const defaultEdgeOptions = {
  type: 'default',
  style: {
    stroke: 'rgba(161,161,170,0.25)',
    strokeWidth: 1.5,
    strokeDasharray: '6 4',
  },
  className: 'flow-edge-animated',
  animated: false,
}

const INLINE_POSITIONS = {
  kb:          { x: 0,    y: 20  },
  bom:         { x: 200,  y: -20 },
  trends:      { x: 200,  y: 60  },
  merge:       { x: 400,  y: 20  },
  morph:       { x: 580,  y: 20  },
  cib:         { x: 760,  y: 20  },
  consistency: { x: 940,  y: 20  },
  scenarios:   { x: 1120, y: 20  },
  mcda:        { x: 1300, y: 20  },
}

const EXPANDED_POSITIONS = {
  kb:          { x: 0,   y: 60  },
  bom:         { x: 300, y: 0   },
  trends:      { x: 300, y: 120 },
  merge:       { x: 600, y: 60  },
  morph:       { x: 900, y: 60  },
  cib:         { x: 200, y: 280 },
  consistency: { x: 500, y: 280 },
  scenarios:   { x: 800, y: 280 },
  mcda:        { x: 1100,y: 280 },
}

const NODE_DEFS = [
  { id: 'kb',          label: 'Knowledge Base',     fullLabel: 'Knowledge Base',      category: 'input',    metricKey: 'sources',          metricSuffix: 'sources' },
  { id: 'bom',         label: 'BOM Decomp.',        fullLabel: 'BOM Decomposition',   category: 'input',    metricKey: 'chunks',           metricSuffix: 'chunks' },
  { id: 'trends',      label: 'Trend Scanning',     fullLabel: 'Trend Scanning',      category: 'input',    metricKey: null },
  { id: 'merge',       label: 'Driver Merge',       fullLabel: 'Driver Merge',        category: 'analysis', metricKey: 'drivers_total',    metricSuffix: 'drivers' },
  { id: 'morph',       label: 'Morph Box',          fullLabel: 'Morphological Box',   category: 'analysis', metricKey: 'manifestations',   metricSuffix: 'manif.' },
  { id: 'cib',         label: 'CIB Analysis',       fullLabel: 'CIB Analysis',        category: 'analysis', metricKey: null },
  { id: 'consistency', label: 'Consistency',         fullLabel: 'Consistency Filter',  category: 'analysis', metricKey: 'consistency_seeds',metricSuffix: 'seeds' },
  { id: 'scenarios',   label: 'Scenarios',           fullLabel: 'Scenario Generation', category: 'output',   metricKey: 'scenarios',        metricSuffix: 'scenarios' },
  { id: 'mcda',        label: 'MCDA Eval',           fullLabel: 'MCDA Evaluation',     category: 'output',   metricKey: null },
]

const INLINE_EDGES = [
  { id: 'kb-bom', source: 'kb', target: 'bom' },
  { id: 'kb-trends', source: 'kb', target: 'trends' },
  { id: 'bom-merge', source: 'bom', target: 'merge' },
  { id: 'trends-merge', source: 'trends', target: 'merge' },
  { id: 'merge-morph', source: 'merge', target: 'morph' },
  { id: 'morph-cib', source: 'morph', target: 'cib' },
  { id: 'cib-consistency', source: 'cib', target: 'consistency' },
  { id: 'consistency-scenarios', source: 'consistency', target: 'scenarios' },
  { id: 'scenarios-mcda', source: 'scenarios', target: 'mcda' },
]

const EXPANDED_EDGES = [
  { id: 'kb-bom', source: 'kb', target: 'bom' },
  { id: 'kb-trends', source: 'kb', target: 'trends' },
  { id: 'bom-merge', source: 'bom', target: 'merge' },
  { id: 'trends-merge', source: 'trends', target: 'merge' },
  { id: 'merge-morph', source: 'merge', target: 'morph' },
  { id: 'morph-cib', source: 'morph', target: 'cib', sourceHandle: 'bottom', targetHandle: 'top' },
  { id: 'cib-consistency', source: 'cib', target: 'consistency' },
  { id: 'consistency-scenarios', source: 'consistency', target: 'scenarios' },
  { id: 'scenarios-mcda', source: 'scenarios', target: 'mcda' },
]

export default function PipelineFlow({ overview = {}, onNodeClick, height = 220, expanded = false }) {
  const handleNodeClick = useCallback(
    (path) => {
      if (onNodeClick) onNodeClick(path)
    },
    [onNodeClick],
  )

  const positions = expanded ? EXPANDED_POSITIONS : INLINE_POSITIONS

  const nodes = useMemo(
    () =>
      NODE_DEFS.map((def) => ({
        id: def.id,
        type: 'pipeline',
        position: positions[def.id],
        data: {
          key: def.id,
          label: expanded ? def.fullLabel : def.label,
          category: def.category,
          expanded,
          metric:
            def.metricKey && overview[def.metricKey] != null
              ? `${overview[def.metricKey]} ${def.metricSuffix}`
              : null,
          onClick: handleNodeClick,
        },
      })),
    [overview, handleNodeClick, expanded, positions],
  )

  const edges = useMemo(
    () => (expanded ? EXPANDED_EDGES : INLINE_EDGES),
    [expanded],
  )

  return (
    <div className="w-full rounded-xl overflow-hidden" style={{ height }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        fitViewOptions={{ padding: expanded ? 0.12 : 0.15 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        minZoom={0.3}
        maxZoom={2}
        style={{ background: 'transparent' }}
      />
    </div>
  )
}
