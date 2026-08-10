import React from 'react'
import { Lightbulb } from 'lucide-react'
import ChartRenderer from './ChartRenderer'

export default function InsightCard({ insight }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-2 mb-1.5">
        <Lightbulb size={15} className="text-amber-500" />
        <p className="text-sm font-semibold text-ink-900">{insight.title}</p>
      </div>
      <p className="text-xl font-bold text-brand-700 mb-1.5">{insight.value}</p>
      <p className="text-sm text-ink-500 leading-relaxed">{insight.explanation}</p>
      {insight.chart && (
        <div className="mt-4">
          <ChartRenderer spec={insight.chart} />
        </div>
      )}
    </div>
  )
}
