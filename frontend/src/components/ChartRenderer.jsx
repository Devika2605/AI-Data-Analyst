import React from 'react'
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell,
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from 'recharts'

const COLORS = ['#3b6fe0', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16']

export default function ChartRenderer({ spec }) {
  if (!spec || !spec.data || spec.data.length === 0) return null

  const { type, title, data } = spec

  return (
    <div className="card p-4">
      {title && <p className="text-sm font-medium text-ink-900 mb-3">{title}</p>}
      <ResponsiveContainer width="100%" height={280}>
        {renderChart(type, spec, data)}
      </ResponsiveContainer>
    </div>
  )
}

function renderChart(type, spec, data) {
  switch (type) {
    case 'line':
    case 'forecast_line':
      return (
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eef0f3" />
          <XAxis dataKey={spec.x_key || 'date'} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {(spec.y_keys || [spec.y_key || 'value']).map((k, i) => (
            <Line key={k} type="monotone" dataKey={k} stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />
          ))}
          {data.some((d) => 'upper' in d) && (
            <Line type="monotone" dataKey="upper" stroke="#c7d2fe" strokeDasharray="4 4" dot={false} name="Upper bound" />
          )}
          {data.some((d) => 'lower' in d) && (
            <Line type="monotone" dataKey="lower" stroke="#c7d2fe" strokeDasharray="4 4" dot={false} name="Lower bound" />
          )}
        </LineChart>
      )
    case 'area':
      return (
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eef0f3" />
          <XAxis dataKey={spec.x_key} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Area type="monotone" dataKey={spec.y_key} stroke="#3b6fe0" fill="#dbeafe" />
        </AreaChart>
      )
    case 'hbar':
      return (
        <BarChart data={data} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" stroke="#eef0f3" />
          <XAxis type="number" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey={spec.x_key} tick={{ fontSize: 11 }} width={100} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Bar dataKey={spec.y_key} fill="#3b6fe0" radius={[0, 4, 4, 0]} />
        </BarChart>
      )
    case 'pie':
    case 'donut':
      return (
        <PieChart>
          <Pie
            data={data}
            dataKey={spec.value_key}
            nameKey={spec.category_key}
            cx="50%" cy="50%"
            innerRadius={type === 'donut' ? 60 : 0}
            outerRadius={95}
            label={(e) => e[spec.category_key]}
          >
            {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
          </Pie>
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      )
    case 'scatter':
      return (
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#eef0f3" />
          <XAxis dataKey={spec.x_key} tick={{ fontSize: 11 }} name={spec.x_key} />
          <YAxis dataKey={spec.y_key} tick={{ fontSize: 11 }} name={spec.y_key} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          <Scatter data={data} fill="#3b6fe0" />
        </ScatterChart>
      )
    case 'histogram':
    case 'box':
    case 'bar':
    default:
      return (
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eef0f3" />
          <XAxis dataKey={spec.x_key || spec.category_key} tick={{ fontSize: 11 }} interval={0} angle={data.length > 6 ? -20 : 0} textAnchor={data.length > 6 ? 'end' : 'middle'} height={data.length > 6 ? 50 : 30} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          {(spec.y_keys || [spec.y_key || spec.value_key]).map((k, i) => (
            <Bar key={k} dataKey={k} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      )
  }
}
