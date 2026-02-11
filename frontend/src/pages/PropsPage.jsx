import { Users, Clock } from 'lucide-react'

export default function PropsPage() {
  return (
    <div>
      <div className="page-header">
        <h1>Player Props</h1>
        <p>Individual player stat projections - feature in development</p>
      </div>

      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', minHeight: 400,
      }}>
        <div style={{
          background: 'rgba(79,109,255,0.08)', border: '1px solid rgba(79,109,255,0.2)',
          borderRadius: 16, padding: '48px 64px', textAlign: 'center', maxWidth: 480,
        }}>
          <div style={{
            width: 64, height: 64, borderRadius: 16,
            background: 'rgba(79,109,255,0.15)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 20px',
          }}>
            <Users size={32} color="var(--accent)" />
          </div>
          <h2 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8 }}>Coming Soon</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6, marginBottom: 16 }}>
            Player prop projections and over/under picks are currently in development.
            This feature will use ML models to project individual player stat lines.
          </p>
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            color: 'var(--text-secondary)', fontSize: 12,
          }}>
            <Clock size={14} />
            <span>Check back for updates</span>
          </div>
        </div>
      </div>
    </div>
  )
}
