import React, { useCallback, useRef, useState } from 'react'
import { UploadCloud, FileWarning } from 'lucide-react'
import { uploadDataset } from '../services/api'

export default function FileUpload({ onUploaded }) {
  const [dragOver, setDragOver] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  const handleFiles = useCallback(async (fileList) => {
    setError(null)
    const files = Array.from(fileList).filter((f) => f.name.toLowerCase().endsWith('.csv'))
    if (files.length === 0) {
      setError('Please select one or more .csv files.')
      return
    }
    for (const file of files) {
      setUploading(true)
      setProgress(0)
      try {
        const result = await uploadDataset(file, setProgress)
        if (!result.success) {
          setError(result.error || `Failed to upload ${file.name}`)
        } else {
          onUploaded?.(result.dataset)
        }
      } catch (err) {
        setError(err?.response?.data?.detail || err.message || `Failed to upload ${file.name}`)
      } finally {
        setUploading(false)
      }
    }
  }, [onUploaded])

  return (
    <div>
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          handleFiles(e.dataTransfer.files)
        }}
        onClick={() => inputRef.current?.click()}
        className={`card cursor-pointer border-dashed !border-2 px-6 py-10 flex flex-col items-center justify-center text-center transition-colors
          ${dragOver ? 'border-brand-500 bg-brand-50' : 'border-ink-300 hover:border-brand-500/60'}`}
      >
        <UploadCloud size={28} className="text-brand-600 mb-3" />
        <p className="text-sm font-medium text-ink-900">Drag &amp; drop CSV files here</p>
        <p className="text-xs text-ink-500 mt-1">or click to browse · one or more files supported</p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          multiple
          className="hidden"
          onChange={(e) => e.target.files && handleFiles(e.target.files)}
        />
      </div>

      {uploading && (
        <div className="mt-3">
          <div className="h-1.5 bg-ink-300/40 rounded-full overflow-hidden">
            <div className="h-full bg-brand-600 transition-all" style={{ width: `${progress}%` }} />
          </div>
          <p className="text-xs text-ink-500 mt-1">Uploading… {progress}%</p>
        </div>
      )}

      {error && (
        <div className="mt-3 flex items-start gap-2 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          <FileWarning size={16} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}
