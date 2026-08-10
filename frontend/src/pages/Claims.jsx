import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'
import ClaimStatusBadge from '../components/ClaimStatusBadge.jsx'
import CameraCaptureModal from '../components/CameraCaptureModal.jsx'

export default function Claims() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [claims, setClaims] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formError, setFormError] = useState('')
  const [uploading, setUploading] = useState(false)
  const [cameraOpen, setCameraOpen] = useState(false)
  const [statusFilter, setStatusFilter] = useState('')

  function load() {
    setLoading(true)
    const params = statusFilter ? { status_filter: statusFilter } : {}
    client.get('/claims/', { params }).then(({ data }) => setClaims(data)).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [statusFilter])

  async function handleCreate(input) {
    const file = input instanceof File ? input : input.target.files[0]
    if (!file) return
    setFormError('')
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const { data } = await client.post('/claims/from-document', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      navigate(`/claims/${data.id}`)
    } catch (err) {
      setFormError(err.response?.data?.detail || 'Could not read the document.')
    } finally {
      setUploading(false)
      if (input.target) input.target.value = ''
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
        <div className="mt-6 rounded-2xl border border-canopy-900/10 bg-parchment-100 p-6">
          <h2 className="font-display text-lg text-canopy-950">Create from claim document</h2>
          <p className="mt-1 text-sm text-canopy-700/70">Upload a clear labelled scan. OCR reads the claimant, patta, area, village and survey number, then matches the official cadastral boundary—no manual form entry.</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button onClick={() => setCameraOpen(true)} disabled={uploading} className="rounded-lg bg-ochre-500 px-6 py-2.5 text-sm font-medium text-canopy-950 hover:bg-ochre-400 disabled:opacity-60">{uploading ? 'Reading document…' : 'Scan with camera'}</button>
            <label className="cursor-pointer rounded-lg border border-canopy-900/20 px-6 py-2.5 text-sm font-medium text-canopy-900 hover:bg-canopy-900 hover:text-parchment-100">
              Choose image file
              <input type="file" accept="image/png,image/jpeg,image/tiff,image/bmp" onChange={handleCreate} disabled={uploading} className="hidden" />
            </label>
          </div>
          <p className="mt-3 text-xs text-canopy-700/60">On a phone, “Scan with phone camera” opens the rear camera. Photograph the full page in good light, keeping all labels visible.</p>
          {formError && <p className="mt-3 text-sm text-rust-600">{formError}</p>}
        </div>
      )}
      {cameraOpen && <CameraCaptureModal onClose={() => setCameraOpen(false)} onCapture={(file) => { setCameraOpen(false); handleCreate(file) }} />}

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
