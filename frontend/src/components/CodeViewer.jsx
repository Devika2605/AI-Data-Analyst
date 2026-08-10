import React, { useState } from 'react'
import { Copy, Check, Code2 } from 'lucide-react'

export default function CodeViewer({ code, language = 'python', title = 'Generated code' }) {
  const [copied, setCopied] = useState(false)
  if (!code) return null

  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-ink-300/40 bg-surface-muted">
        <div className="flex items-center gap-1.5 text-xs font-medium text-ink-700">
          <Code2 size={13} /> {title}
        </div>
        <button onClick={copy} className="text-xs text-ink-500 hover:text-ink-900 flex items-center gap-1">
          {copied ? <Check size={13} className="text-green-600" /> : <Copy size={13} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="text-xs p-3 overflow-x-auto bg-[#0f1117] text-[#e2e4e9] leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  )
}
