import React from 'react'
import {
  MessageSquare, Database, FileBarChart2, ShieldCheck, LayoutDashboard,
  Sparkles, AlertTriangle, TrendingUp, FileDown, Plus,
} from 'lucide-react'

const NAV_ITEMS = [
  { id: 'chat', label: 'Conversation', icon: MessageSquare },
  { id: 'datasets', label: 'Datasets', icon: Database },
  { id: 'profile', label: 'Data Profile', icon: FileBarChart2 },
  { id: 'quality', label: 'Data Quality', icon: ShieldCheck },
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'insights', label: 'Insights', icon: Sparkles },
  { id: 'anomalies', label: 'Anomalies', icon: AlertTriangle },
  { id: 'forecast', label: 'Forecast', icon: TrendingUp },
  { id: 'reports', label: 'Reports', icon: FileDown },
]

export default function Sidebar({ activeView, onNavigate, onNewAnalysis, hasDatasets }) {
  return (
    <aside className="w-60 shrink-0 h-full bg-white border-r border-ink-300/40 flex flex-col">
      <div className="px-5 py-5 border-b border-ink-300/40">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center">
            <Sparkles size={16} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-ink-900 leading-tight">AI Data Analyst</p>
            <p className="text-[11px] text-ink-500 leading-tight">Analytics copilot</p>
          </div>
        </div>
      </div>

      <div className="px-3 pt-3">
        <button onClick={onNewAnalysis} className="btn-primary w-full justify-center">
          <Plus size={16} /> New Analysis
        </button>
      </div>

      <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const disabled = !hasDatasets && item.id !== 'datasets' && item.id !== 'chat'
          const active = activeView === item.id
          return (
            <button
              key={item.id}
              disabled={disabled}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors
                ${active ? 'bg-brand-50 text-brand-700 font-medium' : 'text-ink-700 hover:bg-surface-muted'}
                ${disabled ? 'opacity-40 cursor-not-allowed' : ''}`}
            >
              <Icon size={16} />
              {item.label}
            </button>
          )
        })}
      </nav>

      <div className="px-4 py-4 border-t border-ink-300/40 text-[11px] text-ink-500">
        Built for the AI Engineer Internship assignment · Digital Back Office
      </div>
    </aside>
  )
}
