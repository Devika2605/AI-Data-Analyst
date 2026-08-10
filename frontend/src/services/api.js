import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

export async function uploadDataset(file, onProgress) {
  const form = new FormData()
  form.append('file', file)
  const res = await api.post('/datasets/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) onProgress(Math.round((evt.loaded / evt.total) * 100))
    },
  })
  return res.data
}

export async function listDatasets() {
  const res = await api.get('/datasets')
  return res.data.datasets
}

export async function getDataset(datasetId) {
  const res = await api.get(`/datasets/${datasetId}`)
  return res.data
}

export async function getProfile(datasetId) {
  const res = await api.get(`/datasets/${datasetId}/profile`)
  return res.data
}

export async function getQuality(datasetId) {
  const res = await api.get(`/datasets/${datasetId}/quality`)
  return res.data
}

export async function sendChat(sessionId, message, datasetIds) {
  const res = await api.post('/chat', { session_id: sessionId, message, dataset_ids: datasetIds })
  return res.data
}

export async function detectAnomalies(datasetId, method = 'isolation_forest', column = null) {
  const res = await api.post('/anomalies', { dataset_id: datasetId, method, column })
  return res.data
}

export async function getForecast(datasetId, horizon = 30, dateColumn = null, targetColumn = null) {
  const res = await api.post('/forecast', {
    dataset_id: datasetId, horizon, date_column: dateColumn, target_column: targetColumn,
  })
  return res.data
}

export async function getInsights(datasetId) {
  const res = await api.post('/insights', { dataset_id: datasetId })
  return res.data
}

export async function generateDashboard(datasetId) {
  const res = await api.post('/dashboard/generate', { dataset_id: datasetId })
  return res.data
}

export async function exportReport(datasetId, sessionId, options = {}) {
  const res = await api.post('/reports/export', {
    dataset_id: datasetId,
    session_id: sessionId,
    include_anomalies: options.includeAnomalies ?? true,
    include_forecast: options.includeForecast ?? true,
    include_insights: options.includeInsights ?? true,
  })
  return res.data
}

export async function checkHealth() {
  const res = await api.get('/health')
  return res.data
}

export default api
