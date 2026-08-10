import React from 'react'
import ChartRenderer from './ChartRenderer'
import { Gauge } from 'lucide-react'

export default function Dashboard({ dashboard }) {
  if (!dashboard) return null

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {dashboard.kpis.map((kpi) => (
          <div key={kpi.label} className="card p-4">
            <p className="text-xs text-ink-500 flex items-center gap-1"><Gauge size={12} /> {kpi.label}</p>
            <p className="text-xl font-bold text-ink-900 mt-1">{kpi.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {dashboard.charts.map((chart, i) => (
          <ChartRenderer key={i} spec={chart} />
        ))}
      </div>
    </div>
  )
}
