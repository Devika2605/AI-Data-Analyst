import React from 'react'
import ChartRenderer from './ChartRenderer'
import { TrendingUp } from 'lucide-react'

export default function ForecastChart({ forecast }) {
  if (!forecast) return null

  if (!forecast.sufficient_data) {
    return (
      <div className="card p-5 text-sm text-ink-700 flex items-start gap-2">
        <TrendingUp size={16} className="text-ink-400 mt-0.5 shrink-0" />
        {forecast.explanation}
      </div>
    )
  }

  const spec = {
    type: 'line',
    title: `${forecast.target_column} — history & forecast`,
    data: forecast.points,
    x_key: 'date',
    y_keys: ['value'],
  }

  return (
    <div className="space-y-3">
      <ChartRenderer spec={spec} />
      <p className="text-sm text-ink-500 px-1">{forecast.explanation}</p>
    </div>
  )
}
