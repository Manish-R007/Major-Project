import { Fragment, useEffect, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup, Polygon } from 'react-leaflet'
import client from '../api/client'
import { useAuth } from '../context/AuthContext.jsx'
import ClaimStatusBadge from '../components/ClaimStatusBadge.jsx'

const ASSET_COLORS = {
  agricultural_land: '#C98A2B',
  forest_cover: '#2C5A49',
  water_body: '#3E6C8A',
  homestead: '#8C6A3E',
  encroachment: '#A64B3A',
}

const STATUS_COLORS = {
  submitted: '#6E9C7D',
  under_review: '#DDA84F',
  verified: '#3E6C55',
  approved: '#17332A',
  rejected: '#A64B3A',
}

const DOC_STATUS_LABELS = {
  matched: '✓ Document verified',
  mismatch: '⚠ Document mismatch flagged',
  unparseable: 'Document uploaded — fields unreadable',
  not_available: 'Document uploaded — not yet verified',
  no_document: 'No document uploaded',
}

const DOC_STATUS_STYLES = {
  matched: 'bg-canopy-400/25 text-canopy-800',
  mismatch: 'bg-rust-500/15 text-rust-600',
  unparseable: 'bg-parchment-300 text-canopy-700/70',
  not_available: 'bg-parchment-300 text-canopy-700/60',
  no_document: 'bg-parchment-300 text-canopy-700/50',
}

export default function Atlas() {
  const { user } = useAuth()
  const [claims, setClaims] = useState([])
  const [selected, setSelected] = useState(null)
  const [detecting, setDetecting] = useState(false)
  const [satelliteImage, setSatelliteImage] = useState(null)
  const [uploadingImage, setUploadingImage] = useState(false)
  const [detectError, setDetectError] = useState('')
  const [basemap, setBasemap] = useState('satellite')

  const canRunDetection = ['village_official', 'district_officer', 'state_officer', 'admin'].includes(user.role)

  function loadLayers() {
    client.get('/atlas/layers').then(({ data }) => setClaims(data.claims))
  }

  useEffect(() => { loadLayers() }, [])

  useEffect(() => {
    if (!selected) { setSatelliteImage(null); return }
    client.get(`/atlas/claims/${selected.id}/satellite-image`)
      .then(({ data }) => setSatelliteImage(data))
      .catch(() => setSatelliteImage(null))
  }, [selected?.id])

  async function uploadSatelliteImage(e) {
    const file = e.target.files[0]
    if (!file || !selected) return
    setUploadingImage(true)
    setDetectError('')
    const formData = new FormData()
    formData.append('file', file)
    try {
      const { data } = await client.post(
        `/atlas/claims/${selected.id}/satellite-image?coverage_deg=0.01`, formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      setSatelliteImage(data)
    } catch (err) {
      setDetectError(err.response?.data?.detail || 'Image upload failed.')
    } finally {
      setUploadingImage(false)
      e.target.value = ''
    }
  }

  async function runDetection(claimId) {
    setDetecting(true)
    setDetectError('')
    try {
      await client.post('/atlas/detect', { claim_id: claimId })
      loadLayers()
      // Refresh the selected claim's data (with new assets) from the reloaded layer list.
      const { data } = await client.get('/atlas/layers')
      const updated = data.claims.find((c) => c.id === claimId)
      if (updated) setSelected(updated)
    } catch (err) {
      setDetectError(err.response?.data?.detail || 'Detection failed.')
    } finally {
      setDetecting(false)
    }
  }

  const center = claims.length
    ? [claims[0].lat, claims[0].lng]
    : [22.5, 82.5] // roughly central India across the four focus states

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.14em] text-ochre-600">WebGIS</p>
          <h1 className="mt-1 font-display text-3xl text-canopy-950">FRA Atlas</h1>
          <p className="mt-1 text-sm text-canopy-700/70">
            {claims.length} claim{claims.length !== 1 && 's'} in your jurisdiction
          </p>
        </div>
        <div className="flex gap-4 text-xs text-canopy-700/70">
          <select value={basemap} onChange={(e) => setBasemap(e.target.value)} className="rounded-full border border-canopy-900/15 bg-parchment-100 px-3 py-1 text-xs text-canopy-900">
            <option value="satellite">Satellite imagery</option>
            <option value="streets">Street map</option>
          </select>
          {Object.entries(ASSET_COLORS).map(([k, color]) => (
            <span key={k} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
              {k.replace('_', ' ')}
            </span>
          ))}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="overflow-hidden rounded-2xl border border-canopy-900/10 lg:col-span-2" style={{ height: 560 }}>
          <MapContainer center={center} zoom={6} style={{ height: '100%', width: '100%' }}>
            {basemap === 'satellite' ? (
              <TileLayer attribution='Tiles &copy; Esri' url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
            ) : (
              <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            )}
            {claims.map((c) => (
              <Fragment key={c.id}>
                {c.parcel_geometry && (
                  <Polygon
                    positions={c.parcel_geometry}
                    pathOptions={{ color: '#F2C14E', fillColor: '#F2C14E', fillOpacity: 0.16, weight: 3 }}
                    eventHandlers={{ click: () => setSelected(c) }}
                  >
                    <Popup><div className="font-body text-sm"><p className="font-semibold">{c.claimant_name}'s parcel</p><p>{c.area_acres} acres claimed</p></div></Popup>
                  </Polygon>
                )}
                {c.document_status === 'mismatch' && (
                  <CircleMarker
                    center={[c.lat, c.lng]}
                    radius={13}
                    pathOptions={{
                      color: '#A64B3A',
                      fillOpacity: 0,
                      weight: 2,
                      dashArray: '4, 3',
                    }}
                  />
                )}
                <CircleMarker
                  center={[c.lat, c.lng]}
                  radius={8}
                  pathOptions={{
                    color: STATUS_COLORS[c.status],
                    fillColor: STATUS_COLORS[c.status],
                    fillOpacity: 0.85,
                    weight: 2,
                  }}
                  eventHandlers={{ click: () => setSelected(c) }}
                >
                  <Popup>
                    <div className="font-body text-sm">
                      <p className="font-semibold">{c.claimant_name}</p>
                      <p className="text-xs text-gray-600">{c.patta_number} · {c.claim_type}</p>
                      <p className="text-xs text-gray-600">{c.area_acres} acres</p>
                    </div>
                  </Popup>
                </CircleMarker>
                {c.assets.map((a, i) => a.geometry && (
                  <Polygon
                    key={`${c.id}-${i}`}
                    positions={a.geometry}
                    pathOptions={{
                      color: ASSET_COLORS[a.asset_type],
                      fillColor: ASSET_COLORS[a.asset_type],
                      fillOpacity: 0.25,
                      weight: 1,
                    }}
                  />
                ))}
              </Fragment>
            ))}
          </MapContainer>
        </div>

        <div className="rounded-2xl border border-canopy-900/10 bg-parchment-100 p-5">
          {!selected && (
            <div className="flex h-full flex-col items-center justify-center bg-contour bg-cover py-16 text-center">
              <p className="font-display text-lg text-canopy-900">Select a claim</p>
              <p className="mt-1 max-w-[220px] text-sm text-canopy-700/60">
                Click a marker on the map to inspect claim details and AI-detected assets.
              </p>
            </div>
          )}

          {selected && (
            <div>
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-mono text-xs text-canopy-700/60">{selected.patta_number}</p>
                  <h3 className="font-display text-xl text-canopy-950">{selected.claimant_name}</h3>
                </div>
                <ClaimStatusBadge status={selected.status} />
              </div>

              <span className={`mt-2 inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${DOC_STATUS_STYLES[selected.document_status] || DOC_STATUS_STYLES.no_document}`}>
                {DOC_STATUS_LABELS[selected.document_status] || 'No document uploaded'}
              </span>
              {selected.document_status === 'mismatch' && (
                <p className="mt-1 text-xs text-rust-600">
                  Uploaded document fields don't match the claim record — see the claim's
                  detail page for specifics before approving.
                </p>
              )}

              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-canopy-700/60">Claim type</dt><dd className="font-medium">{selected.claim_type}</dd></div>
                <div><dt className="text-canopy-700/60">Area</dt><dd className="font-medium">{selected.area_acres} acres</dd></div>
                <div><dt className="text-canopy-700/60">Village</dt><dd className="font-medium">{selected.village}</dd></div>
                <div><dt className="text-canopy-700/60">District</dt><dd className="font-medium">{selected.district}</dd></div>
              </dl>
              <p className="mt-3 rounded-lg bg-ochre-500/10 px-3 py-2 text-xs text-canopy-800">
                Yellow boundary on the satellite map shows this person's claimed {selected.area_acres} acre parcel.
              </p>

              <div className="mt-5 border-t border-canopy-900/10 pt-4">
                <p className="text-xs font-medium uppercase tracking-wide text-canopy-700/70">
                  Detected Assets ({selected.assets.length})
                </p>
                {selected.assets.length === 0 && (
                  <p className="mt-2 text-sm text-canopy-700/60">No assets detected yet.</p>
                )}
                <ul className="mt-2 space-y-2">
                  {selected.assets.map((a, i) => (
                    <li key={i} className="flex items-center justify-between rounded-lg bg-parchment-200/60 px-3 py-2 text-sm">
                      <span className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-sm" style={{ background: ASSET_COLORS[a.asset_type] }} />
                        {a.asset_type.replace('_', ' ')}
                      </span>
                      <span className="font-mono text-xs text-canopy-700/70">
                        {a.area_acres} ac · {(a.confidence_score * 100).toFixed(0)}%
                      </span>
                    </li>
                  ))}
                </ul>
                {selected.assets.length > 0 && (
                  <p className="mt-2 text-[11px] text-canopy-700/50">
                    {selected.assets[0].source === 'satellite_cv_kmeans'
                      ? 'Detected from your uploaded image (real K-means color-clustering analysis).'
                      : 'Simulated detection — no satellite image has been uploaded for this claim yet.'}
                  </p>
                )}
              </div>

              {canRunDetection && (
                <div className="mt-5 space-y-3 border-t border-canopy-900/10 pt-4">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-canopy-700/70">
                      Satellite / Aerial Image
                    </p>
                    {satelliteImage ? (
                      <p className="mt-1 text-xs text-canopy-700/60">
                        📎 {satelliteImage.original_filename} — uploaded{' '}
                        {new Date(satelliteImage.uploaded_at).toLocaleDateString()}
                      </p>
                    ) : (
                      <p className="mt-1 text-xs text-canopy-700/50">
                        No image uploaded — detection will use the simulated fallback.
                      </p>
                    )}
                    <label className="mt-2 inline-block cursor-pointer rounded-full border border-canopy-900/20 px-4 py-1.5 text-xs font-medium text-canopy-900 hover:bg-canopy-900 hover:text-parchment-100">
                      {uploadingImage ? 'Uploading…' : satelliteImage ? 'Replace image' : 'Upload image'}
                      <input
                        type="file"
                        accept="image/png,image/jpeg,image/tiff,image/bmp"
                        onChange={uploadSatelliteImage}
                        disabled={uploadingImage}
                        className="hidden"
                      />
                    </label>
                  </div>

                  {detectError && <p className="text-sm text-rust-600">{detectError}</p>}

                  <button
                    onClick={() => runDetection(selected.id)}
                    disabled={detecting}
                    className="w-full rounded-lg bg-ochre-500 py-2.5 text-sm font-medium text-canopy-950 transition hover:bg-ochre-400 disabled:opacity-60"
                  >
                    {detecting
                      ? 'Running detection…'
                      : satelliteImage
                        ? 'Run Real CV Asset Detection'
                        : 'Run Simulated Asset Detection'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
