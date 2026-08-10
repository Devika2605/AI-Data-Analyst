import React from 'react'

export default function ResultTable({ result }) {
  if (!result || !result.columns || result.rows.length === 0) return null

  return (
    <div className="card overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-ink-300/40 bg-surface-muted">
            {result.columns.map((c) => (
              <th key={c} className="text-left font-medium text-ink-700 px-3 py-2 whitespace-nowrap">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i} className="border-b border-ink-300/20 last:border-0 hover:bg-surface-muted/60">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2 text-ink-700 whitespace-nowrap">
                  {cell === null || cell === undefined ? <span className="text-ink-300">—</span> : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
