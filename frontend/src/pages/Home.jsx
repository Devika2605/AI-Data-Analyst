import React, { useEffect, useState, useCallback } from 'react'
import Sidebar from '../components/Sidebar'
import FileUpload from '../components/FileUpload'
import DatasetCard from '../components/DatasetCard'
import DataPreview from '../components/DataPreview'
import DataProfile from '../components/DataProfile'
import DataQuality from '../components/DataQuality'
import Chat from '../components/Chat'
import InsightCard from '../components/InsightCard'
import AnomalyTable from '../components/AnomalyTable'
import ForecastChart from '../components/ForecastChart'
import Dashboard from '../components/Dashboard'
import ReportExport from '../components/ReportExport'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import { useChat } from '../hooks/useChat'
import {
  getDataset, getProfile, getQuality, getInsights,
  detectAnomalies, getForecast, generateDashboard,
} from '../services/api'
import { Sparkles } from 'lucide-react'

export default function Home() {
  const [datasets, setDatasets] = useState([])
  const [selectedIds, setSelectedIds] = useState([])
  const [activeView, setActiveView] = useState('chat')

  const [selectedDetail, setSelectedDetail] = useState(null)
  const [profile, setProfile] = useState(null)
  const [quality, setQuality] = useState(null)
  const [insights, setInsights] = useState(null)
  const [anomalies, setAnomalies] = useState(null)
  const [forecast, setForecast] = useState(null)
  const [dashboard, setDashboard] = useState(null)
  const [panelLoading, setPanelLoading] = useState(false)
  const [panelError, setPanelError] = useState(null)

  const { messages, loading: chatLoading, error: chatError, ask } = useChat(selectedIds)

  const primaryDatasetId = selectedIds[0] || null

  const handleUploaded = (dataset) => {
    setDatasets((prev) => [...prev, dataset])
    setSelectedIds((prev) => (prev.length === 0 ? [dataset.dataset_id] : [...prev, dataset.dataset_id]))
  }

  const toggleSelect = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const newAnalysis = () => {
    setSelectedIds([])
    setActiveView('datasets')
  }

  const loadPanel = useCallback(async (view) => {
    if (!primaryDatasetId) return
    setPanelLoading(true)
    setPanelError(null)
    try {
      if (view === 'datasets') {
        const detail = await getDataset(primaryDatasetId)
        setSelectedDetail(detail)
      } else if (view === 'profile') {
        setProfile(await getProfile(primaryDatasetId))
      } else if (view === 'quality') {
        setQuality(await getQuality(primaryDatasetId))
      } else if (view === 'insights') {
        setInsights(await getInsights(primaryDatasetId))
      } else if (view === 'anomalies') {
        setAnomalies(await detectAnomalies(primaryDatasetId))
      } else if (view === 'forecast') {
        setForecast(await getForecast(primaryDatasetId))
      } else if (view === 'dashboard') {
        setDashboard(await generateDashboard(primaryDatasetId))
      }
    } catch (err) {
      setPanelError(err?.response?.data?.detail || err.message || 'Failed to load this view.')
    } finally {
      setPanelLoading(false)
    }
  }, [primaryDatasetId])

  useEffect(() => {
    if (activeView !== 'chat' && primaryDatasetId) {
      loadPanel(activeView)
    }
  }, [activeView, primaryDatasetId, loadPanel])

  const hasDatasets = datasets.length > 0

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar
        activeView={activeView}
        onNavigate={setActiveView}
        onNewAnalysis={newAnalysis}
        hasDatasets={hasDatasets}
      />

      <main className="flex-1 flex flex-col min-w-0">
        <header className="px-6 py-4 border-b border-ink-300/40 bg-white flex items-center justify-between">
          <div>
            <h1 className="text-base font-semibold text-ink-900 flex items-center gap-2">
              <Sparkles size={16} className="text-brand-600" /> AI Data Analyst
            </h1>
            <p className="text-xs text-ink-500">Ask questions. Discover insights. Analyze your data.</p>
          </div>
          {selectedIds.length > 0 && (
            <p className="text-xs text-ink-500">
              Active: <strong className="text-ink-900">{selectedIds.length}</strong> dataset{selectedIds.length > 1 ? 's' : ''}
            </p>
          )}
        </header>

        <div className="flex-1 overflow-hidden">
          {activeView === 'chat' && (
            <Chat messages={messages} loading={chatLoading} error={chatError} onAsk={ask} disabled={selectedIds.length === 0} />
          )}

          {activeView !== 'chat' && (
            <div className="h-full overflow-y-auto px-6 py-6">
              {activeView === 'datasets' && (
                <div className="space-y-6 max-w-3xl">
                  <FileUpload onUploaded={handleUploaded} />
                  {datasets.length > 0 && (
                    <div>
                      <p className="text-sm font-medium text-ink-900 mb-3">Uploaded datasets ({datasets.length})</p>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {datasets.map((d) => (
                          <DatasetCard key={d.dataset_id} dataset={d} selected={selectedIds.includes(d.dataset_id)} onToggle={toggleSelect} />
                        ))}
                      </div>
                    </div>
                  )}
                  {selectedDetail && (
                    <div>
                      <p className="text-sm font-medium text-ink-900 mb-3">Preview: {selectedDetail.dataset.filename}</p>
                      <DataPreview preview={selectedDetail.preview} />
                    </div>
                  )}
                </div>
              )}

              {activeView !== 'datasets' && !primaryDatasetId && (
                <ErrorState message="Upload and select a dataset first to view this section." />
              )}

              {activeView !== 'datasets' && primaryDatasetId && panelLoading && <LoadingState label="Crunching the numbers…" />}
              {activeView !== 'datasets' && primaryDatasetId && panelError && <ErrorState message={panelError} onRetry={() => loadPanel(activeView)} />}

              {!panelLoading && !panelError && (
                <>
                  {activeView === 'profile' && <DataProfile profile={profile} />}
                  {activeView === 'quality' && <DataQuality quality={quality} />}
                  {activeView === 'dashboard' && <Dashboard dashboard={dashboard} />}
                  {activeView === 'insights' && insights && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {insights.insights.map((ins, i) => <InsightCard key={i} insight={ins} />)}
                    </div>
                  )}
                  {activeView === 'anomalies' && anomalies && (
                    <div className="space-y-4 max-w-3xl">
                      <div className="card p-4 text-sm text-ink-700">{anomalies.explanation}</div>
                      <AnomalyTable anomalies={anomalies.anomalies} />
                    </div>
                  )}
                  {activeView === 'forecast' && <div className="max-w-3xl"><ForecastChart forecast={forecast} /></div>}
                  {activeView === 'reports' && primaryDatasetId && (
                    <div className="max-w-3xl">
                      <ReportExport datasetId={primaryDatasetId} sessionId={selectedIds.join(',')} />
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
