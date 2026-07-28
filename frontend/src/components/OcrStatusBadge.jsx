const STYLES = {
  pending: 'bg-canopy-200/60 text-canopy-800 border-canopy-800/20',
  complete: 'bg-canopy-400/25 text-canopy-800 border-canopy-600/30',
  unavailable: 'bg-parchment-300 text-canopy-700/70 border-canopy-700/20',
  failed: 'bg-rust-500/15 text-rust-600 border-rust-500/30',
}

const LABELS = {
  pending: 'OCR Pending',
  complete: 'OCR Complete',
  unavailable: 'OCR Unavailable',
  failed: 'OCR Failed',
}

export default function OcrStatusBadge({ status }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-xs font-medium tracking-wide ${STYLES[status] || STYLES.pending}`}
    >
      {LABELS[status] || status}
    </span>
  )
}
