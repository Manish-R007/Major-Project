import { useEffect, useState } from 'react'
import client from '../api/client'

export default function Users() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get('/users/').then(({ data }) => setUsers(data)).finally(() => setLoading(false))
  }, [])

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ochre-600">Administration</p>
      <h1 className="mt-1 font-display text-3xl text-canopy-950">System Users</h1>

      <div className="mt-8 overflow-hidden rounded-2xl border border-canopy-900/10 bg-parchment-100">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-canopy-900/10 bg-parchment-200/50 text-xs uppercase tracking-wide text-canopy-700/70">
            <tr>
              <th className="px-6 py-3">Name</th>
              <th className="px-6 py-3">Username</th>
              <th className="px-6 py-3">Role</th>
              <th className="px-6 py-3">Jurisdiction</th>
              <th className="px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-canopy-900/5">
            {loading && <tr><td colSpan={5} className="px-6 py-8 text-center text-canopy-700/60">Loading…</td></tr>}
            {users.map((u) => (
              <tr key={u.id} className="hover:bg-parchment-200/50">
                <td className="px-6 py-3 font-medium text-canopy-950">{u.full_name}</td>
                <td className="px-6 py-3 font-mono text-xs text-canopy-700/70">{u.username}</td>
                <td className="px-6 py-3">{u.role.replace('_', ' ')}</td>
                <td className="px-6 py-3 text-canopy-700/70">
                  {[u.village, u.district, u.state].filter(Boolean).join(', ') || '—'}
                </td>
                <td className="px-6 py-3">
                  <span className={`rounded-full px-2.5 py-1 text-xs ${u.is_active ? 'bg-canopy-400/25 text-canopy-800' : 'bg-rust-500/15 text-rust-600'}`}>
                    {u.is_active ? 'Active' : 'Disabled'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
