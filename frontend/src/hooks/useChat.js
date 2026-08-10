import { useCallback, useState } from 'react'
import { sendChat } from '../services/api'

function makeSessionId() {
  return 'sess_' + Math.random().toString(36).slice(2) + Date.now().toString(36)
}

export function useChat(datasetIds) {
  const [sessionId] = useState(makeSessionId)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const ask = useCallback(async (text) => {
    if (!text.trim()) return
    setError(null)
    const userMsg = { role: 'user', content: text, id: Date.now() + '-u' }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)
    try {
      const response = await sendChat(sessionId, text, datasetIds)
      const assistantMsg = { role: 'assistant', content: response, id: Date.now() + '-a' }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }, [sessionId, datasetIds])

  return { sessionId, messages, loading, error, ask }
}
