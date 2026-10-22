import { useEffect, useState } from 'react'
import { API, api } from '../lib/api'
import type { Config, SearchTerm } from '../types'

export default function Settings() {
  return (
    <div className="flex flex-col gap-8 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-white">Settings</h1>
        <p className="text-sm text-slate-500 mt-0.5">Configure the tool without touching code</p>
      </div>
      <NotificationsSection />
      <AutomationSection />
      <SearchTermsSection />
      <ConfigSection />
    </div>
  )
}

function NotificationsSection() {
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState(false)

  useEffect(() => {
    fetch(`${API}/notifications/status`)
      .then((r) => r.json())
      .then((d) => { setEnabled(d.enabled); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  async function handleToggle() {
    if (toggling) return
    setToggling(true)
    try {
      const res = await fetch(`${API}/notifications/toggle`, { method: 'POST' })
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

function AutomationSection() {
  const [config, setConfig] = useState<Config | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API}/config`).then((r) => r.json()).then(setConfig).catch(() => {})
  }, [])

  async function toggle(key, next) {
    setSaving(key)
    try {
      const res = await fetch(`${API}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value: String(next) }),
      })
      setConfig(await res.json())
    } catch {
      // backend offline
    }
    setSaving(null)
  }

  return (
    <section>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-white">Automation</h2>
        <p className="text-xs text-slate-500 mt-0.5">Control how much the tool does on its own</p>
      </div>

      <div className="flex flex-col gap-1.5">
        <ToggleRow
          label="Auto-send after review window"
          desc={config?.auto_send_enabled
            ? 'Un-actioned drafts send automatically once their review window elapses'
            : 'Only messages you explicitly approve are sent (recommended)'}
          on={!!config?.auto_send_enabled}
          disabled={!config || saving === 'auto_send_enabled'}
          onClick={() => toggle('auto_send_enabled', !config?.auto_send_enabled)}
        />
        <ToggleRow
          label="Scoring enabled"
          desc={config && !config.scoring_enabled
            ? 'Paused — no LLM calls, no new drafts'
            : 'New posts are scored and drafted by the LLM'}
          on={config ? !!config.scoring_enabled : true}
          disabled={!config || saving === 'scoring_enabled'}
          onClick={() => toggle('scoring_enabled', !config?.scoring_enabled)}
        />
      </div>

      {config?.daily_llm_cap != null && (
        <p className="text-xs text-slate-600 mt-2">
          Daily LLM cap: {config.daily_llm_cap} calls — scoring pauses for the day when hit.
        </p>
      )}
    </section>
  )
}

function ToggleRow({ label, desc, on, disabled, onClick }) {
  return (
    <div className="bg-white/3 border border-white/8 rounded-xl px-4 py-3 flex items-center justify-between">
      <div className="pr-4">
        <p className="text-sm text-slate-300">{label}</p>
        <p className="text-xs text-slate-600 mt-0.5">{desc}</p>
      </div>
      <button
        onClick={onClick}
        disabled={disabled}
        className={`w-11 h-6 rounded-full transition-colors relative shrink-0 disabled:opacity-40 ${
          on ? 'bg-emerald-500' : 'bg-white/10'
        }`}
      >
        <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all ${
          on ? 'left-5' : 'left-0.5'
        }`} />
      </button>
    </div>
  )
}

function SearchTermsSection() {
  const [terms, setTerms] = useState<SearchTerm[]>([])
  const [loading, setLoading] = useState(true)
  const [newTerm, setNewTerm] = useState('')
  const [adding, setAdding] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    load()
  }, [])

  async function load() {
    const { data } = await api('/search-terms')
    setTerms(data ?? [])
    setLoading(false)
  }

  async function handleToggle(term) {
    const { ok } = await api(`/search-terms/${term.id}`, { method: 'PATCH', body: { active: !term.active } })
    if (!ok) return
    setTerms((prev) =>
      prev.map((t) => (t.id === term.id ? { ...t, active: !t.active } : t))
    )
  }

  async function handleDelete(id) {
    await api(`/search-terms/${id}`, { method: 'DELETE' })
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
    const { ok, status, data } = await api('/search-terms', { method: 'POST', body: { term: trimmed } })
    if (!ok) {
      setError(status === 409 ? 'Term already exists' : 'Failed to add term')
    } else {
      setTerms((prev) => [...prev, data])
      setNewTerm('')
    }
    setAdding(false)
  }

  const enabledCount = terms.filter((t) => t.active).length

  return (
    <section>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-white">Search Terms</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          {enabledCount} of {terms.length} enabled — watcher uses these to search Reddit every 10 minutes
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
                      term.active ? 'bg-emerald-500' : 'bg-white/10'
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${
                        term.active ? 'left-4' : 'left-0.5'
                      }`}
                    />
                  </button>
                  <span className={`text-sm ${term.active ? 'text-slate-300' : 'text-slate-600'}`}>
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
  const [config, setConfig] = useState<Config | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API}/config`)
      .then((r) => r.json())
      .then((d) => { setConfig(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  async function handleSave(key, value) {
    setSaving(key)
    try {
      const res = await fetch(`${API}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value: String(value) }),
      })
      const data = await res.json()
      setConfig(data)
    } catch {
      // backend unreachable
    }
    setSaving(null)
  }

  const editableRows = config ? [
    { label: 'Portfolio URL', key: 'portfolio_url', value: config.portfolio_url, type: 'text' },
    { label: 'Daily DM cap', key: 'daily_dm_cap', value: config.daily_dm_cap, type: 'number' },
    { label: 'Approval window (min)', key: 'approval_window_min', value: config.approval_window_min, type: 'number' },
    { label: 'Approval window (max)', key: 'approval_window_max', value: config.approval_window_max, type: 'number' },
  ] : []

  const readOnlyRows = config ? [
    { label: 'Watcher interval', value: `${config.watcher_interval_minutes} min` },
    { label: 'Post retention', value: `${config.post_retention_days} days` },
    { label: 'Gmail', value: config.gmail_configured ? '✓ Configured' : '✗ Not configured' },
  ] : []

  return (
    <section>
      <div className="mb-3">
        <h2 className="text-sm font-semibold text-white">Config</h2>
        <p className="text-xs text-slate-500 mt-0.5">Edit values below — changes take effect on the next watcher cycle</p>
      </div>

      {loading ? (
        <div className="text-slate-500 text-sm">Loading config…</div>
      ) : !config ? (
        <div className="text-slate-600 text-sm">Backend offline — start the server to see config</div>
      ) : (
        <div className="bg-white/3 border border-white/8 rounded-xl overflow-hidden">
          {editableRows.map((row) => (
            <EditableConfigRow
              key={row.key}
              label={row.label}
              value={row.value}
              type={row.type}
              saving={saving === row.key}
              onSave={(val) => handleSave(row.key, val)}
            />
          ))}
          {readOnlyRows.map((row, i) => (
            <div
              key={row.label}
              className={`flex items-center justify-between px-4 py-2.5 text-sm ${
                i < readOnlyRows.length - 1 ? 'border-b border-white/5' : ''
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

function EditableConfigRow({ label, value, type, saving, onSave }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(String(value))

  function handleSubmit(e) {
    e.preventDefault()
    const trimmed = draft.trim()
    if (!trimmed || trimmed === String(value)) { setEditing(false); return }
    onSave(trimmed)
    setEditing(false)
  }

  return (
    <div className="flex items-center justify-between px-4 py-2.5 text-sm border-b border-white/5">
      <span className="text-slate-500">{label}</span>
      {editing ? (
        <form onSubmit={handleSubmit} className="flex items-center gap-2">
          <input
            autoFocus
            type={type}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => setEditing(false)}
            className="bg-white/5 border border-white/10 text-slate-300 text-xs font-mono rounded px-2 py-1 outline-none focus:border-white/20 w-40 text-right"
          />
        </form>
      ) : (
        <button
          onClick={() => { setDraft(String(value)); setEditing(true) }}
          disabled={saving}
          className="font-mono text-xs text-slate-300 hover:text-white transition-colors cursor-pointer bg-transparent border-none p-0"
        >
          {saving ? '…' : value}
        </button>
      )}
    </div>
  )
}
