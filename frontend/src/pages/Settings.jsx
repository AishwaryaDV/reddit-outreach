import { useEffect, useState } from 'react'
import { supabase } from '../lib/supabase'

export default function Settings() {
  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-white">Settings</h1>
        <p className="text-sm text-slate-500 mt-0.5">Configure the tool without touching code</p>
      </div>
      <NotificationsSection />
      <SearchTermsSection />
      <ConfigSection />
    </div>
  )
}

function NotificationsSection() {
  const [enabled, setEnabled] = useState(null)
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)

  useEffect(() => {
    fetch('http://localhost:8000/notifications/status')
      .then((r) => r.json())
      .then((d) => { setEnabled(d.enabled); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  async function handleToggle() {
    if (toggling) return
    setToggling(true)
    try {
      const res = await fetch('http://localhost:8000/notifications/toggle', { method: 'POST' })
      const data = await res.json()
      setEnabled(data.enabled)
    } catch {
      // backend unreachable
    }
    setToggling(false)
  }

  return (
    <section>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-white">Email Alerts</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Pause alerts when you don't want to be notified — setting persists across restarts
        </p>
      </div>

      <div className="bg-white/3 border border-white/8 rounded-xl px-4 py-3 flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-300">
            {loading ? '—' : enabled ? 'Alerts enabled' : 'Alerts paused'}
          </p>
          <p className="text-xs text-slate-600 mt-0.5">
            {enabled
              ? 'You\'ll get an email for every new post that scores ≥ 3'
              : 'No emails will be sent until you re-enable'}
          </p>
        </div>
        <button
          onClick={handleToggle}
          disabled={loading || toggling}
          className={`w-11 h-6 rounded-full transition-colors relative shrink-0 disabled:opacity-40 ${
            enabled ? 'bg-emerald-500' : 'bg-white/10'
          }`}
        >
          <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all ${
            enabled ? 'left-5' : 'left-0.5'
          }`} />
        </button>
      </div>
    </section>
  )
}

function SearchTermsSection() {
  const [terms, setTerms] = useState([])
  const [loading, setLoading] = useState(true)
  const [newTerm, setNewTerm] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    load()
  }, [])

  async function load() {
    const { data } = await supabase
      .from('search_terms')
      .select('*')
      .order('created_at', { ascending: true })
    setTerms(data ?? [])
    setLoading(false)
  }

  async function handleToggle(term) {
    await supabase
      .from('search_terms')
      .update({ enabled: !term.enabled })
      .eq('id', term.id)
    setTerms((prev) =>
      prev.map((t) => (t.id === term.id ? { ...t, enabled: !t.enabled } : t))
    )
  }

  async function handleDelete(id) {
    await supabase.from('search_terms').delete().eq('id', id)
    setTerms((prev) => prev.filter((t) => t.id !== id))
  }

  async function handleAdd(e) {
    e.preventDefault()
    const trimmed = newTerm.trim().toLowerCase()
    if (!trimmed) return
    if (terms.some((t) => t.term === trimmed)) {
      setError('Term already exists')
      return
    }
    setAdding(true)
    setError('')
    const { data, error: dbError } = await supabase
      .from('search_terms')
      .insert({ term: trimmed, enabled: true })
      .select()
      .single()
    if (dbError) {
      setError('Failed to add term')
    } else {
      setTerms((prev) => [...prev, data])
      setNewTerm('')
    }
    setAdding(false)
  }

  const enabledCount = terms.filter((t) => t.enabled).length

  return (
    <section>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-white">Search Terms</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          {enabledCount} of {terms.length} enabled — watcher uses these to search Reddit every 2 minutes
        </p>
      </div>

      {loading ? (
        <div className="text-slate-500 text-sm">Loading...</div>
      ) : (
        <>
          <div className="flex flex-col gap-1.5 mb-3">
            {terms.map((term) => (
              <div
                key={term.id}
                className="flex items-center justify-between bg-white/3 border border-white/8 rounded-lg px-3 py-2"
              >
                <div className="flex items-center gap-2.5">
                  <button
                    onClick={() => handleToggle(term)}
                    className={`w-8 h-4 rounded-full transition-colors relative shrink-0 ${
                      term.enabled ? 'bg-emerald-500' : 'bg-white/10'
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${
                        term.enabled ? 'left-4' : 'left-0.5'
                      }`}
                    />
                  </button>
                  <span className={`text-sm ${term.enabled ? 'text-slate-300' : 'text-slate-600'}`}>
                    {term.term}
                  </span>
                </div>
                <button
                  onClick={() => handleDelete(term.id)}
                  className="text-slate-700 hover:text-red-400 transition-colors text-xs px-1"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>

          <form onSubmit={handleAdd} className="flex gap-2">
            <input
              type="text"
              value={newTerm}
              onChange={(e) => { setNewTerm(e.target.value); setError('') }}
              placeholder="Add a search term…"
              className="flex-1 bg-white/5 border border-white/10 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none focus:border-white/20 placeholder-slate-600"
            />
            <button
              type="submit"
              disabled={adding || !newTerm.trim()}
              className="text-sm px-4 py-2 rounded-lg bg-white/8 border border-white/10 text-slate-300 hover:bg-white/12 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {adding ? 'Adding…' : 'Add'}
            </button>
          </form>
          {error && <p className="text-xs text-red-400 mt-1.5">{error}</p>}
          <p className="text-xs text-slate-600 mt-2">
            Note: the watcher reads these from the DB on each run. Changes take effect on the next watcher cycle.
          </p>
        </>
      )}
    </section>
  )
}

function ConfigSection() {
  const [config, setConfig] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('http://localhost:8000/config')
      .then((r) => r.json())
      .then((d) => { setConfig(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const rows = config ? [
    { label: 'Watcher interval', value: `${config.watcher_interval_minutes} min` },
    { label: 'Auto-send window', value: `${config.approval_window_minutes} min after approval` },
    { label: 'Daily DM cap', value: config.daily_dm_cap },
    { label: 'Post retention', value: `${config.post_retention_days} days` },
    { label: 'Portfolio URL', value: config.portfolio_url },
    { label: 'Gmail', value: config.gmail_configured ? '✓ Configured' : '✗ Not configured' },
  ] : []

  return (
    <section>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-white">Config</h2>
        <p className="text-xs text-slate-500 mt-0.5">Read-only — edit backend/app/config.py to change</p>
      </div>

      {loading ? (
        <div className="text-slate-500 text-sm">Loading config…</div>
      ) : !config ? (
        <div className="text-slate-600 text-sm">Backend offline — start the server to see config</div>
      ) : (
        <div className="bg-white/3 border border-white/8 rounded-xl overflow-hidden">
          {rows.map((row, i) => (
            <div
              key={row.label}
              className={`flex items-center justify-between px-4 py-2.5 text-sm ${
                i < rows.length - 1 ? 'border-b border-white/5' : ''
              }`}
            >
              <span className="text-slate-500">{row.label}</span>
              <span className={`font-mono text-xs ${
                row.value === '✗ Not configured' ? 'text-amber-400' :
                row.value === '✓ Configured' ? 'text-emerald-400' :
                'text-slate-300'
              }`}>
                {row.value}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
