import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

const DEMO_ACCOUNTS = [
  { role: 'Claimant', username: 'citizen1' },
  { role: 'Village Official', username: 'village_official' },
  { role: 'District Officer', username: 'district_officer' },
  { role: 'State Nodal Officer', username: 'state_officer' },
  { role: 'Administrator', username: 'admin' },
]

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(username, password)
      navigate('/dashboard')
    } catch {
      setError('Incorrect username or password.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-canopy-950 px-6">
      {/* Signature: topographic contour lines, evoking a survey map / forest terrain */}
      <div className="pointer-events-none absolute inset-0 opacity-40">
        <svg viewBox="0 0 1200 800" className="h-full w-full" preserveAspectRatio="xMidYMid slice">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <path
              key={i}
              d={`M-100 ${120 + i * 90} C 250 ${40 + i * 90}, 550 ${200 + i * 90}, 900 ${90 + i * 90} S 1400 ${140 + i * 90}, 1600 ${90 + i * 90}`}
              fill="none"
              stroke="#6E9C7D"
              strokeOpacity={0.18 - i * 0.012}
              strokeWidth="1.5"
            />
          ))}
        </svg>
      </div>
      <div className="pointer-events-none absolute -left-40 -top-40 h-96 w-96 rounded-full bg-ochre-500/10 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-32 -right-24 h-96 w-96 rounded-full bg-canopy-400/10 blur-3xl" />

      <div className="relative z-10 grid w-full max-w-5xl overflow-hidden rounded-3xl border border-parchment-100/10 bg-parchment-100/[0.03] shadow-2xl backdrop-blur md:grid-cols-2">
        {/* Left: brand panel */}
        <div className="hidden flex-col justify-between border-r border-parchment-100/10 p-10 md:flex">
          <div>
            <span className="grid h-11 w-11 place-items-center rounded-full bg-ochre-500 font-display text-lg text-canopy-950">
              FA
            </span>
            <h1 className="mt-8 font-display text-4xl leading-[1.1] text-parchment-100">
              Every claim,
              <br />
              mapped and known.
            </h1>
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-parchment-200/70">
              An AI-powered atlas and decision-support system for the Forest
              Rights Act — digitising legacy claims, mapping assets from
              satellite data, and matching every patta holder to the schemes
              they're entitled to.
            </p>
          </div>
          <div className="flex gap-6 font-mono text-[11px] uppercase tracking-widest text-parchment-200/50">
            <span>Madhya Pradesh</span>
            <span>Tripura</span>
            <span>Odisha</span>
            <span>Telangana</span>
          </div>
        </div>

        {/* Right: login form */}
        <div className="bg-parchment-100 p-10">
          <h2 className="font-display text-2xl text-canopy-950">Sign in</h2>
          <p className="mt-1 text-sm text-canopy-700/70">
            Access your FRA Atlas dashboard.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4">
            <div>
              <label className="text-xs font-medium uppercase tracking-wide text-canopy-800">
                Username
              </label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="mt-1.5 w-full rounded-lg border border-canopy-900/15 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-ochre-500 focus:ring-2 focus:ring-ochre-400/30"
                placeholder="e.g. district_officer"
              />
            </div>
            <div>
              <label className="text-xs font-medium uppercase tracking-wide text-canopy-800">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="mt-1.5 w-full rounded-lg border border-canopy-900/15 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-ochre-500 focus:ring-2 focus:ring-ochre-400/30"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <p className="rounded-lg bg-rust-500/10 px-3 py-2 text-sm text-rust-600">{error}</p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-canopy-900 py-2.5 text-sm font-medium text-parchment-100 transition hover:bg-canopy-800 disabled:opacity-60"
            >
              {submitting ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-canopy-700/70">
            New claimant?{' '}
            <Link to="/register" className="font-medium text-ochre-600 hover:underline">
              Register here
            </Link>
          </p>

          <div className="mt-8 rounded-xl border border-canopy-900/10 bg-parchment-200/60 p-4">
            <p className="text-[11px] font-medium uppercase tracking-wide text-canopy-700/70">
              Demo accounts · password: password123 (admin: admin123)
            </p>
            <ul className="mt-2 grid grid-cols-1 gap-1 sm:grid-cols-2">
              {DEMO_ACCOUNTS.map((acc) => (
                <li key={acc.username}>
                  <button
                    type="button"
                    onClick={() => setUsername(acc.username)}
                    className="font-mono text-xs text-canopy-800 underline decoration-canopy-800/30 underline-offset-2 hover:text-ochre-600"
                  >
                    {acc.username}
                  </button>
                  <span className="ml-1 text-xs text-canopy-700/50">— {acc.role}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
