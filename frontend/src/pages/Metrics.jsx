import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

async function fetchMetrics() {
  const { data } = await api('/metrics')
  return data
}

export default function Metrics() {
  const { data: m, isLoading } = useQuery({
    queryKey: ['metrics'],
    queryFn: fetchMetrics,
    refetchInterval: 30_000,
  })

  if (isLoading || !m) return <div className="text-slate-500">Loading metrics…</div>

  const { calls, cost, latency_ms, per_day, funnel, approve_rate_by_bucket, quota } = m
  const maxDay = Math.max(1, ...per_day.map((d) => d.calls))

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold text-white">Metrics</h1>
        <p className="text-sm text-slate-500 mt-0.5">LLM cost & latency, the pipeline funnel, and quality signals</p>
      </div>

      {quota.paused && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-300">
          ⚠️ Scoring paused — daily LLM cap reached ({quota.today}/{quota.daily_cap}). Resets at midnight UTC.
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Card label="Calls today" value={calls.today} sub={`${calls.total} all-time`} />
        <Card label="Cost today" value={`$${cost.today_usd}`} sub={`$${cost.total_usd} all-time`} />
        <Card label="Parse OK" value={calls.parse_ok_pct != null ? `${calls.parse_ok_pct}%` : '—'} sub={`${calls.fell_back} fell back`} />
        <Card label="Latency p50/p95" value={latency_ms.p50 != null ? `${latency_ms.p50}/${latency_ms.p95}ms` : '—'} />
        <Card label="Daily quota" value={`${quota.today}/${quota.daily_cap}`} sub="LLM calls" />
      </div>

      <Section title="Backends">
        <KeyVals data={calls.by_backend} empty="no calls yet" />
      </Section>

      <Section title="Calls / day (last 14)">
        {per_day.length === 0 ? (
          <span className="text-slate-500 text-sm">no data yet</span>
        ) : (
          <div className="flex items-end gap-1 h-24">
            {per_day.map((d) => (
              <div key={d.day} className="flex-1 flex flex-col items-center justify-end"
                   title={`${d.day}: ${d.calls} calls, $${d.cost}`}>
                <div className="w-full rounded-t bg-emerald-500/60" style={{ height: `${(d.calls / maxDay) * 100}%` }} />
                <div className="mt-1 text-[9px] text-slate-500">{d.day.slice(5)}</div>
              </div>
            ))}
          </div>
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
          <table className="text-sm text-slate-300">
            <thead>
              <tr className="text-slate-500 text-left">
                <th className="pr-8 font-normal">bucket</th>
                <th className="pr-8 font-normal">posts</th>
                <th className="font-normal">approved</th>
              </tr>
            </thead>
            <tbody>
              {approve_rate_by_bucket.map((r) => (
                <tr key={r.bucket}>
                  <td className="pr-8">{r.bucket}</td>
                  <td className="pr-8">{r.total}</td>
                  <td>{r.approved} ({r.total ? Math.round((r.approved / r.total) * 100) : 0}%)</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Section>
    </div>
  )
}

function Card({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-4">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-white">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-500">{sub}</div>}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-4">
      <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-3">{title}</div>
      {children}
    </div>
  )
}

function KeyVals({ data, empty }) {
  const entries = Object.entries(data || {})
  if (entries.length === 0) return <span className="text-slate-500 text-sm">{empty}</span>
  return (
    <div className="flex flex-wrap gap-5 text-sm text-slate-300">
      {entries.map(([k, v]) => (
        <span key={k}><span className="text-slate-500">{k}</span> {v}</span>
      ))}
    </div>
  )
}
