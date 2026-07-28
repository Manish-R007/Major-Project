export default function StatCard({ label, value, sublabel, accent = false }) {
  return (
    <div
      className={`rounded-2xl border p-5 ${
        accent
          ? 'border-canopy-900 bg-canopy-900 text-parchment-100'
          : 'border-canopy-900/10 bg-parchment-100'
      }`}
    >
      <p
        className={`text-[11px] uppercase tracking-[0.14em] ${
          accent ? 'text-parchment-200/70' : 'text-canopy-700/70'
        }`}
      >
        {label}
      </p>
      <p className={`mt-2 font-display text-3xl ${accent ? 'text-parchment-100' : 'text-canopy-950'}`}>
        {value}
      </p>
      {sublabel && (
        <p className={`mt-1 text-xs ${accent ? 'text-parchment-200/60' : 'text-canopy-700/60'}`}>
          {sublabel}
        </p>
      )}
    </div>
  )
}
