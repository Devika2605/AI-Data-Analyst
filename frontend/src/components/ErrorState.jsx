import React from 'react'
import { AlertTriangle } from 'lucide-react'

export default function ErrorState({ message = 'Something went wrong.', onRetry = null }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center px-6">
      <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center mb-3">
        <AlertTriangle size={20} className="text-red-600" />
      </div>
      <p className="text-sm text-ink-700 max-w-sm">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary mt-4">Try again</button>
      )}
    </div>
  )
}
