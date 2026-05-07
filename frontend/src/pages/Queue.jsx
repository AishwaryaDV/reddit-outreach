import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import ScoreBadge from '../components/ScoreBadge'

export default function Queue() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from('messages')
        .select('*, posts(*)')
        .eq('status', 'approved')
        .order('send_after', { ascending: true })

      setItems(data ?? [])
      setLoading(false)
    }
    load()
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">Queue</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {items.length} approved message{items.length !== 1 ? 's' : ''} waiting to send
          </p>
        </div>
      </div>

      {loading ? (
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
            />
          ))}
        </div>
      )}
    </div>
  )
}

function QueueCard({ item, onViewPost }) {
  const post = item.posts
  const sendAfter = item.send_after ? new Date(item.send_after) : null
  const isPast = sendAfter && sendAfter < new Date()

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
          {sendAfter ? (
            isPast
              ? <span className="text-amber-400">Scheduled time passed — waiting for Phase 4</span>
              : <span>Scheduled: {sendAfter.toLocaleString()}</span>
          ) : (
            <span>No send time set</span>
          )}
        </div>
        <div className="relative group">
          <button
            disabled
            className="text-xs px-3 py-1.5 rounded-lg border border-white/10 text-slate-600 bg-white/3 cursor-not-allowed opacity-50"
          >
            Send Now
          </button>
          <div className="absolute right-0 bottom-full mb-2 w-56 bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-xs text-slate-400 leading-relaxed opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 shadow-xl">
            DM sending wires up in Phase 4 — needs Reddit karma first
          </div>
        </div>
      </div>
    </div>
  )
}
