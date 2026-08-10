import React from 'react'
import CodeViewer from './CodeViewer'
import { Database } from 'lucide-react'

export default function SQLViewer({ sql }) {
  if (!sql) return null
  return (
    <div>
      <div className="flex items-center gap-1.5 text-xs text-ink-500 mb-1.5">
        <Database size={12} /> Executed via DuckDB (read-only)
      </div>
      <CodeViewer code={sql} language="sql" title="SQL" />
    </div>
  )
}
