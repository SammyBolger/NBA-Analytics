import { useState, useCallback, useMemo } from 'react'
import { useApi, postApi } from '../hooks/useApi'
import { Target, TrendingUp, Shield, Zap, ChevronDown, ChevronUp, Check, RefreshCw } from 'lucide-react'

function parseStatus(status) {
  if (!status) return { type: 'scheduled', label: 'SCHEDULED' }
  const s = status.toLowerCase()
  if (s.includes('qtr') || s.includes('half') || s.includes('ot') || s.includes('progress'))
    return { type: 'live', label: status }
  if (s.includes('final'))
    return { type: 'final', label: 'FINAL' }
  if (/^\d{4}-\d{2}-\d{2}T/.test(status)) {
    try {
      const d = new Date(status)
      return { type: 'scheduled', label: d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) }
    } catch { return { type: 'scheduled', label: 'SCHEDULED' } }
  }
  return { type: 'scheduled', label: status || 'SCHEDULED' }
}

function getGameTime(status) {
  if (/^\d{4}-\d{2}-\d{2}T/.test(status || '')) {
    try { return new Date(status).getTime() } catch {}
  }
  return 0
}

function ConfidenceBadge({ confidence }) {
  const colors = {
    High: { bg: 'rgba(0,214,143,0.15)', text: 'var(--green)' },
    Medium: { bg: 'rgba(255,159,67,0.15)', text: 'var(--orange)' },
    Low: { bg: 'rgba(255,77,106,0.1)', text: 'var(--text-secondary)' },
  }
  const c = colors[confidence] || colors.Low
  return (
    <span style={{ padding: '3px 10px', borderRadius: 20, fontSize: 11, fontWeight: 700, background: c.bg, color: c.text }}>
      {confidence}
    </span>
  )
}

function ProbBar({ homeProb, awayProb, homeTeam, awayTeam }) {
  const hp = Math.round(homeProb * 100)
  const ap = Math.round(awayProb * 100)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-secondary)', marginBottom: 4 }}>
        <span>{awayTeam} {ap}%</span>
        <span>{homeTeam} {hp}%</span>
      </div>
      <div style={{ display: 'flex', height: 8, borderRadius: 4, overflow: 'hidden', background: 'var(--bg-secondary)' }}>
        <div style={{ width: `${ap}%`, background: 'var(--red)', transition: 'width 0.3s' }} />
        <div style={{ width: `${hp}%`, background: 'var(--accent)', transition: 'width 0.3s' }} />
      </div>
    </div>
  )
}

function PickButton({ team, odds, gameId, onPick, isPicked, isOtherPicked, loading }) {
  const handleClick = async (e) => {
    e.stopPropagation()
    if (loading) return
    await onPick({
      game_id: gameId,
      pick_type: 'moneyline',
      selection: `${team.full_name} ML`,
      odds: odds,
      stake: 10,
      notes: `Model moneyline: ${odds > 0 ? '+' : ''}${odds}`,
    })
  }

  return (
    <button
      onClick={handleClick}
      disabled={loading}
      style={{
        padding: '6px 14px', fontSize: 11, fontWeight: 700,
        background: isPicked ? 'rgba(0,214,143,0.2)' : isOtherPicked ? 'rgba(255,255,255,0.04)' : 'rgba(79,109,255,0.12)',
        color: isPicked ? 'var(--green)' : isOtherPicked ? 'var(--text-secondary)' : 'var(--accent)',
        border: `1px solid ${isPicked ? 'rgba(0,214,143,0.4)' : isOtherPicked ? 'rgba(255,255,255,0.08)' : 'rgba(79,109,255,0.3)'}`,
        borderRadius: 8, cursor: 'pointer',
        display: 'flex', alignItems: 'center', gap: 4,
        transition: 'all 0.2s',
        opacity: loading ? 0.5 : 1,
      }}
    >
      {isPicked ? <Check size={12} /> : isOtherPicked ? <RefreshCw size={10} /> : null}
      {isPicked ? 'Locked' : loading ? '...' : isOtherPicked ? 'Switch' : `Pick ${team.abbreviation}`}
    </button>
  )
}

export default function OddsPage() {
  const { data: predictions, loading } = useApi('/api/model-odds', { refreshInterval: 30 })
  const { data: picksData, refetch: refetchPicks } = useApi('/api/picks')
  const [expanded, setExpanded] = useState({})
  const [filter, setFilter] = useState('all')
  const [savingGame, setSavingGame] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)

  const existingPicks = useMemo(() => {
    const map = {}
    const picks = picksData?.picks || []
    for (const p of picks) {
      if (p.pick_type === 'moneyline' && p.game_id) {
        map[p.game_id] = p.selection
      }
    }
    return map
  }, [picksData])

  const preGameOnly = useMemo(() => {
    const games = (predictions || []).filter(g => {
      const parsed = parseStatus(g.status)
      return parsed.type === 'scheduled'
    })
    return [...games].sort((a, b) => getGameTime(a.status) - getGameTime(b.status))
  }, [predictions])

  const filtered = preGameOnly.filter(g => {
    if (filter === 'high') return g.confidence === 'High'
    if (filter === 'medium') return g.confidence === 'Medium' || g.confidence === 'High'
    return true
  })

  const highCount = preGameOnly.filter(g => g.confidence === 'High').length
  const avgProb = preGameOnly.length ? (preGameOnly.reduce((s, g) => s + g.model_pick_prob, 0) / preGameOnly.length * 100).toFixed(1) : 0

  const handlePick = useCallback(async (pickData) => {
    setSavingGame(pickData.game_id)
    try {
      const result = await postApi('/api/picks', pickData)
      await refetchPicks()
      const action = result.status === 'updated' ? 'Changed to' : 'Picked'
      setSuccessMsg(`${action}: ${pickData.selection}`)
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (e) {
      alert('Error saving pick')
    } finally {
      setSavingGame(null)
    }
  }, [refetchPicks])

  return (
    <div>
      <div className="page-header">
        <h1>Odds & Model Picks</h1>
        <p>ML-predicted winners with computed moneylines &bull; Pre-game picks only</p>
      </div>

      {successMsg && (
        <div style={{
          padding: '10px 16px', marginBottom: 16, borderRadius: 8,
          background: 'rgba(0,214,143,0.12)', border: '1px solid rgba(0,214,143,0.3)',
          color: 'var(--green)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <Check size={16} /> {successMsg}
        </div>
      )}

      <div className="grid-3" style={{ marginBottom: 24 }}>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgba(79,109,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Target size={20} color="var(--accent)" />
            </div>
            <div>
              <div className="stat-value">{preGameOnly.length}</div>
              <div className="stat-label">Games Available</div>
            </div>
          </div>
        </div>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgba(0,214,143,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Zap size={20} color="var(--green)" />
            </div>
            <div>
              <div className="stat-value">{highCount}</div>
              <div className="stat-label">High Confidence</div>
            </div>
          </div>
        </div>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgba(255,159,67,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <TrendingUp size={20} color="var(--orange)" />
            </div>
            <div>
              <div className="stat-value">{avgProb}%</div>
              <div className="stat-label">Avg Pick Prob</div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {[['all', 'All Games'], ['medium', 'Medium+'], ['high', 'High Only']].map(([key, label]) => (
          <button key={key} className={`btn btn-sm ${filter === key ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setFilter(key)}>
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>Analyzing games...</div>
      ) : filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🏀</div>
          <h3 style={{ marginBottom: 8 }}>No Pre-Game Picks Available</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>All games have started or finished. Check back tomorrow for new predictions.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {filtered.map(game => {
            const parsed = parseStatus(game.status)
            const isExpanded = expanded[game.game_id]
            const currentPick = existingPicks[game.game_id]
            const awaySelection = `${game.away_team?.full_name} ML`
            const homeSelection = `${game.home_team?.full_name} ML`
            const awayPicked = currentPick === awaySelection
            const homePicked = currentPick === homeSelection
            const hasPick = awayPicked || homePicked
            const isSaving = savingGame === game.game_id

            return (
              <div key={game.game_id} className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div
                  style={{ padding: '16px 20px', cursor: 'pointer' }}
                  onClick={() => setExpanded(p => ({ ...p, [game.game_id]: !p[game.game_id] }))}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <span className="badge badge-scheduled" style={{ fontSize: 10 }}>{parsed.label}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{game.date}</span>
                      {hasPick && (
                        <span style={{
                          fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 12,
                          background: 'rgba(0,214,143,0.15)', color: 'var(--green)',
                          display: 'flex', alignItems: 'center', gap: 4,
                        }}>
                          <Check size={10} /> Pick Locked
                        </span>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <ConfidenceBadge confidence={game.confidence} />
                      {isExpanded ? <ChevronUp size={16} color="var(--text-secondary)" /> : <ChevronDown size={16} color="var(--text-secondary)" />}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                        <div style={{
                          width: 36, height: 36, borderRadius: 8,
                          background: game.away_team?.primary_color || '#333',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 11, fontWeight: 800, color: '#fff'
                        }}>{game.away_team?.abbreviation}</div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 14 }}>{game.away_team?.full_name}</div>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                            ML: <span style={{ fontWeight: 700, color: game.away_moneyline > 0 ? 'var(--green)' : '#fff' }}>
                              {game.away_moneyline > 0 ? '+' : ''}{game.away_moneyline}
                            </span>
                            <span style={{ marginLeft: 8 }}>{(game.away_win_prob * 100).toFixed(1)}%</span>
                          </div>
                        </div>
                        <PickButton
                          team={game.away_team}
                          odds={game.away_moneyline}
                          gameId={game.game_id}
                          onPick={handlePick}
                          isPicked={awayPicked}
                          isOtherPicked={homePicked}
                          loading={isSaving}
                        />
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{
                          width: 36, height: 36, borderRadius: 8,
                          background: game.home_team?.primary_color || '#333',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 11, fontWeight: 800, color: '#fff'
                        }}>{game.home_team?.abbreviation}</div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 14 }}>{game.home_team?.full_name}</div>
                          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                            ML: <span style={{ fontWeight: 700, color: game.home_moneyline > 0 ? 'var(--green)' : '#fff' }}>
                              {game.home_moneyline > 0 ? '+' : ''}{game.home_moneyline}
                            </span>
                            <span style={{ marginLeft: 8 }}>{(game.home_win_prob * 100).toFixed(1)}%</span>
                          </div>
                        </div>
                        <PickButton
                          team={game.home_team}
                          odds={game.home_moneyline}
                          gameId={game.game_id}
                          onPick={handlePick}
                          isPicked={homePicked}
                          isOtherPicked={awayPicked}
                          loading={isSaving}
                        />
                      </div>
                    </div>

                    <div style={{ width: 1, height: 60, background: 'var(--border)' }} />

                    <div style={{ minWidth: 120, textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 1 }}>Model Pick</div>
                      <div style={{
                        width: 44, height: 44, borderRadius: 10, margin: '0 auto 6px',
                        background: game.model_pick?.primary_color || '#333',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 13, fontWeight: 800, color: '#fff',
                        boxShadow: '0 0 12px ' + (game.model_pick?.primary_color || '#333') + '60',
                      }}>{game.model_pick?.abbreviation}</div>
                      <div style={{ fontSize: 18, fontWeight: 800 }}>{(game.model_pick_prob * 100).toFixed(1)}%</div>
                    </div>
                  </div>

                  <div style={{ marginTop: 12 }}>
                    <ProbBar
                      homeProb={game.home_win_prob}
                      awayProb={game.away_win_prob}
                      homeTeam={game.home_team?.abbreviation}
                      awayTeam={game.away_team?.abbreviation}
                    />
                  </div>
                </div>

                {isExpanded && (
                  <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)', background: 'rgba(0,0,0,0.15)' }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12, textTransform: 'uppercase', letterSpacing: 1 }}>
                      Team Stats (Last 10 Games)
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 12, fontSize: 13 }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontWeight: 700, marginBottom: 8 }}>{game.away_team?.abbreviation}</div>
                        {game.away_stats ? (
                          <>
                            <div style={{ marginBottom: 4 }}>Win%: <strong>{(game.away_stats.win_pct * 100).toFixed(0)}%</strong></div>
                            <div style={{ marginBottom: 4 }}>PPG: <strong>{game.away_stats.avg_scored}</strong></div>
                            <div style={{ marginBottom: 4 }}>Opp PPG: <strong>{game.away_stats.avg_allowed}</strong></div>
                            <div>Net: <strong className={game.away_stats.net_rating >= 0 ? 'positive' : 'negative'}>{game.away_stats.net_rating > 0 ? '+' : ''}{game.away_stats.net_rating}</strong></div>
                          </>
                        ) : <div style={{ color: 'var(--text-secondary)' }}>No data yet</div>}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <div style={{ width: 1, height: '100%', background: 'var(--border)' }} />
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontWeight: 700, marginBottom: 8 }}>{game.home_team?.abbreviation}</div>
                        {game.home_stats ? (
                          <>
                            <div style={{ marginBottom: 4 }}>Win%: <strong>{(game.home_stats.win_pct * 100).toFixed(0)}%</strong></div>
                            <div style={{ marginBottom: 4 }}>PPG: <strong>{game.home_stats.avg_scored}</strong></div>
                            <div style={{ marginBottom: 4 }}>Opp PPG: <strong>{game.home_stats.avg_allowed}</strong></div>
                            <div>Net: <strong className={game.home_stats.net_rating >= 0 ? 'positive' : 'negative'}>{game.home_stats.net_rating > 0 ? '+' : ''}{game.home_stats.net_rating}</strong></div>
                          </>
                        ) : <div style={{ color: 'var(--text-secondary)' }}>No data yet</div>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
