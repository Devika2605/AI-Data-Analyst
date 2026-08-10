import React, { useEffect, useRef, useState } from 'react'
import { Send } from 'lucide-react'
import ChatMessage from './ChatMessage'
import SuggestedQuestions from './SuggestedQuestions'
import LoadingState from './LoadingState'

export default function Chat({ messages, loading, error, onAsk, disabled }) {
  const [input, setInput] = useState('')
  const scrollRef = useRef(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  const submit = (text) => {
    const value = (text ?? input).trim()
    if (!value || disabled) return
    onAsk(value)
    setInput('')
  }

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-6 py-6 space-y-5">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto text-center py-10">
            <h2 className="text-lg font-semibold text-ink-900">Ask anything about your data</h2>
            <p className="text-sm text-ink-500 mt-1 mb-6">
              Discover insights, trends, anomalies, and forecasts — powered by real computation, not guesses.
            </p>
            <div className="flex justify-center">
              <SuggestedQuestions onSelect={submit} />
            </div>
          </div>
        )}

        {messages.map((m) => <ChatMessage key={m.id} message={m} />)}

        {loading && <LoadingState compact label="Analyzing…" />}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      <div className="border-t border-ink-300/40 bg-white px-6 py-4">
        {messages.length > 0 && (
          <div className="mb-3">
            <SuggestedQuestions onSelect={submit} />
          </div>
        )}
        <div className="flex items-center gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            disabled={disabled}
            placeholder={disabled ? 'Upload a dataset to start asking questions…' : 'Ask anything about your data…'}
            className="flex-1 text-sm border border-ink-300/60 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500 disabled:bg-surface-muted"
          />
          <button onClick={() => submit()} disabled={disabled || !input.trim()} className="btn-primary">
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}
