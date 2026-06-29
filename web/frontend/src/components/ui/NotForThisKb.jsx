import { Database } from 'lucide-react'

/** Shown when the current page has no data for the selected knowledge base (graceful). */
export default function NotForThisKb() {
  return (
    <div className="flex flex-col items-center justify-center h-[calc(100vh-44px)] text-center px-8">
      <Database className="text-zinc-700 mb-4" size={40} />
      <div className="text-zinc-300 text-lg font-semibold mb-2">
        Not available for this knowledge base
      </div>
      <p className="text-sm text-zinc-500 max-w-md">
        This view has no data for the selected knowledge base — it was only run through the
        functional scenario path. Switch the knowledge base in the top bar, or pick a view that
        is available for it.
      </p>
    </div>
  )
}
