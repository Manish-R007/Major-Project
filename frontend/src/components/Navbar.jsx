import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

const ROLE_LABELS = {
  citizen: 'Claimant',
  village_official: 'Village Official',
  district_officer: 'District Officer',
  state_officer: 'State Nodal Officer',
  admin: 'Administrator',
}

const linkClass = ({ isActive }) =>
  `px-3 py-2 text-sm tracking-wide transition-colors border-b-2 ${
    isActive
      ? 'border-ochre-500 text-canopy-950 font-medium'
      : 'border-transparent text-canopy-700/70 hover:text-canopy-950'
  }`

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  return (
    <header className="sticky top-0 z-30 border-b border-canopy-900/10 bg-parchment-100/90 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-canopy-900 font-display text-sm text-parchment-100">
            FA
          </span>
          <div className="leading-tight">
            <p className="font-display text-base text-canopy-950">FRA Atlas &amp; DSS</p>
            <p className="text-[11px] uppercase tracking-[0.14em] text-canopy-700/70">
              Ministry of Tribal Affairs
            </p>
          </div>
        </div>

        <nav className="hidden items-center gap-1 md:flex">
          <NavLink to="/dashboard" className={linkClass}>Dashboard</NavLink>
          <NavLink to="/atlas" className={linkClass}>Atlas</NavLink>
          <NavLink to="/claims" className={linkClass}>Claims</NavLink>
          {user.role !== 'citizen' && (
            <NavLink to="/dss" className={linkClass}>DSS</NavLink>
          )}
          {(user.role === 'admin' || user.role === 'state_officer') && (
            <NavLink to="/users" className={linkClass}>Users</NavLink>
          )}
        </nav>

        <div className="flex items-center gap-4">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-canopy-950">{user.full_name}</p>
            <p className="font-mono text-[11px] text-canopy-700/70">
              {ROLE_LABELS[user.role] || user.role}
            </p>
          </div>
          <button
            onClick={() => { logout(); navigate('/login') }}
            className="rounded-full border border-canopy-900/20 px-4 py-1.5 text-sm text-canopy-900 transition hover:bg-canopy-900 hover:text-parchment-100"
          >
            Sign out
          </button>
        </div>
      </div>
    </header>
  )
}
