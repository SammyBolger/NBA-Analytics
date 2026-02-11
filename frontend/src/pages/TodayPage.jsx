import { useState, useMemo } from 'react'
import { useApi } from '../hooks/useApi'
import { Activity, Trophy, ChevronLeft, ChevronRight, Calendar } from 'lucide-react'

function isFinal(status) {
  if (!status) return false
  return status.toLowerCase().includes('final')
}

function isLive(status) {
  if (!status) return false
  const s = status.toLowerCase()
  return s.includes('qtr') || s.includes('half') || s.includes('ot') || s.includes('progress')
}

function MiniGameRow({ game }) {
  const final_ = isFinal(game.status)
  const live = isLive(game.status)
  const homeWon = final_ && game.home_team_score > game.visitor_team_score
  const awayWon = final_ && game.visitor_team_score > game.home_team_score

  let statusStr = null
  if (final_) {
    statusStr = 'F'
  } else if (live) {
    statusStr = game.status
  } else if (/^\d{4}-\d{2}-\d{2}T/.test(game.status || '')) {
    try {
      statusStr = new Date(game.status).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    } catch { statusStr = 'TBD' }
  }

  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '10px 14px', borderBottom: '1px solid var(--border)',
      fontSize: 13,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
        <span style={{
          fontWeight: awayWon ? 700 : 400,
          color: awayWon ? '#fff' : 'var(--text-secondary)',
          minWidth: 36,
        }}>{game.visitor_team?.abbreviation}</span>
        <span style={{ fontWeight: awayWon ? 700 : 400, minWidth: 28, textAlign: 'right' }}>
          {final_ || live ? (game.visitor_team_score ?? '-') : '-'}
        </span>
      </div>
      <span style={{ color: 'var(--text-secondary)', fontSize: 11, margin: '0 8px' }}>@</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, justifyContent: 'flex-end' }}>
        <span style={{ fontWeight: homeWon ? 700 : 400, minWidth: 28 }}>
          {final_ || live ? (game.home_team_score ?? '-') : '-'}
        </span>
        <span style={{
          fontWeight: homeWon ? 700 : 400,
          color: homeWon ? '#fff' : 'var(--text-secondary)',
          minWidth: 36, textAlign: 'right',
        }}>{game.home_team?.abbreviation}</span>
      </div>
      {statusStr && (
        <span style={{
          marginLeft: 10, fontSize: 9, padding: '2px 6px', borderRadius: 4,
          fontWeight: 600,
          background: live ? 'rgba(255,77,106,0.15)' : final_ ? 'rgba(255,255,255,0.06)' : 'rgba(255,159,67,0.12)',
          color: live ? 'var(--red)' : final_ ? 'var(--text-secondary)' : 'var(--orange)',
          minWidth: 24, textAlign: 'center',
        }}>
          {live && <span style={{width:5,height:5,borderRadius:'50%',background:'var(--red)',marginRight:3,display:'inline-block'}}></span>}
          {statusStr}
        </span>
      )}
    </div>
  )
}

function GameCalendar({ calendarData }) {
  const [monthOffset, setMonthOffset] = useState(0)
  const [selectedDate, setSelectedDate] = useState(null)

  const now = new Date()
  const viewDate = new Date(now.getFullYear(), now.getMonth() + monthOffset, 1)
  const year = viewDate.getFullYear()
  const month = viewDate.getMonth()
  const monthName = viewDate.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const firstDow = new Date(year, month, 1).getDay()

  const dates = calendarData?.dates || {}
  const todayStr = now.toLocaleDateString('en-CA')

  const calendarDays = useMemo(() => {
    const days = []
    for (let i = 0; i < firstDow; i++) days.push(null)
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
      const games = dates[dateStr] || []
      days.push({ day: d, dateStr, games })
    }
    return days
  }, [dates, year, month, firstDow, daysInMonth])

  const selectedGames = selectedDate ? (dates[selectedDate] || []) : []

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Calendar size={20} /> Game Calendar
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button onClick={() => setMonthOffset(m => m - 1)} className="btn btn-secondary btn-sm" style={{ padding: '4px 8px' }}>
            <ChevronLeft size={16} />
          </button>
          <span style={{ fontSize: 14, fontWeight: 600, minWidth: 140, textAlign: 'center' }}>{monthName}</span>
          <button onClick={() => setMonthOffset(m => m + 1)} className="btn btn-secondary btn-sm" style={{ padding: '4px 8px' }}>
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
          borderBottom: '1px solid var(--border)',
        }}>
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
            <div key={d} style={{
              padding: '8px 4px', textAlign: 'center',
              fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)',
              textTransform: 'uppercase',
            }}>{d}</div>
          ))}
        </div>
        <div style={{
          display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)',
        }}>
          {calendarDays.map((cell, i) => {
            if (!cell) return <div key={`e-${i}`} style={{ padding: 8, minHeight: 56 }} />
            const isToday = cell.dateStr === todayStr
            const hasGames = cell.games.length > 0
            const isSelected = cell.dateStr === selectedDate
            const allFinal = hasGames && cell.games.every(g => isFinal(g.status))
            const hasLive = hasGames && cell.games.some(g => isLive(g.status))
            return (
              <div
                key={cell.dateStr}
                onClick={() => hasGames && setSelectedDate(isSelected ? null : cell.dateStr)}
                style={{
                  padding: '6px 4px', minHeight: 56,
                  borderTop: '1px solid var(--border)',
                  borderRight: (i + 1) % 7 !== 0 ? '1px solid var(--border)' : 'none',
                  cursor: hasGames ? 'pointer' : 'default',
                  background: isSelected ? 'rgba(79,109,255,0.12)' : isToday ? 'rgba(79,109,255,0.06)' : 'transparent',
                  transition: 'background 0.15s',
                }}
              >
                <div style={{
                  fontSize: 12, fontWeight: isToday ? 700 : 400,
                  color: isToday ? 'var(--accent)' : '#fff',
                  marginBottom: 4, textAlign: 'center',
                }}>
                  {cell.day}
                </div>
                {hasGames && (
                  <div style={{ textAlign: 'center' }}>
                    <div style={{
                      fontSize: 10, fontWeight: 600,
                      color: hasLive ? 'var(--red)' : allFinal ? 'var(--green)' : 'var(--orange)',
                      background: hasLive ? 'rgba(255,77,106,0.12)' : allFinal ? 'rgba(0,214,143,0.12)' : 'rgba(255,159,67,0.12)',
                      borderRadius: 4, padding: '2px 4px',
                      display: 'inline-block',
                    }}>
                      {cell.games.length} {cell.games.length === 1 ? 'game' : 'games'}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {selectedDate && (
        <div style={{ marginTop: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 12 }}>
            {new Date(selectedDate + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
          </h3>
          {selectedGames.length > 0 ? (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              {selectedGames.map(game => (
                <MiniGameRow key={game.id} game={game} />
              ))}
            </div>
          ) : (
            <div className="card" style={{ textAlign: 'center', padding: 24, color: 'var(--text-secondary)' }}>
              No games on this date
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function TodayPage() {
  const { data: status } = useApi('/api/status')
  const { data: picksData } = useApi('/api/picks')
  const { data: calendarData } = useApi('/api/games/calendar')
  const { data: games } = useApi('/api/games/today', { refreshInterval: 15 })

  const picks = (picksData?.picks || []).filter(p => p.pick_type === 'moneyline')
  const wins = picks.filter(p => p.result === 'win').length
  const losses = picks.filter(p => p.result === 'loss').length

  const todayCount = (games || []).length
  const liveCount = (games || []).filter(g => isLive(g.status)).length

  return (
    <div>
      <div className="page-header">
        <h1>Home</h1>
        <p>{new Date().toLocaleDateString('en-US', {weekday:'long', year:'numeric', month:'long', day:'numeric'})}</p>
      </div>

      {status && !status.has_api_key && (
        <div className="card" style={{ marginBottom: 20, borderColor: 'var(--orange)', background: 'rgba(255,159,67,0.08)' }}>
          <h3 style={{ color: 'var(--orange)', marginBottom: 8 }}>API Key Required</h3>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            Set the <code style={{ background: 'var(--bg-secondary)', padding: '2px 6px', borderRadius: 4 }}>BDL_API_KEY</code> environment variable with your BallDontLie API key to enable live data.
            Get a free key at <a href="https://www.balldontlie.io" target="_blank" rel="noreferrer">balldontlie.io</a>.
            The app is showing seed data for demonstration.
          </p>
        </div>
      )}

      <div className="grid-3" style={{ marginBottom: 24 }}>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgba(0,214,143,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Trophy size={20} color="var(--green)" />
            </div>
            <div>
              <div className="stat-value">{wins + losses > 0 ? `${wins}-${losses}` : '--'}</div>
              <div className="stat-label">My Record (W-L)</div>
            </div>
          </div>
        </div>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: 'rgba(79,109,255,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Activity size={20} color="var(--accent)" />
            </div>
            <div>
              <div className="stat-value">{todayCount}</div>
              <div className="stat-label">Games Today</div>
            </div>
          </div>
        </div>
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 42, height: 42, borderRadius: 10, background: liveCount > 0 ? 'rgba(255,77,106,0.15)' : 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {liveCount > 0 && <span className="pulse" style={{width:8,height:8,borderRadius:'50%',background:'var(--red)',display:'inline-block'}}></span>}
              {liveCount === 0 && <Activity size={20} color="var(--text-secondary)" />}
            </div>
            <div>
              <div className="stat-value" style={{ color: liveCount > 0 ? 'var(--red)' : 'var(--text-secondary)' }}>{liveCount}</div>
              <div className="stat-label">Live Now</div>
            </div>
          </div>
        </div>
      </div>

      {calendarData ? (
        <GameCalendar calendarData={calendarData} />
      ) : (
        <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-secondary)' }}>Loading calendar...</div>
      )}
    </div>
  )
}
