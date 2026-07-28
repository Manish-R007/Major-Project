import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'
import StatCard from '../components/StatCard.jsx'
import ClaimStatusBadge from '../components/ClaimStatusBadge.jsx'

export default function Dashboard() {
  const { user } = useAuth()
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get('/claims/').then(({ data }) => setClaims(data)).finally(() => setLoading(false))
  }, [])

  const counts = claims.reduce((acc, c) => {
    acc[c.status] = (acc[c.status] || 0) + 1
    return acc
  }, {})
  const totalArea = claims.reduce((sum, c) => sum + c.area_acres, 0)

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ochre-600">
            Welcome back
          </p>
          <h1 className="mt-1 font-display text-3xl text-canopy-950">{user.full_name}</h1>
          <p className="mt-1 text-sm text-canopy-700/70">
            {user.village && `${user.village}, `}
            {user.district && `${user.district}, `}
            {user.state || 'National view'}
          </p>
        </div>
        <Link
          to="/atlas"
          className="rounded-full bg-canopy-900 px-5 py-2.5 text-sm font-medium text-parchment-100 transition hover:bg-canopy-800"
        >
          Open the Atlas →
        </Link>
      </div>

      <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total Claims" value={loading ? '—' : claims.length} accent />
        <StatCard label="Approved" value={loading ? '—' : (counts.approved || 0)} />
        <StatCard label="Under Review" value={loading ? '—' : (counts.under_review || 0)} />
        <StatCard label="Total Area" value={loading ? '—' : `${totalArea.toFixed(1)} ac`} />
      </div>

      <div className="mt-10 rounded-2xl border border-canopy-900/10 bg-parchment-100">
        <div className="flex items-center justify-between border-b border-canopy-900/10 px-6 py-4">
          <h2 className="font-display text-lg text-canopy-950">Recent Claims</h2>
          <Link to="/claims" className="text-sm text-ochre-600 hover:underline">
            View all →
          </Link>
        </div>
        <div className="divide-y divide-canopy-900/5">
          {loading && <p className="px-6 py-6 text-sm text-canopy-700/60">Loading claims…</p>}
          {!loading && claims.length === 0 && (
            <p className="px-6 py-6 text-sm text-canopy-700/60">
              No claims yet. Once claims are submitted, they'll appear here.
            </p>
          )}
          {claims.slice(0, 6).map((c) => (
            <Link
              key={c.id}
              to={`/claims/${c.id}`}
              className="flex items-center justify-between px-6 py-4 transition hover:bg-parchment-200/60"
            >
              <div>
                <p className="font-mono text-xs text-canopy-700/60">{c.patta_number}</p>
                <p className="text-sm font-medium text-canopy-950">{c.claimant_name}</p>
                <p className="text-xs text-canopy-700/60">
                  {c.village}, {c.district}, {c.state} · {c.area_acres} acres
                </p>
              </div>
              <ClaimStatusBadge status={c.status} />
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
