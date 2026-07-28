import { useEffect, useState } from 'react'
import client from '../api/client'

export default function DSS() {
  const [schemes, setSchemes] = useState([])

  useEffect(() => {
    client.get('/dss/schemes').then(({ data }) => setSchemes(data))
  }, [])

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-ochre-600">Decision Support System</p>
      <h1 className="mt-1 font-display text-3xl text-canopy-950">Scheme Catalogue</h1>
      <p className="mt-1 max-w-xl text-sm text-canopy-700/70">
        These rules power the scheme recommendations generated on each claim's
        detail page. Eligibility gates are explicit and auditable by design.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        {schemes.map((s) => (
          <div key={s.id} className="rounded-2xl border border-canopy-900/10 bg-parchment-100 p-6">
            <p className="font-display text-lg text-canopy-950">{s.name}</p>
            <p className="mt-1 text-xs uppercase tracking-wide text-canopy-700/60">{s.ministry}</p>
            <p className="mt-3 text-sm text-canopy-800">{s.description}</p>
            <div className="mt-4 flex flex-wrap gap-2">
              {(s.eligibility_rules.claim_types || []).map((t) => (
                <span key={t} className="rounded-full bg-canopy-200/50 px-2.5 py-1 text-xs text-canopy-800">{t}</span>
              ))}
              {(s.eligibility_rules.land_types || []).map((t) => (
                <span key={t} className="rounded-full bg-ochre-400/20 px-2.5 py-1 text-xs text-ochre-600">{t}</span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
