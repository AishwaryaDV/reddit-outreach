import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

async function fetchMetrics() {
  const { data } = await api('/metrics')
  return data
}

const fmtMs = (ms) => (ms == null ? '—' : ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`)

export default function Metrics() {
  const { data: m, isLoading } = useQuery({
    queryKey: ['metrics'],
    queryFn: fetchMetrics,
    refetchInterval: 30_000,
  })

  if (isLoading || !m) return <div className="text-slate-500 text-sm">Loading metrics…</div>

  const { calls, cost, latency_ms, per_day, funnel, approve_rate_by_bucket, quota } = m
  const maxDay = Math.max(1, ...per_day.map((d) => d.calls))

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold text-white">Metrics</h1>
        <p className="text-sm text-slate-500 mt-0.5">LLM cost & latency, the pipeline funnel, and quality signals</p>
      </div>

      {quota.paused && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          Scoring paused — daily LLM cap reached ({quota.today}/{quota.daily_cap}). Resets at midnight UTC.
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card label="Calls today" value={calls.today} sub={`${calls.total} all-time`} />
        <Card label="Cost today" value={`$${cost.today_usd}`} sub={`$${cost.total_usd} all-time`} />
        <Card label="Parse OK" value={calls.parse_ok_pct != null ? `${calls.parse_ok_pct}%` : '—'} sub={`${calls.fell_back} fell back`} />
        <Card label="Latency p50/p95" value={latency_ms.p50 != null ? `${fmtMs(latency_ms.p50)} / ${fmtMs(latency_ms.p95)}` : '—'} />
        <Card label="Daily quota" value={`${quota.today}/${quota.daily_cap}`} sub="LLM calls" />
      </div>

      <Section title="Backends">
        <BackendBar data={calls.by_backend} />
      </Section>

      <Section title="Calls / day (last 14)">
        {per_day.length === 0 ? (
          <span className="text-slate-500 text-sm">no data yet</span>
        ) : (
          <>
            <div className="flex gap-2 h-28">
              {per_day.map((d) => (
                <div key={d.day} className="flex-1 h-full flex items-end" title={`${d.day}: ${d.calls} calls, $${d.cost}`}>
                  <div className="w-full rounded-t bg-emerald-500/70 min-h-[2px]"
                       style={{ height: `${(d.calls / maxDay) * 100}%` }} />
                </div>
              ))}
            </div>
            <div className="flex gap-2 mt-2">
              {per_day.map((d) => (
                <div key={d.day} className="flex-1 text-center text-xs text-slate-500">{d.day.slice(5)}</div>
              ))}
            </div>
          </>
        )}
      </Section>

      <Section title="Funnel — posts by status">
        <KeyVals data={funnel.posts} empty="no posts yet" />
      </Section>
      <Section title="Messages by status">
        <KeyVals data={funnel.messages} empty="no messages yet" />
      </Section>

      <Section title="Approve rate by score bucket">
        {approve_rate_by_bucket.length === 0 ? (
          <span className="text-slate-500 text-sm">no scored posts yet</span>
        ) : (
          <div className="flex flex-col gap-2">
            {approve_rate_by_bucket.map((r) => (
              <div key={r.bucket} className="flex items-center gap-3 text-sm">
                <span className="w-12 text-slate-500 tabular-nums">{r.bucket}</span>
                <div className="flex-1 h-2 rounded-full bg-white/8 overflow-hidden">
                  <div className="h-full rounded-full bg-emerald-500/70"
                       style={{ width: `${r.total ? (r.approved / r.total) * 100 : 0}%` }} />
                </div>
                <span className="w-24 text-right text-slate-400 tabular-nums">
                  {r.approved}/{r.total} ({r.total ? Math.round((r.approved / r.total) * 100) : 0}%)
                </span>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  )
}

function Card({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/3 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-white tabular-nums">{value}</div>
      <div className="mt-1 text-xs text-slate-600 h-4">{sub || ''}</div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="rounded-xl border border-white/8 bg-white/3 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500 mb-3">{title}</div>
      {children}
    </div>
  )
}

const BACKEND_COLORS = {
  claude_sdk: 'bg-violet-500/70',
  gemini: 'bg-emerald-500/70',
  replay: 'bg-slate-500/60',
}

function BackendBar({ data }) {
  const entries = Object.entries(data || {})
  const total = entries.reduce((sum, [, v]) => sum + v, 0)
  if (total === 0) return <span className="text-slate-500 text-sm">no calls yet</span>
  return (
    <div className="flex flex-col gap-3">
      <div className="flex h-3 rounded-full overflow-hidden bg-white/5">
        {entries.map(([k, v]) => (
          <div key={k} className={BACKEND_COLORS[k] || 'bg-sky-500/70'}
               style={{ width: `${(v / total) * 100}%` }} title={`${k}: ${v}`} />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1.5 text-sm">
        {entries.map(([k, v]) => (
          <span key={k} className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-sm ${BACKEND_COLORS[k] || 'bg-sky-500/70'}`} />
            <span className="text-slate-400">{k}</span>
            <span className="text-slate-200 tabular-nums">{v}</span>
            <span className="text-slate-600 tabular-nums">({Math.round((v / total) * 100)}%)</span>
          </span>
        ))}
      </div>
    </div>
  )
}

function KeyVals({ data, empty }) {
  const entries = Object.entries(data || {})
  if (entries.length === 0) return <span className="text-slate-500 text-sm">{empty}</span>
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-slate-300">
      {entries.map(([k, v]) => (
        <span key={k}>
          <span className="text-slate-500">{k}</span> <span className="tabular-nums">{v}</span>
        </span>
      ))}
    </div>
  )
}
