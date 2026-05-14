import { NavLink, useLocation, useNavigate } from 'react-router-dom'

const nav = [
  { to: '/', label: 'Feed' },
  { to: '/queue', label: 'Queue' },
  { to: '/tracker', label: 'Tracker' },
  { to: '/settings', label: 'Settings' },
]

export default function Layout({ children }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const isReview = pathname.startsWith('/review/')
  const isRoot = pathname === '/'

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <header className="border-b border-white/8 px-6 py-4 flex items-center gap-8">
        <span className="text-white font-semibold tracking-tight">
          Reddit Outreach
        </span>
        {!isRoot && (
          <button
            onClick={() => navigate('/')}
            style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12.5, color: '#7a7a7a', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
            Feed
          </button>
        )}
        <nav className="flex gap-1">
          {nav.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-white/10 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className={isReview ? 'flex-1 px-6 py-6 w-full' : 'flex-1 px-3 py-6 max-w-6xl mx-auto w-full'}>
        {children}
      </main>
    </div>
  )
}
