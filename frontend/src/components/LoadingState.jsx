import React from 'react'
import { Loader2 } from 'lucide-react'

export default function LoadingState({ label = 'Loading…', compact = false }) {
  if (compact) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-500">
        <Loader2 size={14} className="animate-spin" />
        {label}
      </div>
    )
  }
  return (
    <div className="flex flex-col items-center justify-center py-16 text-ink-500">
      <Loader2 size={24} className="animate-spin mb-3 text-brand-600" />
      <p className="text-sm">{label}</p>
    </div>
  )
}
