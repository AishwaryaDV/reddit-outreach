export default function UrgencyDot({ postedAt }) {
  const ageMin = (Date.now() - new Date(postedAt).getTime()) / 60_000

  const color =
    ageMin < 30  ? 'bg-emerald-400' :
    ageMin < 90  ? 'bg-yellow-400'  :
                   'bg-red-400'

  const label =
    ageMin < 30  ? `${Math.round(ageMin)}m ago` :
    ageMin < 90  ? `${Math.round(ageMin)}m ago` :
    ageMin < 1440 ? `${Math.round(ageMin / 60)}h ago` :
                    `${Math.round(ageMin / 1440)}d ago`

  return (
    <span className="flex items-center gap-1.5 text-xs text-slate-500">
      <span className={`w-1.5 h-1.5 rounded-full ${color}`} />
      {label}
    </span>
  )
}
