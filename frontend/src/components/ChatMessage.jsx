import React, { useState } from 'react'
import { Bot, User, ChevronDown, ChevronUp, ListChecks, Clock, AlertTriangle } from 'lucide-react'
import ChartRenderer from './ChartRenderer'
import ResultTable from './ResultTable'
import SQLViewer from './SQLViewer'

export default function ChatMessage({ message }) {
  const [showMethodology, setShowMethodology] = useState(false)
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex items-start gap-3 justify-end">
        <div className="max-w-xl bg-brand-600 text-white text-sm rounded-2xl rounded-tr-sm px-4 py-2.5">
          {message.content}
        </div>
        <div className="w-7 h-7 rounded-full bg-ink-300/40 flex items-center justify-center shrink-0">
          <User size={14} className="text-ink-700" />
        </div>
      </div>
    )
  }

  const r = message.content
  const isClarification = !!r.clarification_needed
  const isError = !!r.error

  return (
    <div className="flex items-start gap-3">
      <div className="w-7 h-7 rounded-full bg-brand-600 flex items-center justify-center shrink-0">
        <Bot size={14} className="text-white" />
      </div>
      <div className="max-w-2xl w-full space-y-3">
        <div className={`rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm whitespace-pre-wrap
          ${isError ? 'bg-red-50 text-red-800 border border-red-200' : 'bg-white border border-ink-300/40 text-ink-900'}`}>
          {isError && <AlertTriangle size={14} className="inline mr-1.5 -mt-0.5" />}
          {isClarification ? r.clarification_needed : r.answer}
        </div>

        {r.visualization && <ChartRenderer spec={r.visualization} />}
        {r.result && <ResultTable result={r.result} />}
        {r.sql && <SQLViewer sql={r.sql} />}

        {r.methodology?.length > 0 && (
          <div className="card p-0 overflow-hidden">
            <button
              onClick={() => setShowMethodology((v) => !v)}
              className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-ink-700 hover:bg-surface-muted"
            >
              <span className="flex items-center gap-1.5"><ListChecks size={13} /> Analysis performed</span>
              {showMethodology ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
            {showMethodology && (
              <ol className="px-4 pb-3 pt-1 text-xs text-ink-500 list-decimal list-inside space-y-1">
                {r.methodology.map((step, i) => <li key={i}>{step}</li>)}
              </ol>
            )}
          </div>
        )}

        {r.warnings?.length > 0 && (
          <div className="flex items-start gap-1.5 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-1.5">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            <span>{r.warnings.join(' · ')}</span>
          </div>
        )}

        {(r.execution_time_ms || r.sources?.length > 0) && (
          <div className="flex items-center gap-3 text-[11px] text-ink-500 px-1">
            {r.execution_time_ms > 0 && (
              <span className="flex items-center gap-1"><Clock size={11} /> {r.execution_time_ms}ms</span>
            )}
            {r.sources?.length > 0 && <span>Source: {r.sources.join(', ')}</span>}
          </div>
        )}
      </div>
    </div>
  )
}
