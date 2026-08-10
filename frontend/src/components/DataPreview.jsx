import React from 'react'
import { Eye } from 'lucide-react'

export default function DataPreview({ preview }) {
  if (!preview) return null
  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-ink-300/40 bg-surface-muted text-xs font-medium text-ink-700">
        <Eye size={13} /> Preview (first {preview.rows.length} rows)
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-ink-300/40">
              {preview.columns.map((c) => (
                <th key={c} className="text-left font-medium text-ink-700 px-3 py-2 whitespace-nowrap">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, i) => (
              <tr key={i} className="border-b border-ink-300/20 last:border-0">
                {row.map((cell, j) => (
                  <td key={j} className="px-3 py-1.5 text-ink-700 whitespace-nowrap">
                    {cell === null || cell === undefined ? <span className="text-ink-300">—</span> : String(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
