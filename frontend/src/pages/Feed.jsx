import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { timeAgo } from '../lib/time'
import ScoreBadge from '../components/ScoreBadge'
import UrgencyDot from '../components/UrgencyDot'
import SetupChecklist from '../components/SetupChecklist'

const PAGE_SIZE = 20

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
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [liveQuery, setLiveQuery] = useState('')
  const [liveSearching, setLiveSearching] = useState(false)
  const [liveResult, setLiveResult] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    fetch('http://localhost:8000/status')
      .then((r) => r.json())
      .then((d) => setLastRunAt(d.last_run_at))
      .catch(() => {})
  }, [])

  async function fetchPosts(time, tab, searchQuery, currentPage) {
    setLoading(true)
    const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()

    let query = supabase
      .from('posts')
      .select('*', { count: 'exact' })
      .order('posted_at', { ascending: false })

    if (tab === 'drafts') {
      query = query.eq('status', 'drafted').lt('detected_at', oneDayAgo)
    } else {
      query = query.gte('detected_at', filterCutoff(time))
      if (tab === 'approved') query = query.in('status', ['approved', 'sent'])
      else if (tab === 'disapproved') query = query.eq('status', 'cancelled')
    }

    if (searchQuery.trim()) {
      const q = searchQuery.trim()
      query = query.or(`title.ilike.%${q}%,subreddit.ilike.%${q}%,author.ilike.%${q}%`)
    }

    const from = currentPage * PAGE_SIZE
    query = query.range(from, from + PAGE_SIZE - 1)

    const { data, count } = await query
    setPosts(data ?? [])
    setTotal(count ?? 0)
    setLoading(false)
  }

  // Reset page when filters or search change
  useEffect(() => { setPage(0) }, [timeFilter, statusTab, search])

  useEffect(() => {
    fetchPosts(timeFilter, statusTab, search, page)

    const channel = supabase
      .channel('posts-feed')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'posts' }, (payload) => {
        if (statusTab === 'all' && page === 0 && !search) {
          setPosts((prev) => [payload.new, ...prev].slice(0, PAGE_SIZE))
          setTotal((prev) => prev + 1)
        }
      })
      .subscribe()

    return () => supabase.removeChannel(channel)
  }, [timeFilter, statusTab, search, page])

  function handleDismiss(postId) {
    supabase.from('posts').update({ status: 'cancelled' }).eq('id', postId)
    setPosts((prev) => prev.filter((p) => p.id !== postId))
    setTotal((prev) => Math.max(0, prev - 1))
  }

  async function handleLiveSearch(e) {
    e.preventDefault()
    if (!liveQuery.trim() || liveSearching) return
    setLiveSearching(true)
    setLiveResult(null)
    try {
      const res = await fetch(`http://localhost:8000/search/reddit?q=${encodeURIComponent(liveQuery.trim())}`)
      const data = await res.json()
      setLiveResult(data)
      await fetchPosts(timeFilter, statusTab, search, 0)
      setPage(0)
    } catch {
      setLiveResult({ error: true })
    }
    setLiveSearching(false)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>
      <SetupChecklist />

      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-xl font-semibold text-white">Feed</h1>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-slate-500">
              {total} post{total !== 1 ? 's' : ''}
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

      {/* Search bars */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') setSearch(searchInput) }}
          placeholder="Filter by title, subreddit, author…"
          className="flex-1 bg-white/5 border border-white/10 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none focus:border-white/20 placeholder-slate-600"
        />
        {search && (
          <button
            onClick={() => { setSearch(''); setSearchInput('') }}
            className="text-xs px-3 py-2 rounded-lg border border-white/10 text-slate-500 hover:text-white bg-white/5 transition-colors"
          >
            Clear
          </button>
        )}
        {!search && (
          <button
            onClick={() => setSearch(searchInput)}
            className="text-xs px-3 py-2 rounded-lg border border-white/10 text-slate-400 bg-white/5 hover:bg-white/8 hover:text-slate-300 transition-colors"
          >
            Search feed
          </button>
        )}
      </div>

      {/* Live Reddit search */}
      <form onSubmit={handleLiveSearch} className="flex gap-2 mb-5">
        <input
          type="text"
          value={liveQuery}
          onChange={(e) => { setLiveQuery(e.target.value); setLiveResult(null) }}
          placeholder="Search Reddit live (e.g. hiring react developer)…"
          className="flex-1 bg-white/5 border border-white/10 text-slate-300 text-sm rounded-lg px-3 py-2 outline-none focus:border-white/20 placeholder-slate-600"
        />
        <button
          type="submit"
          disabled={liveSearching || !liveQuery.trim()}
          className="text-xs px-3 py-2 rounded-lg border border-white/10 text-slate-400 bg-white/5 hover:bg-white/8 hover:text-slate-300 disabled:opacity-40 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
        >
          {liveSearching ? 'Searching…' : 'Search Reddit'}
        </button>
        {liveResult && (
          <span className={`text-xs self-center ${liveResult.error ? 'text-red-400' : 'text-emerald-400'}`}>
            {liveResult.error ? 'Failed' : liveResult.new_posts > 0 ? `+${liveResult.new_posts} new` : 'No new posts'}
          </span>
        )}
      </form>

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
        <EmptyState tab={statusTab} hasSearch={!!search} />
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {posts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                onClick={() => navigate(`/review/${post.id}`)}
                onDismiss={() => handleDismiss(post.id)}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="text-xs px-4 py-2 rounded-lg border border-white/10 text-slate-400 bg-white/5 hover:bg-white/8 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                ← Previous
              </button>
              <span className="text-xs text-slate-600">
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="text-xs px-4 py-2 rounded-lg border border-white/10 text-slate-400 bg-white/5 hover:bg-white/8 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function EmptyState({ tab, hasSearch }) {
  if (hasSearch) return (
    <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
      <p className="text-slate-400 text-sm">No posts match your search</p>
    </div>
  )

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

function PostCard({ post, onClick, onDismiss }) {
  const ageMin = (Date.now() - new Date(post.posted_at).getTime()) / 60_000
  const urgencyBorder =
    ageMin < 30 ? 'border-emerald-500/30 hover:border-emerald-500/50' :
    ageMin < 90 ? 'border-yellow-500/30 hover:border-yellow-500/50' :
                  'border-red-500/20 hover:border-red-500/40'

  const daysOld = Math.floor((Date.now() - new Date(post.detected_at).getTime()) / (1000 * 60 * 60 * 24))
  const showAgeTag = (post.status === 'drafted' || post.status === 'new') && daysOld >= 1

  function handleDismiss(e) {
    e.stopPropagation()
    onDismiss()
  }

  return (
    <div
      onClick={onClick}
      className={`bg-white/3 border ${urgencyBorder} rounded-xl p-4 cursor-pointer hover:bg-white/5 transition-all group relative`}
    >
      <button
        onClick={handleDismiss}
        className="absolute top-3 right-3 w-6 h-6 flex items-center justify-center rounded-md text-slate-700 hover:text-red-400 hover:bg-white/5 transition-colors opacity-0 group-hover:opacity-100 text-xs"
        title="Dismiss post"
      >
        ✕
      </button>

      <div className="flex items-start justify-between gap-4 pr-6">
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
    } catch {}
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
