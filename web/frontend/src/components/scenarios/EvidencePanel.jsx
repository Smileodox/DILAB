import { motion } from 'framer-motion'
import { X, Loader2, AlertTriangle, Radio, FileText } from 'lucide-react'

function SectionConnector() {
  return (
    <div className="flex justify-center py-1">
      <div className="flex flex-col items-center gap-1">
        <div className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
        <div className="w-px h-6 bg-zinc-700" />
        <div className="w-1.5 h-1.5 rounded-full bg-zinc-700" />
      </div>
    </div>
  )
}

export default function EvidencePanel({ traceability, loading, onClose }) {
  return (
    <motion.div
      initial={{ x: '100%' }}
      animate={{ x: 0 }}
      exit={{ x: '100%' }}
      transition={{ type: 'spring', damping: 30, stiffness: 300 }}
      className="fixed top-0 right-0 h-full w-full max-w-[600px] z-50 bg-zinc-950/95 backdrop-blur-xl border-l border-white/5 shadow-2xl"
    >
      <button
        onClick={onClose}
        className="absolute top-4 right-4 p-2 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-white/5 transition-colors z-10"
      >
        <X size={20} />
      </button>

      <div className="h-full overflow-y-auto p-8 pt-6">
        <h2 className="text-lg font-bold text-white mb-6 pr-10">
          Evidence &amp; Traceability
        </h2>

        {loading && (
          <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
            <Loader2 size={28} className="animate-spin mb-3" />
            <span className="text-sm">Loading traceability data...</span>
          </div>
        )}

        {!loading && traceability && (
          <>
            {traceability.assessment && (
              <section>
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                  Assessment
                </h3>

                {traceability.assessment.reasoning && (
                  <p className="text-sm text-zinc-300 leading-relaxed mb-4">
                    {traceability.assessment.reasoning}
                  </p>
                )}

                {traceability.assessment.key_risks && (
                  <div className="glass rounded-lg p-3 mb-3 border border-amber-500/10">
                    <div className="flex items-center gap-2 mb-2">
                      <AlertTriangle size={14} className="text-amber-500" />
                      <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
                        Key Risks
                      </span>
                    </div>
                    <p className="text-sm text-zinc-400 leading-relaxed">
                      {traceability.assessment.key_risks}
                    </p>
                  </div>
                )}

                {traceability.assessment.early_signals && (
                  <div className="glass rounded-lg p-3 border border-emerald-500/10">
                    <div className="flex items-center gap-2 mb-2">
                      <Radio size={14} className="text-emerald-500" />
                      <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">
                        Early Signals
                      </span>
                    </div>
                    <p className="text-sm text-zinc-400 leading-relaxed">
                      {traceability.assessment.early_signals}
                    </p>
                  </div>
                )}
              </section>
            )}

            <SectionConnector />

            {traceability.assumptions?.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                  Driver Assumptions
                </h3>
                <div className="space-y-2">
                  {traceability.assumptions.map((a, i) => (
                    <div key={i} className="glass rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-zinc-200">
                          {a.driver?.name || 'Unknown Driver'}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-zinc-800 text-zinc-400">
                          {a.state}
                        </span>
                      </div>
                      {a.description && (
                        <p className="text-xs text-zinc-500 leading-relaxed">
                          {a.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            <SectionConnector />

            {traceability.source_chain?.length > 0 && (
              <section>
                <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">
                  Source Evidence
                </h3>
                <div className="space-y-2">
                  {traceability.source_chain.map((src, i) => (
                    <div key={i} className="glass rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1.5">
                        <FileText size={14} className="text-zinc-500 shrink-0" />
                        <span className="text-sm font-medium text-zinc-200 truncate">
                          {src.source?.title || 'Unknown Source'}
                        </span>
                        {src.source?.type && (
                          <span className="text-[10px] font-mono text-zinc-600 shrink-0">
                            {src.source.type}
                          </span>
                        )}
                      </div>
                      {src.chunk_preview && (
                        <p className="text-xs text-zinc-500 leading-relaxed line-clamp-3 pl-5">
                          {src.chunk_preview}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </motion.div>
  )
}
