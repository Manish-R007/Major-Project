const STYLES = {
  submitted: 'bg-canopy-200/60 text-canopy-800 border-canopy-800/20',
  under_review: 'bg-ochre-400/20 text-ochre-600 border-ochre-500/30',
  verified: 'bg-canopy-400/25 text-canopy-800 border-canopy-600/30',
  approved: 'bg-canopy-700 text-parchment-100 border-canopy-800',
  rejected: 'bg-rust-500/15 text-rust-600 border-rust-500/30',
}

const LABELS = {
  submitted: 'Submitted',
  under_review: 'Under Review',
  verified: 'Verified',
  approved: 'Approved',
  rejected: 'Rejected',
}

export default function ClaimStatusBadge({ status }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium tracking-wide ${STYLES[status] || STYLES.submitted}`}
    >
      {LABELS[status] || status}
    </span>
  )
}
