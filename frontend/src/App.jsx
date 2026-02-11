import { Routes, Route, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { Activity, TrendingUp, Users, Brain, ClipboardList, Home, Info, ExternalLink, LogOut, User } from 'lucide-react'
import { useAuth, AuthProvider } from './contexts/AuthContext'
import AuthPage from './pages/AuthPage'
import TodayPage from './pages/TodayPage'
import GamecenterPage from './pages/GamecenterPage'
import OddsPage from './pages/OddsPage'
import PropsPage from './pages/PropsPage'
import ModelHealthPage from './pages/ModelHealthPage'
import PickTrackerPage from './pages/PickTrackerPage'
import AboutPage from './pages/AboutPage'

const navItems = [
  { path: '/', label: 'Home', icon: Home },
  { path: '/gamecenter', label: 'Gamecenter', icon: Activity },
  { path: '/odds', label: 'Odds & Lines', icon: TrendingUp },
  { path: '/props', label: 'Player Props', icon: Users },
  { path: '/models', label: 'Model Health', icon: Brain },
  { path: '/picks', label: 'Pick Tracker', icon: ClipboardList },
  { path: '/about', label: 'About', icon: Info },
]

function Sidebar() {
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  return (
    <div className="sidebar">
      <div style={{ padding: '0 20px', marginBottom: 32 }}>
        <div
          onClick={() => navigate('/')}
          style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}
        >
          <div style={{
            width: 36, height: 36, borderRadius: 8,
            background: 'linear-gradient(135deg, #4f6dff, #ff4d6a)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 900, fontSize: 14
          }}>NBA</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Analytics</div>
            <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>Sammy Bolger</div>
          </div>
        </div>
      </div>
      <nav>
        {navItems.map(item => {
          const Icon = item.icon
          const isActive = location.pathname === item.path
          return (
            <NavLink
              key={item.path}
              to={item.path}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '12px 20px', color: isActive ? '#fff' : 'var(--text-secondary)',
                background: isActive ? 'rgba(79,109,255,0.12)' : 'transparent',
                borderLeft: isActive ? '3px solid var(--accent)' : '3px solid transparent',
                fontSize: 14, fontWeight: isActive ? 600 : 400,
                textDecoration: 'none', transition: 'all 0.2s',
              }}
            >
              <Icon size={18} />
              {item.label}
            </NavLink>
          )
        })}
      </nav>
      <div style={{ position: 'absolute', bottom: 16, left: 0, right: 0, padding: '0 20px' }}>
        {user && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: '10px 12px', background: 'rgba(79,109,255,0.08)', borderRadius: 8,
            marginBottom: 8,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <User size={14} color="var(--accent)" />
              <span style={{ fontSize: 12, color: '#fff', fontWeight: 600 }}>{user.username}</span>
            </div>
            <button
              onClick={handleLogout}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--text-secondary)', padding: 4,
                display: 'flex', alignItems: 'center',
              }}
              title="Sign out"
            >
              <LogOut size={14} />
            </button>
          </div>
        )}
        <a
          href="https://sammybolger.com"
          target="_blank"
          rel="noreferrer"
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: 12, background: 'rgba(79,109,255,0.08)', borderRadius: 8,
            fontSize: 12, color: 'var(--accent)', textDecoration: 'none',
            transition: 'background 0.2s',
          }}
        >
          <ExternalLink size={14} />
          sammybolger.com
        </a>
      </div>
    </div>
  )
}

function AppContent() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: 'var(--bg-primary)',
      }}>
        <div style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
          <div style={{
            width: 56, height: 56, borderRadius: 14,
            background: 'linear-gradient(135deg, #4f6dff, #ff4d6a)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontWeight: 900, fontSize: 20, color: '#fff',
            margin: '0 auto 16px',
          }}>NBA</div>
          Loading...
        </div>
      </div>
    )
  }

  if (!user) {
    return <AuthPage />
  }

  return (
    <div className="layout">
      <Sidebar />
      <main className="main-content">
        <Routes>
          <Route path="/" element={<TodayPage />} />
          <Route path="/gamecenter" element={<GamecenterPage />} />
          <Route path="/odds" element={<OddsPage />} />
          <Route path="/props" element={<PropsPage />} />
          <Route path="/models" element={<ModelHealthPage />} />
          <Route path="/picks" element={<PickTrackerPage />} />
          <Route path="/about" element={<AboutPage />} />
        </Routes>
      </main>
    </div>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}
