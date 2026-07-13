import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supabase } from '../lib/supabase'
import { API } from '../lib/api'
import { timeAgo, timeUntil } from '../lib/time'
import ScoreBadge from '../components/ScoreBadge'

async function fetchQueue() {
  const { data } = await supabase
    .from('messages')
    .select('*, posts(*)')
    .eq('status', 'approved')
    .order('send_after', { ascending: true })
  return data ?? []
}

export default function Queue() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: items = [], isLoading, isFetching } = useQuery({
    queryKey: ['queue'],
    queryFn: fetchQueue,
    refetchInterval: 30_000,
  })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">Queue</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {items.length} approved message{items.length !== 1 ? 's' : ''} waiting to send
          </p>
        </div>
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ['queue'] })}
          disabled={isFetching}
          className="text-xs px-3 py-1.5 rounded-lg border border-white/10 text-slate-400 bg-white/5 hover:bg-white/8 hover:text-white disabled:opacity-40 transition-colors flex items-center gap-1.5"
        >
          <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" className={isFetching ? 'animate-spin' : ''}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center h-48 text-slate-500 text-sm">
          Loading queue...
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
          <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center">
            <span className="text-slate-500 text-sm">○</span>
          </div>
          <div>
            <p className="text-slate-400 text-sm">Queue is empty</p>
            <p className="text-slate-600 text-xs mt-1">Approve messages in the Feed to queue them here</p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map((item) => (
            <QueueCard
              key={item.id}
              item={item}
              onViewPost={() => navigate(`/review/${item.post_id}`)}
              onSent={() => queryClient.invalidateQueries({ queryKey: ['queue'] })}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function QueueCard({ item, onViewPost, onSent }) {
  const post = item.posts
  const sendAfter = item.send_after ? new Date(item.send_after) : null
  const isPast = sendAfter && sendAfter < new Date()
  const [sending, setSending] = useState(false)
  const [result, setResult] = useState(null)

  async function handleSendNow() {
    if (sending) return
    setSending(true)
    try {
      const res = await fetch(`${API}/messages/${item.id}/send`, { method: 'POST' })
      const data = await res.json()
      setResult(data)
      setTimeout(() => onSent?.(), 1500)
    } catch {
      setResult({ sent: false, reason: 'Backend unreachable' })
    } finally {
      setSending(false)
    }
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
            {post?.posted_at && (
              <>
                <span className="text-slate-700">·</span>
                <span className="text-xs text-slate-600">posted {timeAgo(post.posted_at)}</span>
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
        <ScoreBadge score={post?.score} />
      </div>

      <div className="bg-white/3 border border-white/5 rounded-lg px-3 py-2.5 mb-3">
        <p className="text-xs text-slate-400 leading-relaxed line-clamp-3 whitespace-pre-wrap">
          {item.final_message || item.draft}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div className="text-xs text-slate-600">
          {result ? (
            result.sent
              ? <span className="text-emerald-400">{result.dry_run ? 'Dry run — logged ✓' : 'Sent ✓'}</span>
              : <span className="text-red-400">Failed: {result.reason}</span>
          ) : sendAfter ? (
            isPast
              ? <span className="text-amber-400">Scheduled time passed</span>
              : <span className="text-slate-400">sends in {timeUntil(item.send_after)}</span>
          ) : (
            <span>No send time set</span>
          )}
        </div>
        <button
          onClick={handleSendNow}
          disabled={sending || !!result}
          className="text-xs px-3 py-1.5 rounded-lg border border-white/10 text-slate-300 bg-white/5 hover:bg-white/8 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          {sending ? 'Sending…' : result ? 'Done' : 'Send Now'}
        </button>
      </div>
    </div>
  )
}
