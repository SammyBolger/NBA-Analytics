import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { Trophy, Trash2, CheckCircle, XCircle, Clock, History, ArrowLeft } from 'lucide-react'

export default function PickTrackerPage() {
  const { data, loading, refetch } = useApi('/api/picks')
  const [showHistory, setShowHistory] = useState(false)

  const allPicks = (data?.picks || []).filter(p => p.pick_type === 'moneyline')
  const activePicks = allPicks.filter(p => p.result === 'pending')
  const gradedPicks = allPicks.filter(p => p.result === 'win' || p.result === 'loss')

  const wins = gradedPicks.filter(p => p.result === 'win').length
  const losses = gradedPicks.filter(p => p.result === 'loss').length
  const graded = wins + losses
  const winRate = graded > 0 ? (wins / graded * 100).toFixed(1) : '--'

  const displayPicks = showHistory ? gradedPicks : activePicks

  const handleDelete = async (pickId) => {
    if (!confirm('Remove this pick?')) return
    try {
      await fetch(`/api/picks/${pickId}`, { method: 'DELETE', credentials: 'include' })
      refetch()
    } catch (e) {
      alert('Error removing pick')
    }
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>Pick Tracker</h1>
          <p>Track your moneyline team picks and win-loss record</p>
        </div>
      </div>

      <div className="grid-3" style={{ marginBottom: 24 }}>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: 'rgba(79,109,255,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 12px',
          }}>
            <Trophy size={24} color="var(--accent)" />
          </div>
          <div className="stat-value" style={{ fontSize: 32 }}>{wins}-{losses}</div>
          <div className="stat-label">Record (W-L)</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: 'rgba(0,214,143,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 12px',
          }}>
            <CheckCircle size={24} color="var(--green)" />
          </div>
          <div className="stat-value" style={{ fontSize: 32, color: winRate !== '--' ? 'var(--green)' : 'var(--text-secondary)' }}>
            {winRate === '--' ? '--' : `${winRate}%`}
          </div>
          <div className="stat-label">Win Rate</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: 'rgba(255,159,67,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 12px',
          }}>
            <Clock size={24} color="var(--orange)" />
          </div>
          <div className="stat-value" style={{ fontSize: 32 }}>{activePicks.length}</div>
          <div className="stat-label">Pending</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        <button
          className={`btn btn-sm ${!showHistory ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setShowHistory(false)}
        >
          <Clock size={14} /> Active Picks ({activePicks.length})
        </button>
        <button
          className={`btn btn-sm ${showHistory ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setShowHistory(true)}
        >
          <History size={14} /> Pick History ({gradedPicks.length})
        </button>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>Loading picks...</div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Team Selected</th>
                  <th>Odds</th>
                  <th>Result</th>
                  {!showHistory && <th></th>}
                </tr>
              </thead>
              <tbody>
                {displayPicks.map(pick => (
                  <tr key={pick.id}>
                    <td style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                      {pick.created_at ? new Date(pick.created_at).toLocaleDateString() : '-'}
                    </td>
                    <td style={{ fontWeight: 600 }}>
                      {pick.selection}
                    </td>
                    <td style={{ fontSize: 13 }}>
                      {pick.odds > 0 ? '+' : ''}{pick.odds}
                    </td>
                    <td>
                      {pick.result === 'win' ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--green)', fontWeight: 600 }}>
                          <CheckCircle size={14} /> W
                        </span>
                      ) : pick.result === 'loss' ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--red)', fontWeight: 600 }}>
                          <XCircle size={14} /> L
                        </span>
                      ) : (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: 'var(--text-secondary)' }}>
                          <Clock size={14} /> Pending
                        </span>
                      )}
                    </td>
                    {!showHistory && (
                      <td>
                        <button
                          onClick={() => handleDelete(pick.id)}
                          style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: 'var(--text-secondary)', padding: 4,
                          }}
                          title="Remove pick"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
                {displayPicks.length === 0 && (
                  <tr><td colSpan={showHistory ? 4 : 5} style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>
                    {showHistory
                      ? 'No graded picks yet. Picks are graded automatically when games finish.'
                      : 'No active picks. Head to the Odds & Lines page to make your team picks.'
                    }
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
