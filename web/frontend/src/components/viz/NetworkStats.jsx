import Card from '@/components/ui/Card'

export default function NetworkStats({ stats }) {
  if (!stats) return null

  return (
    <Card>
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        <div>
          <div className="text-xs text-zinc-500 mb-0.5">Total Edges</div>
          <div className="text-lg font-bold text-white">{stats.total_edges}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-0.5">Promoting / Inhibiting</div>
          <div className="text-lg font-bold">
            <span className="text-emerald-400">{stats.promoting}</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className="text-red-400">{stats.inhibiting}</span>
          </div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-0.5">Most Influential</div>
          <div className="text-sm font-semibold text-white truncate">{stats.most_influential}</div>
        </div>
        {stats.strongest_promoting && (
          <div className="col-span-2 lg:col-span-3">
            <div className="text-xs text-zinc-500 mb-0.5">Strongest Promoting</div>
            <div className="text-xs text-emerald-400 truncate">{stats.strongest_promoting}</div>
          </div>
        )}
        {stats.strongest_inhibiting && (
          <div className="col-span-2 lg:col-span-3">
            <div className="text-xs text-zinc-500 mb-0.5">Strongest Inhibiting</div>
            <div className="text-xs text-red-400 truncate">{stats.strongest_inhibiting}</div>
          </div>
        )}
      </div>
    </Card>
  )
}
