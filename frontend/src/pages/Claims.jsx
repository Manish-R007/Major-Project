import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'
import ClaimStatusBadge from '../components/ClaimStatusBadge.jsx'

const EMPTY_FORM = {
  patta_number: '', claimant_name: '', claim_type: 'IFR',
  state: '', district: '', village: '',
  latitude: '', longitude: '', area_acres: '', land_type: 'cultivable',
}

export default function Claims() {
  const { user } = useAuth()
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  function load() {
    setLoading(true)
    const params = statusFilter ? { status_filter: statusFilter } : {}
    client.get('/claims/', { params }).then(({ data }) => setClaims(data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [statusFilter])

  async function handleCreate(e) {
    e.preventDefault()
    setFormError('')
    try {
      await client.post('/claims/', {
        ...form,
        latitude: parseFloat(form.latitude),
        longitude: parseFloat(form.longitude),
        area_acres: parseFloat(form.area_acres),
      })
      setForm(EMPTY_FORM)
      setShowForm(false)
      load()
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Could not submit claim.')
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ochre-600">Registry</p>
          <h1 className="mt-1 font-display text-3xl text-canopy-950">FRA Claims</h1>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-full border border-canopy-900/15 bg-parchment-100 px-4 py-2 text-sm text-canopy-900"
          >
            <option value="">All statuses</option>
            <option value="submitted">Submitted</option>
            <option value="under_review">Under Review</option>
            <option value="verified">Verified</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
          {user.role === 'citizen' && (
            <button
              onClick={() => setShowForm((s) => !s)}
              className="rounded-full bg-canopy-900 px-5 py-2 text-sm font-medium text-parchment-100 hover:bg-canopy-800"
            >
              {showForm ? 'Cancel' : '+ New Claim'}
            </button>
          )}
        </div>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="mt-6 grid grid-cols-1 gap-4 rounded-2xl border border-canopy-900/10 bg-parchment-100 p-6 md:grid-cols-3">
          <Field label="Patta Number" value={form.patta_number} onChange={(v) => setForm({ ...form, patta_number: v })} />
          <Field label="Claimant Name" value={form.claimant_name} onChange={(v) => setForm({ ...form, claimant_name: v })} />
          <div>
            <Label>Claim Type</Label>
            <select value={form.claim_type} onChange={(e) => setForm({ ...form, claim_type: e.target.value })} className={inputClass}>
              <option value="IFR">Individual Forest Rights (IFR)</option>
              <option value="CFR">Community Forest Resource (CFR)</option>
              <option value="CR">Community Rights (CR)</option>
            </select>
          </div>
          <Field label="State" value={form.state} onChange={(v) => setForm({ ...form, state: v })} />
          <Field label="District" value={form.district} onChange={(v) => setForm({ ...form, district: v })} />
          <Field label="Village" value={form.village} onChange={(v) => setForm({ ...form, village: v })} />
          <Field label="Latitude" value={form.latitude} onChange={(v) => setForm({ ...form, latitude: v })} type="number" step="any" />
          <Field label="Longitude" value={form.longitude} onChange={(v) => setForm({ ...form, longitude: v })} type="number" step="any" />
          <Field label="Area (acres)" value={form.area_acres} onChange={(v) => setForm({ ...form, area_acres: v })} type="number" step="any" />
          <div>
            <Label>Land Type</Label>
            <select value={form.land_type} onChange={(e) => setForm({ ...form, land_type: e.target.value })} className={inputClass}>
              <option value="cultivable">Cultivable</option>
              <option value="homestead">Homestead</option>
              <option value="forest">Forest</option>
              <option value="waterlogged">Waterlogged</option>
            </select>
          </div>

          {formError && <p className="col-span-full text-sm text-rust-600">{formError}</p>}

          <div className="col-span-full">
            <button type="submit" className="rounded-lg bg-ochre-500 px-6 py-2.5 text-sm font-medium text-canopy-950 hover:bg-ochre-400">
              Submit Claim
            </button>
          </div>
        </form>
      )}

      <div className="mt-6 overflow-hidden rounded-2xl border border-canopy-900/10 bg-parchment-100">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-canopy-900/10 bg-parchment-200/50 text-xs uppercase tracking-wide text-canopy-700/70">
            <tr>
              <th className="px-6 py-3">Patta No.</th>
              <th className="px-6 py-3">Claimant</th>
              <th className="px-6 py-3">Type</th>
              <th className="px-6 py-3">Location</th>
              <th className="px-6 py-3">Area</th>
              <th className="px-6 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-canopy-900/5">
            {loading && (
              <tr><td colSpan={6} className="px-6 py-8 text-center text-canopy-700/60">Loading…</td></tr>
            )}
            {!loading && claims.length === 0 && (
              <tr><td colSpan={6} className="px-6 py-8 text-center text-canopy-700/60">No claims found.</td></tr>
            )}
            {claims.map((c) => (
              <tr key={c.id} className="transition hover:bg-parchment-200/50">
                <td className="px-6 py-3 font-mono text-xs text-canopy-700/70">
                  <Link to={`/claims/${c.id}`} className="hover:text-ochre-600">{c.patta_number}</Link>
                </td>
                <td className="px-6 py-3 font-medium text-canopy-950">{c.claimant_name}</td>
                <td className="px-6 py-3">{c.claim_type}</td>
                <td className="px-6 py-3 text-canopy-700/70">{c.village}, {c.district}</td>
                <td className="px-6 py-3">{c.area_acres} ac</td>
                <td className="px-6 py-3"><ClaimStatusBadge status={c.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const inputClass = "mt-1.5 w-full rounded-lg border border-canopy-900/15 bg-white px-3.5 py-2.5 text-sm text-ink outline-none transition focus:border-ochre-500 focus:ring-2 focus:ring-ochre-400/30"

function Label({ children }) {
  return <label className="text-xs font-medium uppercase tracking-wide text-canopy-800">{children}</label>
}

function Field({ label, value, onChange, type = 'text', step }) {
  return (
    <div>
      <Label>{label}</Label>
      <input
        required
        type={type}
        step={step}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={inputClass}
      />
    </div>
  )
}
