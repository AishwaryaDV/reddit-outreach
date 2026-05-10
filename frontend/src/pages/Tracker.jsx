import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { timeAgo } from '../lib/time'
import ScoreBadge from '../components/ScoreBadge'

export default function Tracker() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from('messages')
        .select('*, posts(*)')
        .eq('status', 'sent')
        .order('created_at', { ascending: false })

      setItems(data ?? [])
      setLoading(false)
    }
    load()
  }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">Tracker</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            {items.length} DM{items.length !== 1 ? 's' : ''} sent
          </p>
        </div>
        <span className="text-xs px-2.5 py-1 rounded-full bg-slate-500/15 text-slate-500 border border-white/5">
          Reply tracking in Phase 5
        </span>
      </div>

      {loading ? (
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
            />
          ))}
        </div>
      )}
    </div>
  )
}

function TrackerCard({ item, onViewPost }) {
  const post = item.posts
  const sentAt = item.updated_at ? new Date(item.updated_at) : null

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
                <span className="text-xs text-slate-600">sent {timeAgo(item.updated_at)}</span>
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
          <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">sent</span>
        </div>
      </div>

      <div className="bg-white/3 border border-white/5 rounded-lg px-3 py-2.5 mb-3">
        <p className="text-xs text-slate-400 leading-relaxed line-clamp-3 whitespace-pre-wrap">
          {item.final_message || item.draft}
        </p>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-600 italic">No reply yet — reply tracking in Phase 5</span>
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
