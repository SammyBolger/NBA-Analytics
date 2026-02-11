import { useState } from 'react'
import { useApi, postApi } from '../hooks/useApi'
import { Brain, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react'

function RetrainResults({ result }) {
  if (!result) return null
  if (result.error) {
    return (
      <div className="card" style={{ marginBottom: 20, borderColor: 'var(--red)' }}>
        <h3 style={{ fontSize: 14, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--red)' }}>
          <AlertCircle size={16} /> Training Failed
        </h3>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{result.error}</p>
      </div>
    )
  }

  const models = Object.entries(result).filter(([key]) => key !== 'error')

  return (
    <div className="card" style={{ marginBottom: 20, borderColor: 'var(--green)' }}>
      <h3 style={{ fontSize: 14, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
        <CheckCircle size={16} color="var(--green)" /> Training Complete
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
        {models.map(([name, data]) => {
          const isSuccess = data && !data.error && data.status !== 'no_data'
          return (
            <div key={name} style={{
              padding: 12, borderRadius: 8,
              background: isSuccess ? 'rgba(0,214,143,0.06)' : 'rgba(255,159,67,0.06)',
              border: `1px solid ${isSuccess ? 'rgba(0,214,143,0.15)' : 'rgba(255,159,67,0.15)'}`,
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 6, textTransform: 'capitalize' }}>
                {name.replace(/_/g, ' ')}
              </div>
              {isSuccess ? (
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.8 }}>
                  {data.accuracy != null && <div>Accuracy: <strong style={{ color: 'var(--green)' }}>{(data.accuracy * 100).toFixed(1)}%</strong></div>}
                  {data.brier_score != null && <div>Brier Score: <strong>{data.brier_score.toFixed(4)}</strong></div>}
                  {data.mae != null && <div>MAE: <strong>{data.mae.toFixed(2)}</strong></div>}
                  {data.samples != null && <div>Samples: {data.samples}</div>}
                  {data.sample_size != null && <div>Samples: {data.sample_size}</div>}
                </div>
              ) : (
                <div style={{ fontSize: 11, color: 'var(--orange)' }}>
                  {data?.error || data?.message || 'Insufficient data'}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default function ModelHealthPage() {
  const { data, loading, refetch } = useApi('/api/model/health')
  const [retraining, setRetraining] = useState(false)
  const [retrainResult, setRetrainResult] = useState(null)

  const handleRetrain = async () => {
    setRetraining(true)
    try {
      const result = await postApi('/api/model/retrain', {})
      setRetrainResult(result)
      refetch()
    } catch (e) {
      setRetrainResult({ error: e.message })
    }
    setRetraining(false)
  }

  const models = data?.models || {}

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Model Health</h1>
          <p>Monitor model performance and trigger retraining</p>
        </div>
        <button className="btn btn-primary" onClick={handleRetrain} disabled={retraining}>
          <RefreshCw size={16} className={retraining ? 'pulse' : ''} />
          {retraining ? 'Training...' : 'Retrain All Models'}
        </button>
      </div>

      <RetrainResults result={retrainResult} />

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>Loading model metrics...</div>
      ) : (
        <div className="grid-2">
          {Object.entries(models).length === 0 ? (
            <div className="card" style={{ gridColumn: 'span 2', textAlign: 'center', padding: 40 }}>
              <Brain size={48} color="var(--text-secondary)" style={{ marginBottom: 12 }} />
              <h3 style={{ marginBottom: 8 }}>No Models Trained Yet</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginBottom: 16 }}>
                Click "Retrain All Models" to train the baseline models using available data.
              </p>
            </div>
          ) : (
            Object.entries(models).map(([name, metrics]) => (
              <div key={name} className="card">
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 10,
                    background: name.includes('win') ? 'rgba(79,109,255,0.15)' : 'rgba(0,214,143,0.15)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    <Brain size={20} color={name.includes('win') ? 'var(--accent)' : 'var(--green)'} />
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 15 }}>{formatModelName(name)}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                      {name.includes('win') ? 'Logistic Regression' : 'Linear Regression'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  {Object.entries(metrics).map(([metric, info]) => (
                    <div key={metric}>
                      <div className="stat-label">{formatMetricName(metric)}</div>
                      <div style={{ fontSize: 24, fontWeight: 800 }}>
                        {formatMetricValue(metric, info.value)}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2 }}>
                        n={info.sample_size}
                      </div>
                    </div>
                  ))}
                </div>

                {Object.values(metrics)[0]?.trained_at && (
                  <div style={{ marginTop: 12, fontSize: 11, color: 'var(--text-secondary)' }}>
                    Last trained: {new Date(Object.values(metrics)[0].trained_at).toLocaleString()}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}

      <div className="card" style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 12, color: 'var(--text-secondary)' }}>MODEL DETAILS</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
          <div>
            <h4 style={{ fontWeight: 600, marginBottom: 8 }}>Win Probability Model</h4>
            <ul style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 2, paddingLeft: 16 }}>
              <li>Algorithm: Logistic Regression</li>
              <li>Features: Win%, Net Rating, Avg Scored, FG%</li>
              <li>Target: Home team win (binary)</li>
              <li>Metric: Brier Score (lower is better)</li>
              <li>Home court advantage factor included</li>
            </ul>
          </div>
          <div>
            <h4 style={{ fontWeight: 600, marginBottom: 8 }}>Player Prop Models</h4>
            <ul style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 2, paddingLeft: 16 }}>
              <li>Algorithm: Linear Regression</li>
              <li>Features: Rolling averages (PTS, REB, AST, FG%, 3PM)</li>
              <li>Targets: Points, Rebounds, Assists</li>
              <li>Metric: MAE (lower is better)</li>
              <li>Uses last 10 games rolling window</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

function formatModelName(name) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatMetricName(name) {
  const map = { brier_score: 'Brier Score', accuracy: 'Accuracy', mae: 'Mean Abs Error' }
  return map[name] || name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function formatMetricValue(name, value) {
  if (name === 'accuracy') return `${(value * 100).toFixed(1)}%`
  return value?.toFixed(4)
}
