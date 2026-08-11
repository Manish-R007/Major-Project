import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'
import ClaimStatusBadge from '../components/ClaimStatusBadge.jsx'
import OcrStatusBadge from '../components/OcrStatusBadge.jsx'
import VerificationBadge from '../components/VerificationBadge.jsx'
import CameraCaptureModal from '../components/CameraCaptureModal.jsx'

const STATUS_OPTIONS = ['submitted', 'under_review', 'verified', 'approved', 'rejected']

export default function ClaimDetail() {
  const { id } = useParams()
  const { user } = useAuth()
  const [claim, setClaim] = useState(null)
  const [recommendations, setRecommendations] = useState([])
  const [documents, setDocuments] = useState([])
  const [notes, setNotes] = useState('')
  const [newStatus, setNewStatus] = useState('')
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [cameraOpen, setCameraOpen] = useState(false)

  const canReview = ['village_official', 'district_officer', 'state_officer', 'admin'].includes(user.role)

  function load() {
    client.get(`/claims/${id}`).then(({ data }) => {
      setClaim(data)
      setNewStatus(data.status)
    })
    client.get(`/dss/claims/${id}/recommendations`).then(({ data }) => setRecommendations(data))
    client.get(`/claims/${id}/documents`).then(({ data }) => setDocuments(data))
  }

  useEffect(() => { load() }, [id])

  async function handleFileUpload(input) {
    const file = input instanceof File ? input : input.target.files[0]
    if (!file) return
    setUploadError('')
    setUploading(true)
    const formData = new FormData()
    formData.append('file', file)
    try {
      await client.post(`/claims/${id}/documents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      client.get(`/claims/${id}/documents`).then(({ data }) => setDocuments(data))
    } catch (err) {
      setUploadError(err.response?.data?.detail || 'Upload failed.')
    } finally {
      setUploading(false)
      if (input.target) input.target.value = ''
    }
  }

  async function handleDownload(doc) {
    const response = await client.get(`/claims/${id}/documents/${doc.id}/file`, {
      responseType: 'blob',
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', doc.original_filename)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  }

  async function retryOcr(doc) {
    setUploadError('')
    setUploading(true)
    try {
      const { data } = await client.post(`/claims/${id}/documents/${doc.id}/retry-ocr`)
      setDocuments((current) => current.map((item) => item.id === data.id ? data : item))
    } catch (err) {
      setUploadError(err.response?.data?.detail || 'Could not retry OCR.')
    } finally {
      setUploading(false)
    }
  }

  async function updateStatus(e) {
    e.preventDefault()
    setBusy(true)
    try {
      await client.patch(`/claims/${id}/status`, { status: newStatus, reviewer_notes: notes })
      load()
    } finally {
      setBusy(false)
    }
  }

  async function generateRecommendations() {
    setBusy(true)
    try {
      const { data } = await client.post(`/dss/claims/${id}/recommend`)
      setRecommendations(data)
    } finally {
      setBusy(false)
    }
  }

  if (!claim) return <div className="px-6 py-8 text-canopy-700/60">Loading…</div>

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <Link to="/claims" className="text-sm text-canopy-700/60 hover:text-ochre-600">← Back to claims</Link>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs text-canopy-700/60">{claim.patta_number}</p>
          <h1 className="mt-1 font-display text-3xl text-canopy-950">{claim.claimant_name}</h1>
          <p className="mt-1 text-sm text-canopy-700/70">
            {claim.village}, {claim.district}, {claim.state}
          </p>
        </div>
        <ClaimStatusBadge status={claim.status} />
      </div>

      <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <InfoBlock label="Claim Type" value={claim.claim_type} />
        <InfoBlock label="Land Type" value={claim.land_type || '—'} />
        <InfoBlock label="Area" value={`${claim.area_acres} acres`} />
        <InfoBlock label="Submitted" value={new Date(claim.submitted_date).toLocaleDateString()} />
      </div>
      {claim.survey_number && (
        <div className="mt-4 rounded-xl border border-canopy-900/10 bg-parchment-100 p-4 text-sm text-canopy-800">
          <span className="font-medium">Survey / plot number:</span> {claim.survey_number}
          {claim.parcel_source === 'cadastral_registry' && <span className="ml-2 rounded-full bg-canopy-400/25 px-2 py-1 text-xs text-canopy-800">Official cadastral boundary matched</span>}
        </div>
      )}

      {claim.reviewer_notes && (
        <div className="mt-6 rounded-xl border border-canopy-900/10 bg-parchment-200/50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-canopy-700/70">Reviewer Notes</p>
          <p className="mt-1 text-sm text-canopy-900">{claim.reviewer_notes}</p>
        </div>
      )}

      {canReview && (
        <form onSubmit={updateStatus} className="mt-6 rounded-2xl border border-canopy-900/10 bg-parchment-100 p-6">
          <h2 className="font-display text-lg text-canopy-950">Update Status</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
            <select
              value={newStatus}
              onChange={(e) => setNewStatus(e.target.value)}
              className="rounded-lg border border-canopy-900/15 bg-white px-3.5 py-2.5 text-sm"
            >
              {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </select>
            <input
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Reviewer notes (optional)"
              className="rounded-lg border border-canopy-900/15 bg-white px-3.5 py-2.5 text-sm md:col-span-2"
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="mt-4 rounded-lg bg-canopy-900 px-6 py-2.5 text-sm font-medium text-parchment-100 hover:bg-canopy-800 disabled:opacity-60"
          >
            Save Update
          </button>
        </form>
      )}

      <div className="mt-8 rounded-2xl border border-canopy-900/10 bg-parchment-100 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-display text-lg text-canopy-950">Claim Documents</h2>
            <p className="text-xs text-canopy-700/60">
              Scanned pattas, old FRA forms, or survey sketches for this claim.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => setCameraOpen(true)} disabled={uploading} className="rounded-full bg-canopy-900 px-4 py-2 text-xs font-medium text-parchment-100 hover:bg-canopy-800 disabled:opacity-60">{uploading ? 'Uploading…' : 'Scan with camera'}</button>
            <label className="cursor-pointer rounded-full border border-canopy-900/20 px-4 py-2 text-xs font-medium text-canopy-900 hover:bg-canopy-900 hover:text-parchment-100">
              + Upload file
              <input type="file" accept="image/png,image/jpeg,image/tiff,image/bmp,application/pdf" onChange={handleFileUpload} disabled={uploading} className="hidden" />
            </label>
          </div>
        </div>

        {uploadError && <p className="mt-3 text-sm text-rust-600">{uploadError}</p>}
        <p className="mt-3 text-xs text-canopy-700/60">On a phone, “Scan with camera” requests the rear camera. On desktop, choose a file or use your webcam if the browser offers it.</p>

        {documents.length === 0 && (
          <p className="mt-4 text-sm text-canopy-700/60">No documents uploaded yet.</p>
        )}

        <div className="mt-4 space-y-3">
          {documents.map((doc) => (
            <div key={doc.id} className="rounded-xl border border-canopy-900/10 bg-parchment-200/40 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <button
                    onClick={() => handleDownload(doc)}
                    className="text-sm font-medium text-canopy-950 hover:text-ochre-600 hover:underline"
                  >
                    {doc.original_filename}
                  </button>
                  <p className="text-xs text-canopy-700/60">
                    {(doc.file_size_bytes / 1024).toFixed(0)} KB · uploaded{' '}
                    {new Date(doc.uploaded_at).toLocaleDateString()}
                  </p>
                </div>
                <OcrStatusBadge status={doc.ocr_status} />
              </div>
              {doc.ocr_status === 'complete' && (
                <div className="mt-2">
                  <VerificationBadge status={doc.verification_status} mismatchedFields={doc.mismatched_fields} />
                </div>
              )}
              {doc.extracted_text && (
                <div className="mt-3 rounded-lg bg-parchment-100 p-3">
                  <p className="text-[11px] font-medium uppercase tracking-wide text-canopy-700/60">
                    OCR-extracted text
                  </p>
                  <p className="mt-1 whitespace-pre-wrap font-mono text-xs text-canopy-800">
                    {doc.extracted_text || '(no text detected)'}
                  </p>
                </div>
              )}
              {doc.ocr_status === 'failed' && (
                <>
                <p className="mt-2 text-xs text-rust-600 italic">
                  OCR could not read this image. Please re-upload it after the server OCR setup is complete.
                </p>
                <button
                  onClick={() => retryOcr(doc)}
                  disabled={uploading}
                  className="mt-3 rounded-full border border-canopy-900/20 px-3 py-1.5 text-xs font-medium text-canopy-900 hover:bg-canopy-900 hover:text-parchment-100 disabled:opacity-60"
                >
                  {uploading ? 'Retrying OCR…' : 'Retry OCR'}
                </button>
                </>
              )}
              {doc.ocr_status === 'unavailable' && (
                <>
                <p className="mt-2 text-xs text-canopy-700/50 italic">
                  OCR engine not installed on the server — file stored, text not extracted.
                </p>
                <button
                  onClick={() => retryOcr(doc)}
                  disabled={uploading}
                  className="mt-3 rounded-full border border-canopy-900/20 px-3 py-1.5 text-xs font-medium text-canopy-900 hover:bg-canopy-900 hover:text-parchment-100 disabled:opacity-60"
                >
                  {uploading ? 'Retrying OCR…' : 'Retry OCR'}
                </button>
                </>
              )}
            </div>
          ))}
        </div>
      </div>
      {cameraOpen && <CameraCaptureModal onClose={() => setCameraOpen(false)} onCapture={(file) => { setCameraOpen(false); handleFileUpload(file) }} />}

      <div className="mt-8 rounded-2xl border border-canopy-900/10 bg-parchment-100 p-6">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg text-canopy-950">DSS Scheme Recommendations</h2>
          <button
            onClick={generateRecommendations}
            disabled={busy}
            className="rounded-full bg-ochre-500 px-4 py-2 text-xs font-medium text-canopy-950 hover:bg-ochre-400 disabled:opacity-60"
          >
            {busy ? 'Generating…' : 'Regenerate'}
          </button>
        </div>

        {recommendations.length === 0 && (
          <p className="mt-4 text-sm text-canopy-700/60">
            No recommendations yet — click Regenerate to run the DSS engine against this claim.
          </p>
        )}

        <div className="mt-4 space-y-3">
          {recommendations.map((r) => (
            <div key={r.id} className="rounded-xl border border-canopy-900/10 bg-parchment-200/40 p-4">
              <div className="flex items-center justify-between">
                <p className="font-medium text-canopy-950">{r.scheme.name}</p>
                <span className="font-mono text-sm text-ochre-600">{r.score.toFixed(0)}% match</span>
              </div>
              <p className="mt-1 text-xs text-canopy-700/60">{r.scheme.ministry}</p>
              <p className="mt-2 text-sm text-canopy-800">{r.scheme.description}</p>
              <ul className="mt-2 list-inside list-disc text-xs text-canopy-700/70">
                {r.reasons.map((reason, i) => <li key={i}>{reason}</li>)}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function InfoBlock({ label, value }) {
  return (
    <div className="rounded-xl border border-canopy-900/10 bg-parchment-100 p-4">
      <p className="text-[11px] uppercase tracking-wide text-canopy-700/60">{label}</p>
      <p className="mt-1 font-medium text-canopy-950">{value}</p>
    </div>
  )
}
