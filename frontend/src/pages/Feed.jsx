import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import ScoreBadge from '../components/ScoreBadge'
import UrgencyDot from '../components/UrgencyDot'

const TIME_FILTERS = [
  { label: 'Past hour', value: 'hour' },
  { label: 'Today', value: 'today' },
  { label: 'Past 3 days', value: '3days' },
  { label: 'Past week', value: 'week' },
]

function filterCutoff(value) {
  const now = new Date()
  if (value === 'hour') return new Date(now - 60 * 60 * 1000).toISOString()
  if (value === 'today') return new Date(now - 24 * 60 * 60 * 1000).toISOString()
  if (value === '3days') return new Date(now - 3 * 24 * 60 * 60 * 1000).toISOString()
  return new Date(now - 7 * 24 * 60 * 60 * 1000).toISOString()
}

export default function Feed() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [timeFilter, setTimeFilter] = useState('today')
  const navigate = useNavigate()

  async function fetchPosts(filter) {
    setLoading(true)
    const cutoff = filterCutoff(filter)
    const { data } = await supabase
      .from('posts')
      .select('*')
      .neq('status', 'cancelled')
      .gte('detected_at', cutoff)
      .order('detected_at', { ascending: false })
    setPosts(data ?? [])
    setLoading(false)
  }

  useEffect(() => {
    fetchPosts(timeFilter)

    const channel = supabase
      .channel('posts-feed')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'posts' }, (payload) => {
        setPosts((prev) => [payload.new, ...prev])
      })
      .subscribe()

    return () => supabase.removeChannel(channel)
  }, [timeFilter])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white">Feed</h1>
          <p className="text-sm text-slate-500 mt-0.5">{posts.length} post{posts.length !== 1 ? 's' : ''} detected</p>
        </div>
        <select
          value={timeFilter}
          onChange={(e) => setTimeFilter(e.target.value)}
          className="bg-white/5 border border-white/10 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none cursor-pointer hover:bg-white/8"
        >
          {TIME_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>{f.label}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-500 text-sm">
          Loading posts...
        </div>
      ) : posts.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-48 text-slate-500 text-sm gap-2">
          <span>No posts detected in this window</span>
          <span className="text-xs text-slate-600">The watcher runs every 2 minutes</span>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {posts.map((post) => (
            <PostCard
              key={post.id}
              post={post}
              onClick={() => navigate(`/review/${post.id}`)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function PostCard({ post, onClick }) {
  const ageMin = (Date.now() - new Date(post.detected_at).getTime()) / 60_000
  const urgencyBorder =
    ageMin < 30 ? 'border-emerald-500/30' :
    ageMin < 90 ? 'border-yellow-500/30' :
                  'border-red-500/30'

  return (
    <div
      onClick={onClick}
      className={`bg-white/3 border ${urgencyBorder} rounded-xl p-4 cursor-pointer hover:bg-white/6 transition-colors group`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-xs text-slate-500">r/{post.subreddit}</span>
            <span className="text-slate-700">·</span>
            <UrgencyDot postedAt={post.posted_at} />
          </div>
          <h3 className="text-sm font-medium text-white leading-snug line-clamp-2 group-hover:text-slate-100">
            {post.title}
          </h3>
          {post.score_reason && (
            <p className="text-xs text-slate-500 mt-1.5 line-clamp-1">{post.score_reason}</p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <ScoreBadge score={post.score} />
          <StatusPill status={post.status} />
        </div>
      </div>
    </div>
  )
}

function StatusPill({ status }) {
  const styles = {
    new: 'bg-slate-500/15 text-slate-400',
    drafted: 'bg-blue-500/15 text-blue-400',
    approved: 'bg-purple-500/15 text-purple-400',
    sent: 'bg-emerald-500/15 text-emerald-400',
    cancelled: 'bg-red-500/15 text-red-400',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${styles[status] ?? styles.new}`}>
      {status}
    </span>
  )
}
