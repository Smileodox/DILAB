export default function ScoreBar({ label, value, max = 10, color = '#3b82f6' }) {
  const pct = (value / max) * 100

  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-zinc-500 w-24 text-right">{label}</span>
      <div className="flex-1 h-2 rounded-full bg-zinc-800/80 overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-mono text-zinc-400 w-8">{value.toFixed(1)}</span>
    </div>
  )
}
