import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import { timeAgo } from '../lib/time'
import ScoreBadge from '../components/ScoreBadge'

const OUTCOMES = ['', 'ignored', 'responded', 'hired', 'ongoing']

async function fetchSent() {
  const { data } = await supabase
    .from('messages')
    .select('*, posts(*)')
    .in('status', ['sent', 'dry_sent'])
    .order('sent_at', { ascending: false, nullsFirst: false })
  return data ?? []
}

export default function Tracker() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: items = [], isLoading, isFetching } = useQuery({
    queryKey: ['tracker'],
    queryFn: fetchSent,
    refetchInterval: 30_000,
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">Tracker</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {items.length} DM{items.length !== 1 ? 's' : ''} sent
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ['tracker'] })}
            disabled={isFetching}
            className="text-xs px-3 py-1.5 rounded-lg border border-white/10 text-slate-400 bg-white/5 hover:bg-white/8 hover:text-white disabled:opacity-40 transition-colors flex items-center gap-1.5"
          >
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" className={isFetching ? 'animate-spin' : ''}>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
          <span className="text-xs px-2.5 py-1 rounded-full bg-slate-500/15 text-slate-500 border border-white/5">
            Reply tracking in Phase 5
          </span>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-48 text-slate-500 text-sm">
          Loading history...
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
          <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center">
            <span className="text-slate-500 text-sm">○</span>
          </div>
          <div>
            <p className="text-slate-400 text-sm">No DMs sent yet</p>
            <p className="text-slate-600 text-xs mt-1">Sent messages will appear here once Phase 4 is live</p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <TrackerCard
              key={item.id}
              item={item}
              onViewPost={() => navigate(`/review/${item.post_id}`)}
              onOutcomeChange={() => queryClient.invalidateQueries({ queryKey: ['tracker'] })}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function TrackerCard({ item, onViewPost, onOutcomeChange }) {
  const post = item.posts
  const sentAt = item.sent_at ? new Date(item.sent_at) : null
  const isDry = item.status === 'dry_sent'
  const [saving, setSaving] = useState(false)

  async function handleOutcome(value) {
    setSaving(true)
    await supabase
      .from('messages')
      .update({ outcome: value || null })
      .eq('id', item.id)
    setSaving(false)
    onOutcomeChange?.()
  }

  return (
    <div className="bg-white/3 border border-white/8 rounded-xl p-4">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="text-xs font-medium text-slate-400">r/{post?.subreddit}</span>
            {post?.author && (
              <>
                <span className="text-slate-700">·</span>
                <span className="text-xs text-slate-600">u/{post.author}</span>
              </>
            )}
            {sentAt && (
              <>
                <span className="text-slate-700">·</span>
                <span className="text-xs text-slate-600">{isDry ? 'dry-run' : 'sent'} {timeAgo(item.sent_at)}</span>
              </>
            )}
          </div>
          <h3
            className="text-sm font-medium text-white leading-snug line-clamp-1 hover:text-slate-200 cursor-pointer"
            onClick={onViewPost}
          >
            {post?.title}
          </h3>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <ScoreBadge score={post?.score} />
          <span className={`text-xs px-2 py-0.5 rounded-full ${isDry ? 'bg-amber-500/15 text-amber-400' : 'bg-emerald-500/15 text-emerald-400'}`}>
            {isDry ? 'dry-run' : 'sent'}
          </span>
        </div>
      </div>

      <div className="bg-white/3 border border-white/5 rounded-lg px-3 py-2.5 mb-3">
        <p className="text-xs text-slate-400 leading-relaxed line-clamp-3 whitespace-pre-wrap">
          {item.final_message || item.draft}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <select
            value={item.outcome || ''}
            onChange={(e) => handleOutcome(e.target.value)}
            disabled={saving}
            className="text-xs bg-white/5 border border-white/10 text-slate-400 rounded-lg px-2 py-1 outline-none cursor-pointer"
          >
            <option value="">No outcome</option>
            <option value="ignored">Ignored</option>
            <option value="responded">Responded</option>
            <option value="hired">Hired</option>
            <option value="ongoing">Ongoing</option>
          </select>
          {item.outcome && (
            <OutcomeBadge outcome={item.outcome} />
          )}
        </div>
        <a
          href={`https://reddit.com/comments/${post?.reddit_post_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-slate-500 hover:text-white transition-colors"
        >
          View post →
        </a>
      </div>
    </div>
  )
}

function OutcomeBadge({ outcome }) {
  const styles = {
    ignored:   { bg: 'bg-slate-500/15', color: 'text-slate-500' },
    responded: { bg: 'bg-sky-500/15', color: 'text-sky-400' },
    hired:     { bg: 'bg-emerald-500/15', color: 'text-emerald-400' },
    ongoing:   { bg: 'bg-amber-500/15', color: 'text-amber-400' },
  }
  const s = styles[outcome] || styles.ignored
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${s.bg} ${s.color} capitalize`}>
      {outcome}
    </span>
  )
}
