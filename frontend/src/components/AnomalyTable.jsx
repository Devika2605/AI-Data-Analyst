import React from 'react'
import { AlertOctagon } from 'lucide-react'

const SEVERITY_STYLE = {
  high: 'bg-red-50 text-red-700 border-red-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-ink-300/20 text-ink-700 border-ink-300/40',
}

export default function AnomalyTable({ anomalies }) {
  if (!anomalies || anomalies.length === 0) return null

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-ink-300/40 bg-surface-muted text-xs font-medium text-ink-700">
        <AlertOctagon size={13} /> Flagged rows
      </div>
      <div className="max-h-96 overflow-y-auto divide-y divide-ink-300/20">
        {anomalies.map((a, i) => (
          <div key={i} className="px-4 py-3">
            <div className="flex items-center justify-between mb-1">
              <p className="text-sm font-medium text-ink-900">Anomaly #{a.row_index}</p>
              <span className={`badge border ${SEVERITY_STYLE[a.severity] || SEVERITY_STYLE.low}`}>
                {a.severity} · score {a.anomaly_score}
              </span>
            </div>
            <p className="text-xs text-ink-500 mb-1">
              {Object.entries(a.values || {}).map(([k, v]) => `${k}: ${v}`).join('  ·  ')}
            </p>
            <p className="text-xs text-ink-700">{a.reason}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
