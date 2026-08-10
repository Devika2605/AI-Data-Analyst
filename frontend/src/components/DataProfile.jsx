import React from 'react'
import { Hash, Calendar, Type, Tag, KeyRound } from 'lucide-react'

const ROLE_META = {
  numeric: { icon: Hash, color: 'text-brand-600 bg-brand-50', label: 'numeric' },
  date: { icon: Calendar, color: 'text-purple-600 bg-purple-50', label: 'date' },
  text: { icon: Type, color: 'text-cyan-600 bg-cyan-50', label: 'text' },
  categorical: { icon: Tag, color: 'text-amber-600 bg-amber-50', label: 'category' },
  id: { icon: KeyRound, color: 'text-ink-500 bg-surface-muted', label: 'id' },
}

export default function DataProfile({ profile }) {
  if (!profile) return null

  return (
    <div>
      <div className="flex items-center gap-4 mb-4 text-sm text-ink-700">
        <span><strong className="text-ink-900">{profile.rows.toLocaleString()}</strong> rows</span>
        <span><strong className="text-ink-900">{profile.columns}</strong> columns</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {profile.column_profiles.map((col) => {
          const meta = ROLE_META[col.role] || ROLE_META.categorical
          const Icon = meta.icon
          return (
            <div key={col.name} className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-ink-900 truncate">{col.name}</p>
                <span className={`badge ${meta.color}`}><Icon size={11} /> {meta.label}</span>
              </div>

              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-ink-500">
                <span>Missing: <strong className="text-ink-700">{col.missing_pct}%</strong></span>
                <span>Unique: <strong className="text-ink-700">{col.unique_count}</strong></span>

                {col.role === 'numeric' && (
                  <>
                    <span>Min: <strong className="text-ink-700">{col.min ?? '—'}</strong></span>
                    <span>Max: <strong className="text-ink-700">{col.max ?? '—'}</strong></span>
                    <span>Mean: <strong className="text-ink-700">{col.mean ?? '—'}</strong></span>
                    <span>Median: <strong className="text-ink-700">{col.median ?? '—'}</strong></span>
                    <span>Std dev: <strong className="text-ink-700">{col.std ?? '—'}</strong></span>
                    <span>Q1 / Q3: <strong className="text-ink-700">{col.q1 ?? '—'} / {col.q3 ?? '—'}</strong></span>
                  </>
                )}

                {col.role === 'date' && (
                  <>
                    <span className="col-span-2">Range: <strong className="text-ink-700">{col.earliest?.slice(0, 10)} → {col.latest?.slice(0, 10)}</strong></span>
                    <span>Frequency: <strong className="text-ink-700">{col.detected_frequency || 'unknown'}</strong></span>
                  </>
                )}

                {(col.role === 'categorical' || col.role === 'text') && col.top_categories?.length > 0 && (
                  <span className="col-span-2">
                    Top: <strong className="text-ink-700">
                      {col.top_categories.slice(0, 3).map((t) => `${t.value} (${t.count})`).join(', ')}
                    </strong>
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
