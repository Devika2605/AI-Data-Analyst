import React, { useState } from 'react'
import { FileDown, Loader2 } from 'lucide-react'
import { exportReport } from '../services/api'

export default function ReportExport({ datasetId, sessionId }) {
  const [loading, setLoading] = useState(false)
  const [markdown, setMarkdown] = useState(null)
  const [error, setError] = useState(null)

  const generate = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await exportReport(datasetId, sessionId)
      setMarkdown(res.report_markdown)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to generate report.')
    } finally {
      setLoading(false)
    }
  }

  const download = () => {
    const blob = new Blob([markdown], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-data-analyst-report-${datasetId}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      <div className="card p-5 flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-ink-900">Export report</p>
          <p className="text-xs text-ink-500 mt-0.5">Includes dataset summary, quality report, insights, anomalies, and forecast.</p>
        </div>
        <button onClick={generate} disabled={loading} className="btn-primary">
          {loading ? <Loader2 size={15} className="animate-spin" /> : <FileDown size={15} />}
          Generate Report
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {markdown && (
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-ink-300/40 bg-surface-muted">
            <p className="text-xs font-medium text-ink-700">Report preview</p>
            <button onClick={download} className="btn-secondary text-xs !py-1">Download .md</button>
          </div>
          <pre className="text-xs p-4 whitespace-pre-wrap text-ink-700 max-h-[500px] overflow-y-auto">{markdown}</pre>
        </div>
      )}
    </div>
  )
}
