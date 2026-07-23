// Friendly fallback for failed/empty API loads — keeps a fetch hiccup from blanking the page.
export default function LoadError({ title, message }) {
  return (
    <div className="max-w-7xl mx-auto px-8 py-8">
      {title && <h1 className="text-2xl font-bold text-white mb-6">{title}</h1>}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 max-w-md text-center mx-auto mt-12">
        <h2 className="text-base font-semibold text-zinc-100 mb-2">Data unavailable</h2>
        <p className="text-sm text-zinc-400 mb-6">
          {message || 'This view could not load its data. The backend may be restarting.'}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-sm font-medium text-white"
        >
          Retry
        </button>
      </div>
    </div>
  )
}
