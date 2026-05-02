export default function ScoreBadge({ score }) {
  if (score == null) return (
    <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-slate-500">
      unscored
    </span>
  )

  const color =
    score >= 8 ? 'bg-emerald-500/15 text-emerald-400' :
    score >= 5 ? 'bg-yellow-500/15 text-yellow-400' :
                 'bg-slate-500/15 text-slate-400'

  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>
      {score}/10
    </span>
  )
}
