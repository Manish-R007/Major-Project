const FIELD_LABELS = {
  patta_number: 'patta number',
  claimant_name: 'claimant name',
  area_acres: 'area',
}

const STYLES = {
  matched: 'bg-canopy-400/25 text-canopy-800 border-canopy-600/30',
  mismatch: 'bg-rust-500/15 text-rust-600 border-rust-500/30',
  unparseable: 'bg-parchment-300 text-canopy-700/70 border-canopy-700/20',
  not_available: 'bg-parchment-300 text-canopy-700/50 border-canopy-700/15',
}

const LABELS = {
  matched: '✓ Fields match claim record',
  mismatch: '⚠ Mismatch detected',
  unparseable: 'Could not read structured fields',
  not_available: 'Not verified',
}

export default function VerificationBadge({ status, mismatchedFields }) {
  const fieldNames = (mismatchedFields || []).map((f) => FIELD_LABELS[f] || f).join(', ')

  return (
    <div>
      <span
        className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium tracking-wide ${STYLES[status] || STYLES.not_available}`}
      >
        {LABELS[status] || status}
      </span>
      {status === 'mismatch' && fieldNames && (
        <p className="mt-1 text-xs text-rust-600">
          Differs from the claim record: {fieldNames}. Please review before approving.
        </p>
      )}
    </div>
  )
}
