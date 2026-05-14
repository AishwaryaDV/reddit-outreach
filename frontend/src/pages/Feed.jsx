import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { timeAgo } from '../lib/time'
import SetupChecklist from '../components/SetupChecklist'
import CustomSelect from '../components/CustomSelect'

const PAGE_SIZE = 20
const ACCENT = '#ff4500'

const TIME_FILTERS = [
  { label: 'Past hour', value: 'hour' },
  { label: 'Today', value: 'today' },
]

const STATUS_TABS = [
  { label: 'All', value: 'all' },
  { label: 'Drafts', value: 'drafts' },
  { label: 'Approved', value: 'approved' },
  { label: 'Disapproved', value: 'disapproved' },
  { label: 'Search', value: 'search' },
]

const SUB_COLORS = {
  saas: '#7c5cff',
  reactjs: '#22d3a8',
  webdev: '#ff8a3d',
  startups: '#f5cc4b',
  entrepreneur: '#ff5d8f',
  growmybusiness: '#5cc2ff',
  marketing: '#c084fc',
  sideproject: '#34d399',
  entrepreneurridealone: '#fbbf24',
}

function subColor(sub) {
  const key = (sub || '').toLowerCase()
  if (SUB_COLORS[key]) return SUB_COLORS[key]
  let h = 0
  for (let i = 0; i < key.length; i++) h = ((h << 5) - h + key.charCodeAt(i)) | 0
  const colors = Object.values(SUB_COLORS)
  return colors[Math.abs(h) % colors.length]
}

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
  const [selectedPostId, setSelectedPostId] = useState(() => sessionStorage.getItem('lastOpenedPostId'))
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [sortOrder, setSortOrder] = useState('newest')
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const [liveQuery, setLiveQuery] = useState('')
  const [liveSearching, setLiveSearching] = useState(false)
  const [liveResult, setLiveResult] = useState(null)
  const [deleteConfirm, setDeleteConfirm] = useState(null)
  const navigate = useNavigate()

  useEffect(() => {
    fetch('http://localhost:8000/status')
      .then((r) => r.json())
      .then((d) => setLastRunAt(d.last_run_at))
      .catch(() => {})
  }, [])

  async function fetchPosts(time, tab, searchQuery, currentPage, sort) {
    setLoading(true)
    const oneDayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString()

    let query = supabase
      .from('posts')
      .select('*', { count: 'exact' })
      .order('posted_at', { ascending: sort === 'oldest' })

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

  useEffect(() => { setPage(0) }, [timeFilter, statusTab, search, sortOrder])

  useEffect(() => {
    if (statusTab === 'search') return
    fetchPosts(timeFilter, statusTab, search, page, sortOrder)

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
  }, [timeFilter, statusTab, search, page, sortOrder])

  async function handleDelete(postId) {
    await supabase.from('messages').delete().eq('post_id', postId)
    await supabase.from('posts').delete().eq('id', postId)
    setPosts((prev) => prev.filter((p) => p.id !== postId))
    setTotal((prev) => Math.max(0, prev - 1))
    setDeleteConfirm(null)
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
    } catch {
      setLiveResult({ error: true })
    }
    setLiveSearching(false)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const fromRow = total === 0 ? 0 : page * PAGE_SIZE + 1
  const toRow = Math.min((page + 1) * PAGE_SIZE, total)

  return (
    <div>
      <SetupChecklist />

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, letterSpacing: -0.5, color: '#f5f5f5' }}>
          Feed
        </h1>
        <div style={{ fontSize: 12.5, color: '#7a7a7a' }}>
          <span style={{ color: '#e5e5e5', fontWeight: 500 }}>{total}</span> posts detected
          {lastRunAt && (
            <> · checked <span style={{ color: '#9a9a9a' }}>{timeAgo(lastRunAt)}</span></>
          )}
        </div>
      </div>

      {/* Controls row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        {/* Search — wider, icon on right */}
        <div style={{ position: 'relative', marginRight: 'auto' }}>
          <input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') setSearch(searchInput) }}
            placeholder="Search posts, subreddits, authors…"
            style={{
              width: 260, background: '#1a1a1a', border: '1px solid #262626',
              color: '#cfcfcf', fontSize: 12, borderRadius: 8,
              padding: '7px 32px 7px 12px', outline: 'none', boxSizing: 'border-box',
            }}
          />
          {searchInput ? (
            <button
              onClick={() => { setSearch(''); setSearchInput('') }}
              style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', color: '#5a5a5a', background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex' }}
            >
              <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          ) : (
            <span style={{ position: 'absolute', right: 9, top: '50%', transform: 'translateY(-50%)', color: '#5a5a5a', pointerEvents: 'none', display: 'flex' }}>
              <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </span>
          )}
        </div>

        <CustomSelect
          icon={<svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4M17 8v12m0 0l4-4m-4 4l-4-4" /></svg>}
          value={sortOrder}
          onChange={(val) => setSortOrder(val)}
          options={[{ value: 'newest', label: 'Newest' }, { value: 'oldest', label: 'Oldest' }]}
        />

        <CustomSelect
          icon={<svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>}
          value={timeFilter}
          onChange={(val) => setTimeFilter(val)}
          options={TIME_FILTERS}
        />

        <BackfillButton />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', alignItems: 'center', borderBottom: '1px solid #1f1f1f', marginBottom: 16 }}>
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusTab(tab.value)}
            style={{
              flex: 1, padding: '10px 14px', fontSize: 12.5,
              fontWeight: statusTab === tab.value ? 600 : 500,
              color: statusTab === tab.value ? '#fff' : '#7a7a7a',
              borderBottom: statusTab === tab.value ? `2px solid ${ACCENT}` : '2px solid transparent',
              marginBottom: -1, background: 'none', border: 'none',
              borderBottom: statusTab === tab.value ? `2px solid ${ACCENT}` : '2px solid transparent',
              cursor: 'pointer', textAlign: 'center', transition: 'color 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search tab */}
      {statusTab === 'search' ? (
        <div style={{ maxWidth: 520 }}>
          <p style={{ fontSize: 12, color: '#7a7a7a', marginBottom: 12, marginTop: 0 }}>
            Search Reddit in real time — new matching posts are saved to your feed.
          </p>
          <form onSubmit={handleLiveSearch} style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={liveQuery}
              onChange={(e) => { setLiveQuery(e.target.value); setLiveResult(null) }}
              placeholder="e.g. hiring react developer…"
              style={{
                flex: 1, background: '#1a1a1a', border: '1px solid #262626',
                color: '#cfcfcf', fontSize: 13, borderRadius: 8,
                padding: '8px 12px', outline: 'none',
              }}
            />
            <button
              type="submit"
              disabled={liveSearching || !liveQuery.trim()}
              style={{
                padding: '8px 16px', background: ACCENT, color: '#0a0a0a',
                border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600,
                cursor: 'pointer', opacity: (liveSearching || !liveQuery.trim()) ? 0.45 : 1,
              }}
            >
              {liveSearching ? 'Searching…' : 'Search Reddit'}
            </button>
          </form>
          {liveResult && (
            <p style={{ fontSize: 12, marginTop: 12, color: liveResult.error ? '#ff5d6c' : '#22d3a8' }}>
              {liveResult.error
                ? 'Search failed — is the backend running?'
                : liveResult.new_posts > 0
                  ? `+${liveResult.new_posts} new post${liveResult.new_posts !== 1 ? 's' : ''} added to feed`
                  : 'No new posts found'}
            </p>
          )}
        </div>
      ) : loading ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200, color: '#5a5a5a', fontSize: 14 }}>
          Loading posts...
        </div>
      ) : posts.length === 0 ? (
        <EmptyState tab={statusTab} hasSearch={!!search} />
      ) : (
        <>
          {/* Dense table */}
          <div style={{ borderRadius: 12, background: '#0e0e0e', overflow: 'hidden' }}>
            <ColumnHeaders />
            {posts.map((post) => (
              <DenseRow
                key={post.id}
                post={post}
                highlight={post.id === selectedPostId}
                isConfirming={deleteConfirm === post.id}
                onDM={() => {
                  sessionStorage.setItem('lastOpenedPostId', post.id)
                  setSelectedPostId(post.id)
                  navigate(`/review/${post.id}`)
                }}
                onDeleteRequest={() => setDeleteConfirm(post.id)}
                onDeleteConfirm={() => handleDelete(post.id)}
                onDeleteCancel={() => setDeleteConfirm(null)}
              />
            ))}
          </div>

          {/* Bottom bar */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <span style={{ fontSize: 12, color: '#5a5a5a' }}>
                {fromRow}–{toRow} of {total} posts
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {[
                  { color: '#22d3a8', label: 'Strong (8+)' },
                  { color: '#fbbf24', label: 'Good (6–7)' },
                  { color: '#7a7a7a', label: 'Weak (<6)' },
                ].map(({ color, label }) => (
                  <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
                    <span style={{ fontSize: 11, color: '#5a5a5a' }}>{label}</span>
                  </div>
                ))}
              </div>
            </div>
            {totalPages > 1 && (
              <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
            )}
          </div>
        </>
      )}
    </div>
  )
}

function ColumnHeaders() {
  const cols = ['lead', 'post', 'subreddit', 'engagement', 'posted', '']
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '56px 1fr 140px 120px 80px 100px',
      gap: 16, padding: '10px 16px',
      borderBottom: '1px solid #1f1f1f',
      background: '#0a0a0a',
    }}>
      {cols.map((c, i) => (
        <div key={i} style={{ fontSize: 10, color: '#5a5a5a', textTransform: 'uppercase', letterSpacing: 0.6, fontWeight: 600 }}>
          {c}
        </div>
      ))}
    </div>
  )
}

function DenseRow({ post, highlight, isConfirming, onDM, onDeleteRequest, onDeleteConfirm, onDeleteCancel }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '56px 1fr 140px 120px 80px 100px',
      gap: 16, padding: '14px 16px',
      borderBottom: '1px solid #161616',
      alignItems: 'center',
      position: 'relative',
      background: highlight ? `linear-gradient(90deg, ${ACCENT}0a, transparent 30%)` : 'transparent',
    }}>
      {highlight && (
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 2, background: ACCENT }} />
      )}

      <ScoreRing score={post.score} size={36} />

      {/* Post column */}
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontSize: 13.5, fontWeight: 500, color: '#f5f5f5',
          lineHeight: 1.3, marginBottom: 4,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {post.title}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <AuthorIcon />
          <span style={{ fontSize: 11, color: '#7a7a7a' }}>u/{post.author}</span>
          {post.score_reason && (
            <>
              <span style={{ fontSize: 10, color: '#3a3a3a' }}>·</span>
              <span style={{
                fontSize: 11, color: '#5a5a5a',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 220,
              }}>
                {post.score_reason}
              </span>
            </>
          )}
        </div>
      </div>

      <SubBadge sub={post.subreddit} />

      <Engagement upvotes={post.reddit_upvotes} comments={post.num_comments} />

      <PostedCell postedAt={post.posted_at} />

      {/* Actions */}
      <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
        {isConfirming ? (
          <>
            <button onClick={onDeleteConfirm} style={{
              padding: '4px 8px', background: 'rgba(255,93,108,0.12)',
              color: '#ff5d6c', border: '1px solid rgba(255,93,108,0.25)',
              borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            }}>
              Delete
            </button>
            <button onClick={onDeleteCancel} style={{
              padding: '4px 8px', background: '#1a1a1a',
              color: '#9a9a9a', border: '1px solid #262626',
              borderRadius: 6, fontSize: 11, cursor: 'pointer',
            }}>
              Cancel
            </button>
          </>
        ) : (
          <>
            <button onClick={onDM} style={{
              padding: '5px 10px', background: ACCENT,
              color: '#0a0a0a', border: 'none',
              borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap',
            }}>
              Draft reply
            </button>
            <button onClick={onDeleteRequest} style={{
              padding: '5px 8px', background: '#1a1a1a',
              color: '#7a7a7a', border: '1px solid #262626',
              borderRadius: 6, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6l-1 14H6L5 6" />
                <path d="M10 11v6M14 11v6" />
                <path d="M9 6V4h6v2" />
              </svg>
            </button>
          </>
        )}
      </div>
    </div>
  )
}

function ScoreRing({ score, size = 36 }) {
  const radius = (size - 5) / 2
  const circumference = 2 * Math.PI * radius
  const pct = Math.max(0, Math.min(10, score ?? 0)) / 10
  const color = score >= 8 ? '#22d3a8' : score >= 6 ? '#fbbf24' : '#7a7a7a'

  return (
    <div style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#1f1f1f" strokeWidth={2.5} />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke={color} strokeWidth={2.5}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - pct)}
          strokeLinecap="round"
        />
      </svg>
      <span style={{
        position: 'absolute', inset: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: Math.round(size * 0.3), fontWeight: 600, color,
        fontFamily: 'ui-monospace, SF Mono, Menlo, monospace',
      }}>
        {score ?? '—'}
      </span>
    </div>
  )
}

function SubBadge({ sub }) {
  const color = subColor(sub)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
      <span style={{ fontSize: 11.5, color: '#cfcfcf', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        r/{sub}
      </span>
    </div>
  )
}

function Engagement({ upvotes, comments }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, fontFamily: 'ui-monospace, SF Mono, Menlo, monospace' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#e5e5e5' }}>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M12 4l-8 8h5v8h6v-8h5z"/></svg>
        {upvotes ?? 0}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#7a7a7a' }}>
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        {comments ?? 0}
      </div>
    </div>
  )
}

function PostedCell({ postedAt }) {
  const mins = (Date.now() - new Date(postedAt).getTime()) / 60_000
  const fresh = mins < 30
  const aging = mins < 90
  const color = fresh ? '#22d3a8' : aging ? '#fbbf24' : '#ff5d6c'
  const bg = fresh ? 'rgba(34,211,168,0.1)' : aging ? 'rgba(251,191,36,0.1)' : 'rgba(255,93,108,0.1)'
  return (
    <span style={{ fontSize: 11, color, background: bg, padding: '2px 7px', borderRadius: 4, whiteSpace: 'nowrap', fontFamily: 'ui-monospace, SF Mono, Menlo, monospace' }}>
      {timeAgo(postedAt)}
    </span>
  )
}

function AuthorIcon() {
  return (
    <div style={{ width: 16, height: 16, borderRadius: '50%', background: '#262626', border: '1px solid #3a3a3a', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
      <svg width="9" height="9" viewBox="0 0 24 24" fill="#7a7a7a">
        <path d="M12 12c2.7 0 4.8-2.1 4.8-4.8S14.7 2.4 12 2.4 7.2 4.5 7.2 7.2 9.3 12 12 12zm0 2.4c-3.2 0-9.6 1.6-9.6 4.8v2.4h19.2v-2.4c0-3.2-6.4-4.8-9.6-4.8z"/>
      </svg>
    </div>
  )
}

function EmptyState({ tab, hasSearch }) {
  if (hasSearch) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 192, color: '#5a5a5a', fontSize: 14 }}>
      No posts match your search
    </div>
  )
  const messages = {
    all: 'No posts in this window',
    drafts: 'No stale drafts — all posts reviewed within 24 hours',
    approved: 'No approved posts yet',
    disapproved: 'No disapproved posts yet',
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 192, gap: 8 }}>
      <p style={{ color: '#5a5a5a', fontSize: 14, margin: 0 }}>{messages[tab]}</p>
      {tab === 'all' && (
        <p style={{ color: '#3a3a3a', fontSize: 12, margin: 0 }}>Watcher runs every 2 minutes — posts appear here in real time</p>
      )}
    </div>
  )
}


function getPageWindow(current, total) {
  const size = Math.min(5, total)
  let start = Math.max(0, current - Math.floor(size / 2))
  if (start + size > total) start = total - size
  return Array.from({ length: size }, (_, i) => start + i)
}

function Pagination({ page, totalPages, onPageChange }) {
  const pages = getPageWindow(page, totalPages)
  const btn = (label, onClick, disabled, active) => (
    <button
      key={label}
      onClick={onClick}
      disabled={disabled}
      style={{
        width: 30, height: 30, display: 'flex', alignItems: 'center', justifyContent: 'center',
        borderRadius: 6, fontSize: 12, fontWeight: active ? 600 : 400, cursor: disabled ? 'not-allowed' : 'pointer',
        background: active ? 'rgba(255,255,255,0.12)' : '#1a1a1a',
        color: active ? '#fff' : disabled ? '#3a3a3a' : '#9a9a9a',
        border: active ? '1px solid rgba(255,255,255,0.18)' : '1px solid #262626',
        transition: 'all 0.1s',
        fontFamily: 'ui-monospace, SF Mono, Menlo, monospace',
      }}
    >
      {label}
    </button>
  )

  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {btn('←', () => onPageChange((p) => Math.max(0, p - 1)), page === 0, false)}
      {pages.map((p) => btn(p + 1, () => onPageChange(p), false, p === page))}
      {btn('→', () => onPageChange((p) => Math.min(totalPages - 1, p + 1)), page >= totalPages - 1, false)}
    </div>
  )
}

function BackfillButton() {
  const [state, setState] = useState('idle')

  async function handleClick() {
    if (state !== 'idle') return
    setState('loading')
    try { await fetch('http://localhost:8000/watcher/backfill') } catch {}
    setState('done')
    setTimeout(() => setState('idle'), 3000)
  }

  const icon = state === 'loading'
    ? <svg className="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
    : state === 'done'
    ? <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
    : <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>

  return (
    <div style={{ position: 'relative' }} className="group">
      <button
        onClick={handleClick}
        disabled={state !== 'idle'}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          padding: '7px 12px', background: '#1a1a1a', border: '1px solid #262626',
          borderRadius: 8, color: '#9a9a9a', fontSize: 12, cursor: 'pointer',
          opacity: state !== 'idle' ? 0.6 : 1, transition: 'all 0.15s',
        }}
      >
        {icon}
        <span>{state === 'done' ? 'Done' : 'Backfill'}</span>
      </button>
      <div className="absolute right-0 top-full mt-2 w-60 opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-10"
        style={{
          background: '#141414', border: '1px solid #262626',
          borderRadius: 8, padding: '8px 12px',
          fontSize: 11.5, color: '#9a9a9a', lineHeight: 1.5,
          boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        }}>
        Pulls all Reddit posts from the last 24h across your search terms — useful after a server restart to catch up on missed posts.
      </div>
    </div>
  )
}
