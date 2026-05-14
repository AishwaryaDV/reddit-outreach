import { NavLink, useLocation } from 'react-router-dom'

const nav = [
  { to: '/', label: 'Feed' },
  { to: '/queue', label: 'Queue' },
  { to: '/tracker', label: 'Tracker' },
  { to: '/settings', label: 'Settings' },
]

export default function Layout({ children }) {
  const { pathname } = useLocation()
  const isReview = pathname.startsWith('/review/')

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0a0a]">
      <header className="border-b border-white/8 px-6 py-4 flex items-center gap-8">
        <span className="text-white font-semibold tracking-tight">
          Reddit Outreach
        </span>
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
