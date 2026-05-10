import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { timeAgo } from '../lib/time'
import ScoreBadge from '../components/ScoreBadge'
import UrgencyDot from '../components/UrgencyDot'
import SetupChecklist from '../components/SetupChecklist'

const TIME_FILTERS = [
  { label: 'Past hour', value: 'hour' },
  { label: 'Today', value: 'today' },
]

const STATUS_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Drafts', value: 'drafts' },
  { label: 'Approved', value: 'approved' },
  { label: 'Disapproved', value: 'disapproved' },
]

function filterCutoff(value) {
  const now = new Date()
  if (value === 'hour') return new Date(now - 60 * 60 * 1000).toISOString()
  return new Date(now - 24 * 60 * 60 * 1000).toISOString()
}

export default function Feed() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [timeFilter, setTimeFilter] = useState('today')
  const [statusTab, setStatusTab] = useState('all')
  const [lastRunAt, setLastRunAt] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    fetch('http://localhost:8000/status')
      .then((r) => r.json())
      .then((d) => setLastRunAt(d.last_run_at))
      .catch(() => {})
  }, [])

  async function fetchPosts(time, tab) {
    setLoading(true)
    const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()

    let query = supabase
      .from('posts')
      .select('*')
      .order('detected_at', { ascending: false })

    if (tab === 'drafts') {
      query = query.eq('status', 'drafted').lt('detected_at', oneDayAgo)
    } else {
      query = query.gte('detected_at', filterCutoff(time))
      if (tab === 'approved') query = query.in('status', ['approved', 'sent'])
      else if (tab === 'disapproved') query = query.eq('status', 'cancelled')
    }

    const { data } = await query
    setPosts(data ?? [])
    setLoading(false)
  }

  useEffect(() => {
    fetchPosts(timeFilter, statusTab)

    const channel = supabase
      .channel('posts-feed')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'posts' }, (payload) => {
        if (statusTab === 'all') setPosts((prev) => [payload.new, ...prev])
      })
      .subscribe()

    return () => supabase.removeChannel(channel)
  }, [timeFilter, statusTab])

  return (
    <div>
      <SetupChecklist />

      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-white">Feed</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-slate-500">
              {posts.length} post{posts.length !== 1 ? 's' : ''}
            </p>
            {lastRunAt && (
              <>
                <span className="text-slate-700">·</span>
                <p className="text-xs text-slate-600">checked {timeAgo(lastRunAt)}</p>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <BackfillButton />
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
      </div>

      <div className="flex gap-1 border-b border-white/8 mb-5">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusTab(tab.value)}
            className={`px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px ${
              statusTab === tab.value
                ? 'text-white border-white'
                : 'text-slate-500 border-transparent hover:text-slate-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-500 text-sm">
          Loading posts...
        </div>
      ) : posts.length === 0 ? (
        <EmptyState tab={statusTab} />
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

function EmptyState({ tab }) {
  const messages = {
    all: 'No posts in this window',
    drafts: 'No stale drafts — all posts reviewed within 24 hours',
    approved: 'No approved posts yet',
    disapproved: 'No disapproved posts yet',
  }
  return (
    <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
      <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center">
        <span className="text-slate-500 text-sm">○</span>
      </div>
      <div>
        <p className="text-slate-400 text-sm">{messages[tab]}</p>
        {tab === 'all' && (
          <p className="text-slate-600 text-xs mt-1">Watcher runs every 2 minutes — posts appear here in real time</p>
        )}
      </div>
    </div>
  )
}

function PostCard({ post, onClick }) {
  const ageMin = (Date.now() - new Date(post.posted_at).getTime()) / 60_000
  const urgencyBorder =
    ageMin < 30 ? 'border-emerald-500/30 hover:border-emerald-500/50' :
    ageMin < 90 ? 'border-yellow-500/30 hover:border-yellow-500/50' :
                  'border-red-500/20 hover:border-red-500/40'

  const daysOld = Math.floor((Date.now() - new Date(post.detected_at).getTime()) / (1000 * 60 * 60 * 24))
  const showAgeTag = (post.status === 'drafted' || post.status === 'new') && daysOld >= 1

  return (
    <div
      onClick={onClick}
      className={`bg-white/3 border ${urgencyBorder} rounded-xl p-4 cursor-pointer hover:bg-white/5 transition-all group`}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="text-xs font-medium text-slate-400">r/{post.subreddit}</span>
            <span className="text-slate-700">·</span>
            <UrgencyDot postedAt={post.posted_at} />
            {post.author && (
              <>
                <span className="text-slate-700">·</span>
                <span className="text-xs text-slate-600">u/{post.author}</span>
              </>
            )}
          </div>
          <h3 className="text-sm font-medium text-white leading-snug line-clamp-2 group-hover:text-slate-100 mb-1.5">
            {post.title}
          </h3>
          {post.score_reason && (
            <p className="text-xs text-slate-500 line-clamp-1 mb-1.5">{post.score_reason}</p>
          )}
          {(post.num_comments > 0 || post.reddit_upvotes > 0) && (
            <div className="flex items-center gap-2 text-xs text-slate-600">
              {post.reddit_upvotes > 0 && <span>↑ {post.reddit_upvotes}</span>}
              {post.num_comments > 0 && <span>💬 {post.num_comments}</span>}
            </div>
          )}
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <ScoreBadge score={post.score} />
          <div className="flex items-center gap-1.5 flex-wrap justify-end">
            {showAgeTag && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400">
                {daysOld}d old
              </span>
            )}
            <StatusPill status={post.status} />
          </div>
        </div>
      </div>
    </div>
  )
}

function BackfillButton() {
  const [state, setState] = useState('idle')

  async function handleClick() {
    if (state !== 'idle') return
    setState('loading')
    try {
      await fetch('http://localhost:8000/watcher/backfill')
    } catch {
      // fire-and-forget
    }
    setState('done')
    setTimeout(() => setState('idle'), 3000)
  }

  const label =
    state === 'loading' ? 'Triggering…' :
    state === 'done'    ? 'Triggered ✓' :
                          'Backfill 24h'

  return (
    <div className="relative group">
      <button
        onClick={handleClick}
        disabled={state !== 'idle'}
        className="text-xs px-3 py-2 rounded-lg border border-white/10 text-slate-400 bg-white/5 hover:bg-white/8 hover:text-slate-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {label}
      </button>
      <div className="absolute right-0 top-full mt-2 w-64 bg-slate-900 border border-white/10 rounded-lg px-3 py-2 text-xs text-slate-400 leading-relaxed opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 shadow-xl">
        Fetches all posts from the last 24 hours. Use this after restarting the server to fill any gaps the watcher may have missed.
      </div>
    </div>
  )
}

function StatusPill({ status }) {
  const styles = {
    new:       'bg-slate-500/15 text-slate-400',
    drafted:   'bg-blue-500/15 text-blue-400',
    approved:  'bg-purple-500/15 text-purple-400',
    sent:      'bg-emerald-500/15 text-emerald-400',
    cancelled: 'bg-red-500/15 text-red-400',
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${styles[status] ?? styles.new}`}>
      {status}
    </span>
  )
}
