import { useState } from 'react'

const ITEMS = [
  {
    key: 'reddit_karma',
    label: 'Reddit app registration',
    detail: 'Build karma to ~50+ on r/reactjs, r/webdev — needed for Phase 4 sending',
  },
  {
    key: 'oracle',
    label: 'Oracle server',
    detail: 'Incident ticket raised — needed for Phase 6 deployment only',
  },
]

export default function SetupChecklist() {
  const [dismissed, setDismissed] = useState(
    () => JSON.parse(localStorage.getItem('checklist_dismissed') || '[]')
  )

  const pending = ITEMS.filter((item) => !dismissed.includes(item.key))

  if (!pending.length) return null

  function dismiss(key) {
    const next = [...dismissed, key]
    setDismissed(next)
    localStorage.setItem('checklist_dismissed', JSON.stringify(next))
  }

  return (
    <div className="mb-6 bg-yellow-500/5 border border-yellow-500/20 rounded-xl p-4">
      <p className="text-xs font-medium text-yellow-400 mb-3">Setup checklist — {pending.length} item{pending.length !== 1 ? 's' : ''} pending</p>
      <div className="flex flex-col gap-2">
        {pending.map((item) => (
          <div key={item.key} className="flex items-start justify-between gap-3">
            <div>
              <span className="text-sm text-slate-300">{item.label}</span>
              <p className="text-xs text-slate-500 mt-0.5">{item.detail}</p>
            </div>
            <button
              onClick={() => dismiss(item.key)}
              className="text-xs text-slate-600 hover:text-slate-400 transition-colors shrink-0 mt-0.5"
            >
              dismiss
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
