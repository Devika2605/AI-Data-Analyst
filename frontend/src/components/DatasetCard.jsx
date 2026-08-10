import React from 'react'
import { FileSpreadsheet, CheckCircle2, AlertCircle } from 'lucide-react'

export default function DatasetCard({ dataset, selected, onToggle }) {
  const scoreColor = dataset.quality_score >= 80 ? 'text-green-600'
    : dataset.quality_score >= 60 ? 'text-amber-600' : 'text-red-600'

  return (
    <button
      onClick={() => onToggle(dataset.dataset_id)}
      className={`card w-full text-left p-4 transition-colors ${selected ? 'ring-2 ring-brand-500 border-brand-500' : 'hover:border-ink-300'}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <FileSpreadsheet size={18} className="text-brand-600 shrink-0" />
          <p className="text-sm font-medium text-ink-900 truncate">{dataset.filename}</p>
        </div>
        {selected ? (
          <CheckCircle2 size={18} className="text-brand-600 shrink-0" />
        ) : (
          <span className="w-[18px] h-[18px] rounded-full border border-ink-300 shrink-0" />
        )}
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-ink-500">
        <div>
          <p className="text-ink-900 font-semibold">{dataset.rows.toLocaleString()}</p>
          <p>rows</p>
        </div>
        <div>
          <p className="text-ink-900 font-semibold">{dataset.columns}</p>
          <p>columns</p>
        </div>
        <div>
          <p className={`font-semibold ${scoreColor}`}>{dataset.quality_score}/100</p>
          <p>quality</p>
        </div>
      </div>

      {dataset.warnings?.length > 0 && (
        <div className="mt-3 flex items-start gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-2 py-1.5">
          <AlertCircle size={13} className="mt-0.5 shrink-0" />
          <span>{dataset.warnings[0]}{dataset.warnings.length > 1 ? ` (+${dataset.warnings.length - 1} more)` : ''}</span>
        </div>
      )}
    </button>
  )
}
