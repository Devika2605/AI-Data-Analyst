import React from 'react'
import { CheckCircle2, AlertTriangle, XCircle, Info } from 'lucide-react'

const SEVERITY_META = {
  warning: { icon: AlertTriangle, color: 'text-amber-600' },
  error: { icon: XCircle, color: 'text-red-600' },
  info: { icon: Info, color: 'text-brand-600' },
}

export default function DataQuality({ quality }) {
  if (!quality) return null

  const scoreColor = quality.score >= 80 ? 'text-green-600' : quality.score >= 60 ? 'text-amber-600' : 'text-red-600'
  const ringColor = quality.score >= 80 ? '#16a34a' : quality.score >= 60 ? '#d97706' : '#dc2626'

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div className="card p-6 flex flex-col items-center justify-center text-center">
        <svg width="96" height="96" viewBox="0 0 96 96">
          <circle cx="48" cy="48" r="42" fill="none" stroke="#eef0f3" strokeWidth="8" />
          <circle
            cx="48" cy="48" r="42" fill="none" stroke={ringColor} strokeWidth="8"
            strokeDasharray={`${(quality.score / 100) * 264} 264`}
            strokeLinecap="round" transform="rotate(-90 48 48)"
          />
        </svg>
        <p className={`text-2xl font-bold -mt-16 ${scoreColor}`}>{quality.score}</p>
        <p className="text-xs text-ink-500 mt-16">Data Quality Score</p>
      </div>

      <div className="card p-5 md:col-span-2">
        <p className="text-sm font-medium text-ink-900 mb-3">Checks passed</p>
        <ul className="space-y-1.5">
          {quality.checks_passed.map((c, i) => (
            <li key={i} className="flex items-center gap-2 text-sm text-ink-700">
              <CheckCircle2 size={14} className="text-green-600 shrink-0" /> {c}
            </li>
          ))}
        </ul>

        {quality.issues.length > 0 && (
          <>
            <p className="text-sm font-medium text-ink-900 mt-4 mb-2">Issues found</p>
            <ul className="space-y-1.5">
              {quality.issues.map((issue, i) => {
                const meta = SEVERITY_META[issue.severity] || SEVERITY_META.info
                const Icon = meta.icon
                return (
                  <li key={i} className={`flex items-center gap-2 text-sm ${meta.color}`}>
                    <Icon size={14} className="shrink-0" /> <span className="text-ink-700">{issue.message}</span>
                  </li>
                )
              })}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}
