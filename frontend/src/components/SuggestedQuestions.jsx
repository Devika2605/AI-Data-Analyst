import React from 'react'
import { Sparkles } from 'lucide-react'

const DEFAULT_QUESTIONS = [
  'Which region generated the highest revenue?',
  'Show monthly sales trends.',
  'What are the top five customers?',
  'Which products are underperforming?',
  'Detect anomalies.',
  "Forecast next month's revenue.",
  'Generate a business summary.',
]

export default function SuggestedQuestions({ onSelect, questions = DEFAULT_QUESTIONS }) {
  return (
    <div>
      <p className="text-xs font-medium text-ink-500 mb-2 flex items-center gap-1.5">
        <Sparkles size={13} /> Try asking
      </p>
      <div className="flex flex-wrap gap-2">
        {questions.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            className="text-xs px-3 py-1.5 rounded-full border border-ink-300/60 text-ink-700 hover:border-brand-500 hover:text-brand-700 hover:bg-brand-50 transition-colors"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
