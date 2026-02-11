import { useState, useMemo } from 'react'
import { useApi } from '../hooks/useApi'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

function parseStatus(status) {
  if (!status) return { type: 'scheduled', label: 'SCHEDULED', sortKey: 1 }
  const s = status.toLowerCase()
  if (s.includes('qtr') || s.includes('half') || s.includes('ot') || s.includes('progress'))
    return { type: 'live', label: status, sortKey: 0 }
  if (s.includes('final'))
    return { type: 'final', label: 'FINAL', sortKey: 2 }
  if (/^\d{4}-\d{2}-\d{2}T/.test(status)) {
    try {
      const d = new Date(status)
      return { type: 'scheduled', label: d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }), sortKey: 1, time: d }
    } catch { return { type: 'scheduled', label: 'SCHEDULED', sortKey: 1 } }
  }
  return { type: 'scheduled', label: status || 'SCHEDULED', sortKey: 1 }
}

function getGameTime(game) {
  const status = game.status || ''
  if (/^\d{4}-\d{2}-\d{2}T/.test(status)) {
    try { return new Date(status).getTime() } catch {}
  }
  return 0
}

export default function GamecenterPage() {
  const { data: games, loading } = useApi('/api/games/today', { refreshInterval: 15 })
  const [selectedGame, setSelectedGame] = useState(null)

  const sortedGames = useMemo(() => {
    if (!games || games.length === 0) return []
    return [...games].sort((a, b) => {
      const pa = parseStatus(a.status)
      const pb = parseStatus(b.status)
      if (pa.sortKey !== pb.sortKey) return pa.sortKey - pb.sortKey
      if (pa.sortKey === 1) {
        return getGameTime(a) - getGameTime(b)
      }
      return 0
    })
  }, [games])

  const liveGames = sortedGames.filter(g => parseStatus(g.status).type === 'live')
  const scheduledGames = sortedGames.filter(g => parseStatus(g.status).type === 'scheduled')
  const finalGames = sortedGames.filter(g => parseStatus(g.status).type === 'final')

  return (
    <div>
      <div className="page-header">
        <h1>Gamecenter</h1>
        <p>Today's games &bull; Auto-refreshing every 15 seconds</p>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>Loading...</div>}

      {!loading && sortedGames.length === 0 && (
        <div className="card" style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>🏀</div>
          <h3 style={{ marginBottom: 8 }}>No Games Today</h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14 }}>Check back on a game day to see live scores and results.</p>
        </div>
      )}

      {liveGames.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="pulse" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--red)', display: 'inline-block' }}></span>
            Live ({liveGames.length})
          </h2>
          <div className="grid-2">
            {liveGames.map(game => (
              <GameCard key={game.id} game={game} selected={selectedGame === game.id} onClick={() => setSelectedGame(selectedGame === game.id ? null : game.id)} />
            ))}
          </div>
        </div>
      )}

      {scheduledGames.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12 }}>
            Upcoming ({scheduledGames.length})
          </h2>
          <div className="grid-2">
            {scheduledGames.map(game => (
              <GameCard key={game.id} game={game} selected={selectedGame === game.id} onClick={() => setSelectedGame(selectedGame === game.id ? null : game.id)} />
            ))}
          </div>
        </div>
      )}

      {finalGames.length > 0 && (
        <div style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 12, color: 'var(--text-secondary)' }}>
            Final ({finalGames.length})
          </h2>
          <div className="grid-2">
            {finalGames.map(game => (
              <GameCard key={game.id} game={game} selected={selectedGame === game.id} onClick={() => setSelectedGame(selectedGame === game.id ? null : game.id)} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function GameCard({ game, selected, onClick }) {
  const parsed = parseStatus(game.status)
  const isLive = parsed.type === 'live'
  const isFinal = parsed.type === 'final'
  const momentum = game.momentum || []

  return (
    <div className="card" onClick={onClick} style={{ cursor: 'pointer', borderColor: isLive ? 'var(--red)' : selected ? 'var(--accent)' : undefined, padding: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px', borderBottom: '1px solid var(--border)' }}>
        <span className={`badge ${isLive ? 'badge-live' : isFinal ? 'badge-final' : 'badge-scheduled'}`}>
          {isLive && <span className="pulse" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--red)', marginRight: 6, display: 'inline-block' }}></span>}
          {parsed.label}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{game.date}</span>
      </div>

      <div style={{ padding: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 32, height: 32, borderRadius: 6, background: game.visitor_team?.primary_color || '#333', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 800, color: '#fff' }}>
              {game.visitor_team?.abbreviation}
            </div>
            <span style={{ fontWeight: 600 }}>{game.visitor_team?.full_name || game.visitor_team?.name || 'Away'}</span>
          </div>
          <span style={{ fontSize: 24, fontWeight: 800 }}>{game.visitor_team_score}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 32, height: 32, borderRadius: 6, background: game.home_team?.primary_color || '#333', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 10, fontWeight: 800, color: '#fff' }}>
              {game.home_team?.abbreviation}
            </div>
            <span style={{ fontWeight: 600 }}>{game.home_team?.full_name || game.home_team?.name || 'Home'}</span>
          </div>
          <span style={{ fontSize: 24, fontWeight: 800 }}>{game.home_team_score}</span>
        </div>
      </div>

      {selected && momentum.length > 0 && (
        <div style={{ padding: '8px 16px 16px', borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>MOMENTUM</div>
          <ResponsiveContainer width="100%" height={100}>
            <LineChart data={momentum}>
              <XAxis dataKey="period" tick={{ fontSize: 10, fill: '#888' }} />
              <YAxis tick={{ fontSize: 10, fill: '#888' }} />
              <Tooltip contentStyle={{ background: '#1a1a3e', border: 'none', borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="home" stroke={game.home_team?.primary_color || '#4f6dff'} strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="visitor" stroke={game.visitor_team?.primary_color || '#ff4d6a'} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
