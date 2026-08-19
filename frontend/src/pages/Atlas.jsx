import { useEffect, useRef, useState } from 'react'
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

function createMarkerContent(color, hasDocumentMismatch) {
  const marker = document.createElement('div')
  marker.style.width = '16px'
  marker.style.height = '16px'
  marker.style.borderRadius = '9999px'
  marker.style.background = color
  marker.style.border = `2px solid ${hasDocumentMismatch ? '#A64B3A' : '#ffffff'}`
  marker.style.boxShadow = '0 1px 4px rgba(0, 0, 0, 0.35)'
  return marker
}

function removeMapOverlay(overlay) {
  if (typeof overlay.setMap === 'function') {
    overlay.setMap(null)
    return
  }
  overlay.map = null
}

export default function Atlas() {
  const { user } = useAuth()
  const [claims, setClaims] = useState([])
  const [selected, setSelected] = useState(null)
  const [detecting, setDetecting] = useState(false)
  const [detectError, setDetectError] = useState('')

  const canRunDetection = ['village_official', 'district_officer', 'state_officer', 'admin'].includes(user.role)

  function loadLayers() {
    client.get('/atlas/layers').then(({ data }) => setClaims(data.claims))
  }

  useEffect(() => { loadLayers() }, [])

  async function analyzeSatellite(claimId) {
    setDetecting(true)
    setDetectError('')
    try {
      const { data } = await client.get('/atlas/layers')
      const current = data.claims.find((c) => c.id === claimId)
      if (!current) throw new Error('Claim is no longer available in your jurisdiction.')
      await client.post(`/atlas/claims/${claimId}/analyze-satellite`)
      const refreshed = await client.get('/atlas/layers')
      setClaims(refreshed.data.claims)
      const updated = refreshed.data.claims.find((c) => c.id === claimId)
      if (updated) setSelected(updated)
    } catch (err) {
      setDetectError(err.response?.data?.detail || err.message || 'Satellite analysis failed.')
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
          <GoogleClaimsMap claims={claims} center={center} onSelect={setSelected} />
          {/* Legacy renderer removed; Google Maps is rendered above.
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
          */}
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
                  Parcel land-cover breakdown ({selected.assets.length})
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
                  <p className="mt-2 text-xs text-canopy-700/60">
                    Analysed within this claimant’s boundary: {selected.assets.reduce((total, asset) => total + Number(asset.area_acres || 0), 0).toFixed(2)} of {Number(selected.area_acres).toFixed(2)} acres.
                  </p>
                )}
                {selected.assets.length > 0 && (
                  <p className="mt-2 text-[11px] text-canopy-700/50">
                    {selected.assets[0].source === 'satellite_cv_kmeans'
                      ? 'Automatically acquired Sentinel-2 imagery, classified with scene data and vegetation signals.'
                      : 'Detection source recorded with this asset.'}
                  </p>
                )}
              </div>

              {canRunDetection && (
                <div className="mt-5 space-y-3 border-t border-canopy-900/10 pt-4">
                  <p className="text-xs text-canopy-700/60">
                    Free Sentinel-2 imagery is acquired automatically for this parcel. Land cover and scheme recommendations are refreshed from the analysed image.
                  </p>

                  {detectError && <p className="text-sm text-rust-600">{detectError}</p>}

                  <button
                    onClick={() => analyzeSatellite(selected.id)}
                    disabled={detecting}
                    className="w-full rounded-lg bg-ochre-500 py-2.5 text-sm font-medium text-canopy-950 transition hover:bg-ochre-400 disabled:opacity-60"
                  >
                    {detecting ? 'Acquiring and analysing…' : 'Analyse satellite image'}
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

function GoogleClaimsMap({ claims, center, onSelect }) {
  const elementRef = useRef(null)
  const mapRef = useRef(null)
  const callbackNameRef = useRef(`initGoogleClaimsMap${Math.random().toString(36).slice(2)}`)
  const overlaysRef = useRef([])
  const [mapReady, setMapReady] = useState(false)
  const [error, setError] = useState('')
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
  const mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID

  useEffect(() => {
    if (!apiKey) {
      setError('Google Maps is not configured. Add VITE_GOOGLE_MAPS_API_KEY to frontend/.env.local and restart Vite.')
      return undefined
    }
    const initialise = () => {
      if (mapRef.current || !elementRef.current) return
      if (typeof window.google?.maps?.Map !== 'function') {
        setError('Google Maps loaded, but the Maps JavaScript library is not available. Check that Maps JavaScript API is enabled for this key.')
        return
      }
      mapRef.current = new window.google.maps.Map(elementRef.current, {
        center: { lat: center[0], lng: center[1] }, zoom: claims.length ? 12 : 5,
        mapTypeId: 'satellite', mapTypeControl: true, streetViewControl: false, fullscreenControl: true,
        mapTypeControlOptions: { mapTypeIds: ['roadmap', 'satellite', 'hybrid', 'terrain'] },
        ...(mapId ? { mapId } : {}),
      })
      setMapReady(true)
    }
    const handleAuthFailure = () => {
      setError('Google Maps rejected this key. The public Google demo/sample key only works on Google\'s own demo sites. Create a browser key in your Google Cloud project, enable Maps JavaScript API and billing, and allow this app\'s URL in its HTTP referrer restrictions.')
    }
    const callbackName = callbackNameRef.current
    window.gm_authFailure = handleAuthFailure
    window[callbackName] = initialise
    if (window.google?.maps) { initialise(); return undefined }
    const existing = document.getElementById('google-maps-js')
    if (existing) {
      return () => {
        if (window[callbackName] === initialise) delete window[callbackName]
      }
    }
    const script = document.createElement('script')
    script.id = 'google-maps-js'
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&v=weekly&loading=async&libraries=marker&callback=${callbackName}`
    script.async = true
    script.defer = true
    const handleLoadError = () => setError('Google Maps could not load. Check the API key restrictions and Maps JavaScript API setting.')
    script.addEventListener('error', handleLoadError)
    document.head.appendChild(script)
    return () => {
      script.removeEventListener('error', handleLoadError)
      if (window.gm_authFailure === handleAuthFailure) delete window.gm_authFailure
      if (window[callbackName] === initialise) delete window[callbackName]
    }
  }, [apiKey, mapId])

  useEffect(() => {
    if (!mapReady || !mapRef.current) return
    overlaysRef.current.forEach(removeMapOverlay)
    const map = mapRef.current
    const bounds = new window.google.maps.LatLngBounds()
    const overlays = []
    claims.forEach((claim) => {
      const position = { lat: claim.lat, lng: claim.lng }
      bounds.extend(position)
      if (claim.parcel_geometry) {
        const parcel = new window.google.maps.Polygon({
          paths: claim.parcel_geometry.map(([lat, lng]) => ({ lat, lng })), map,
          strokeColor: '#F2C14E', strokeOpacity: 1, strokeWeight: 3, fillColor: '#F2C14E', fillOpacity: 0.16,
        })
        parcel.addListener('click', () => onSelect(claim))
        overlays.push(parcel)
      }
      const markerTitle = `${claim.claimant_name} - ${claim.area_acres} acres`
      const markerColor = STATUS_COLORS[claim.status]
      const marker = mapId && window.google.maps.marker?.AdvancedMarkerElement
        ? new window.google.maps.marker.AdvancedMarkerElement({
          position, map, title: markerTitle,
          content: createMarkerContent(markerColor, claim.document_status === 'mismatch'),
        })
        : new window.google.maps.Marker({
          position, map, title: markerTitle,
          icon: { path: window.google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: markerColor, fillOpacity: 0.9,
            strokeColor: claim.document_status === 'mismatch' ? '#A64B3A' : '#ffffff', strokeWeight: 2 },
        })
      marker.addListener('click', () => onSelect(claim))
      overlays.push(marker)
      claim.assets.forEach((asset) => {
        if (!asset.geometry) return
        overlays.push(new window.google.maps.Polygon({
          paths: asset.geometry.map(([lat, lng]) => ({ lat, lng })), map,
          strokeColor: ASSET_COLORS[asset.asset_type], strokeWeight: 1, fillColor: ASSET_COLORS[asset.asset_type], fillOpacity: 0.25,
        }))
      })
    })
    overlaysRef.current = overlays
    if (claims.length === 1) map.setCenter({ lat: claims[0].lat, lng: claims[0].lng })
    else if (claims.length > 1) map.fitBounds(bounds, 48)
  }, [claims, mapReady, onSelect])

  return <div className="relative h-full w-full"><div ref={elementRef} className="h-full w-full" />{error && <div className="absolute inset-0 flex items-center justify-center bg-parchment-100 p-8 text-center text-sm text-rust-600">{error}</div>}</div>
}
