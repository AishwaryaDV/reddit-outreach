import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { timeAgo } from '../lib/time'

const ACCENT = '#ff4500'

const SUB_COLORS = {
  saas: '#7c5cff', reactjs: '#22d3a8', webdev: '#ff8a3d',
  startups: '#f5cc4b', entrepreneur: '#ff5d8f', growmybusiness: '#5cc2ff',
  marketing: '#c084fc', sideproject: '#34d399', entrepreneurridealone: '#fbbf24',
}
function subColor(sub) {
  const key = (sub || '').toLowerCase()
  if (SUB_COLORS[key]) return SUB_COLORS[key]
  let h = 0
  for (let i = 0; i < key.length; i++) h = ((h << 5) - h + key.charCodeAt(i)) | 0
  return Object.values(SUB_COLORS)[Math.abs(h) % Object.values(SUB_COLORS).length]
}

function scoreLabel(score) {
  if (score >= 8.5) return 'strong match'
  if (score >= 7) return 'good match'
  if (score >= 5) return 'possible match'
  return 'weak match'
}

function scoreColor(score) {
  if (score >= 8.5) return '#22d3a8'
  if (score >= 7) return '#fbbf24'
  return '#7a7a7a'
}

export default function MessageReview() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [post, setPost] = useState(null)
  const [message, setMessage] = useState(null)
  const [draft, setDraft] = useState('')
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState(null)

  // Fetch sidebar post list once
  useEffect(() => {
    supabase
      .from('posts')
      .select('id, title, subreddit, author, posted_at, reddit_upvotes, num_comments, score, status')
      .order('score', { ascending: false })
      .limit(200)
      .then(({ data }) => setPosts(data ?? []))
  }, [])

  // Fetch selected post + message when id changes
  useEffect(() => {
    setLoading(true)
    setPost(null)
    setMessage(null)
    setDraft('')
    setAction(null)

    async function load() {
      const { data: postData } = await supabase
        .from('posts').select('*').eq('id', id).single()
      if (!postData) { navigate('/'); return }
      setPost(postData)

      const { data: msgData } = await supabase
        .from('messages').select('*').eq('post_id', id)
        .in('status', ['pending', 'approved'])
        .order('created_at', { ascending: false })
        .limit(1).single()
      if (msgData) { setMessage(msgData); setDraft(msgData.draft ?? '') }
      setLoading(false)
    }
    load()
  }, [id])

  function goNext() {
    const idx = posts.findIndex((p) => p.id === id)
    const next = posts[idx + 1] || posts[idx - 1] || null
    if (next) navigate(`/review/${next.id}`)
    else navigate('/')
  }

  async function handleApprove() {
    if (!message || action) return
    setAction('approving')
    await supabase.from('messages').update({ status: 'approved', final_message: draft }).eq('id', message.id)
    await supabase.from('posts').update({ status: 'approved' }).eq('id', id)
    setPosts((prev) => prev.map((p) => p.id === id ? { ...p, status: 'approved' } : p))
    goNext()
  }

  async function handleDisapprove() {
    if (action) return
    setAction('disapproving')
    if (message) await supabase.from('messages').update({ status: 'cancelled' }).eq('id', message.id)
    await supabase.from('posts').update({ status: 'cancelled' }).eq('id', id)
    setPosts((prev) => prev.map((p) => p.id === id ? { ...p, status: 'cancelled' } : p))
    goNext()
  }

  const postUrl = post ? `https://reddit.com/comments/${post.reddit_post_id}` : '#'

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: 10, height: 'calc(100vh - 113px)' }}>

      {/* Left sidebar — post list */}
      <div style={{ border: '1px solid #2e2e2e', borderRadius: 12, background: '#0e0e0e', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '10px 14px', borderBottom: '1px solid #1f1f1f', display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <span style={{ fontSize: 12, color: '#9a9a9a' }}>Freshest first</span>
          <span style={{ fontSize: 10, color: '#3a3a3a' }}>·</span>
          <span style={{ fontSize: 12, color: '#5a5a5a' }}>opened on top</span>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 11.5, color: '#5a5a5a' }}>{posts.length} posts</span>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {[
            ...posts.filter((p) => p.id === id),
            ...posts.filter((p) => p.id !== id).sort((a, b) => new Date(b.posted_at) - new Date(a.posted_at)),
          ].map((p) => (
            <SidebarItem
              key={p.id}
              post={p}
              selected={p.id === id}
              onClick={() => navigate(`/review/${p.id}`)}
            />
          ))}
        </div>
      </div>

      {/* Right — post detail */}
      {loading ? (
        <div style={{ border: '1px solid #2e2e2e', borderRadius: 12, background: '#0e0e0e', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#5a5a5a', fontSize: 14 }}>
          Loading...
        </div>
      ) : post ? (
        <div style={{ border: '1px solid #2e2e2e', borderRadius: 12, background: '#0e0e0e', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {/* Header strip */}
          <div style={{ padding: '12px 18px', borderBottom: '1px solid #1f1f1f', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
            <SubBadge sub={post.subreddit} />
            {!post.subreddit?.toLowerCase().startsWith('u_') && (
              <>
                <span style={{ fontSize: 10, color: '#3a3a3a' }}>·</span>
                <span style={{ fontSize: 11.5, color: '#9a9a9a' }}>u/{post.author}</span>
              </>
            )}
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: '#7a7a7a', fontFamily: 'ui-monospace, monospace' }}>
              posted {timeAgo(post.posted_at)}
            </span>
            <a
              href={postUrl}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 11, color: '#9a9a9a', padding: '4px 9px', background: '#1a1a1a', border: '1px solid #262626', borderRadius: 6, textDecoration: 'none' }}
            >
              open ↗
            </a>
          </div>

          {/* Scrollable content */}
          <div style={{ flex: 1, overflowY: 'auto', padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Score row */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ScoreRing score={post.score} size={40} />
              <div>
                <div style={{ fontSize: 10.5, color: '#7a7a7a', textTransform: 'uppercase', letterSpacing: 0.6, marginBottom: 2 }}>
                  Lead score · 0–10
                </div>
                <div style={{ fontSize: 12.5, color: scoreColor(post.score), fontWeight: 500 }}>
                  {scoreLabel(post.score)}
                </div>
              </div>
              <div style={{ flex: 1 }} />
              {(post.reddit_upvotes > 0 || post.num_comments > 0) && (
                <div style={{ fontSize: 11.5, color: '#7a7a7a', display: 'flex', gap: 10, fontFamily: 'ui-monospace, monospace' }}>
                  {post.reddit_upvotes > 0 && <span>↑ {post.reddit_upvotes}</span>}
                  {post.num_comments > 0 && <span>💬 {post.num_comments}</span>}
                </div>
              )}
              <StatusPill status={post.status} />
            </div>

            {/* Title */}
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 600, letterSpacing: -0.3, lineHeight: 1.3, color: '#fafafa' }}>
              {post.title}
            </h2>

            {/* Score reason */}
            {post.score_reason && (
              <p style={{ margin: 0, fontSize: 12, color: '#7a7a7a', background: '#111', border: '1px solid #1f1f1f', borderRadius: 8, padding: '8px 12px' }}>
                {post.score_reason}
              </p>
            )}

            {/* Body */}
            <div style={{ fontSize: 13, lineHeight: 1.65, color: '#b5b5b5', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {post.body || <span style={{ color: '#5a5a5a', fontStyle: 'italic' }}>No post body</span>}
            </div>
          </div>

          {/* Draft panel — pinned to bottom */}
          <div style={{ flexShrink: 0, borderTop: '1px solid #1f1f1f', padding: '0' }}>
            <DraftPanel
              message={message}
              draft={draft}
              setDraft={setDraft}
              action={action}
              onApprove={handleApprove}
              onDisapprove={handleDisapprove}
            />
          </div>
        </div>
      ) : null}
    </div>
  )
}

function SidebarItem({ post, selected, onClick }) {
  const ref = useRef(null)

  useEffect(() => {
    if (selected && ref.current) {
      ref.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [selected])

  const mins = (Date.now() - new Date(post.posted_at).getTime()) / 60_000
  const fresh = mins < 30
  const aging = mins < 90
  const timeColor = fresh ? '#22d3a8' : aging ? '#fbbf24' : '#ff5d6c'
  const timeBg = fresh ? 'rgba(34,211,168,0.1)' : aging ? 'rgba(251,191,36,0.1)' : 'rgba(255,93,108,0.1)'

  return (
    <div
      ref={ref}
      onClick={onClick}
      style={{
        padding: '10px 12px 10px 14px',
        borderBottom: '1px solid #161616',
        background: selected ? `linear-gradient(90deg, ${ACCENT}0d, transparent 60%)` : 'transparent',
        display: 'grid',
        gridTemplateColumns: '30px 1fr',
        gap: 8,
        cursor: 'pointer',
        transition: 'background 0.1s',
        alignItems: 'start',
        position: 'relative',
      }}
    >
      {selected && (
        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: 2, background: ACCENT }} />
      )}
      <div style={{ paddingTop: 2 }}>
        <ScoreRing score={post.score} size={28} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontSize: 12.5, fontWeight: 500, color: selected ? '#fff' : '#e5e5e5',
          lineHeight: 1.35, marginBottom: 5,
          display: '-webkit-box', WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>
          {post.title}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'nowrap', overflow: 'hidden' }}>
          <SubBadge sub={post.subreddit} small />
          <span style={{ fontSize: 10, color: '#3a3a3a', flexShrink: 0 }}>·</span>
          <span style={{ fontSize: 10.5, color: '#7a7a7a', flexShrink: 0 }}>↑{post.reddit_upvotes ?? 0}</span>
          <span style={{ fontSize: 10, color: '#3a3a3a', flexShrink: 0 }}>·</span>
          <span style={{ fontSize: 10.5, color: timeColor, background: timeBg, padding: '1px 5px', borderRadius: 3, flexShrink: 0 }}>
            {timeAgo(post.posted_at)}
          </span>
          <div style={{ flex: 1 }} />
          <StatusPill status={post.status} />
        </div>
      </div>
    </div>
  )
}

function DraftPanel({ message, draft, setDraft, action, onApprove, onDisapprove }) {
  return (
    <div style={{ background: '#0a0a0a' }}>
      {/* Header */}
      <div style={{ padding: '8px 14px', borderBottom: '1px solid #1f1f1f', background: '#111', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: ACCENT, boxShadow: `0 0 0 3px ${ACCENT}26`, flexShrink: 0 }} />
        <span style={{ fontSize: 11.5, color: '#e5e5e5', fontWeight: 500 }}>AI draft reply</span>
        <span style={{ fontSize: 11.5, color: '#7a7a7a' }}>· tone: helpful, casual</span>
        <div style={{ flex: 1 }} />
        {message?.send_after && <Countdown sendAfter={message.send_after} />}
      </div>

      {/* Draft body */}
      {message ? (
        <>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={5}
            style={{
              width: '100%', background: 'transparent', border: 'none',
              borderBottom: '1px solid #1f1f1f', color: '#cfcfcf',
              fontSize: 12.5, lineHeight: 1.6, padding: '12px 14px',
              resize: 'none', outline: 'none', boxSizing: 'border-box',
              fontFamily: 'inherit',
            }}
          />
          {/* Footer */}
          <div style={{ padding: '10px 14px', display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              onClick={onApprove}
              disabled={!!action}
              style={{
                padding: '6px 14px', background: ACCENT, color: '#0a0a0a',
                border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 600,
                cursor: action ? 'not-allowed' : 'pointer', opacity: action ? 0.5 : 1,
              }}
            >
              {action === 'approving' ? 'Approving…' : 'Approve & Queue →'}
            </button>
            <button
              onClick={onDisapprove}
              disabled={!!action}
              style={{
                padding: '6px 12px', background: '#1a1a1a', color: '#9a9a9a',
                border: '1px solid #262626', borderRadius: 6, fontSize: 12,
                cursor: action ? 'not-allowed' : 'pointer', opacity: action ? 0.5 : 1,
              }}
            >
              {action === 'disapproving' ? '…' : 'Disapprove'}
            </button>
            <p style={{ margin: 0, fontSize: 11, color: '#5a5a5a' }}>
              Portfolio link must stay in the last line.
            </p>
          </div>
        </>
      ) : (
        <div style={{ padding: '20px 14px', textAlign: 'center' }}>
          <p style={{ margin: 0, fontSize: 13, color: '#5a5a5a' }}>No draft generated for this post</p>
          <p style={{ margin: '6px 0 0', fontSize: 11.5, color: '#3a3a3a' }}>Enable the real scorer to generate drafts</p>
        </div>
      )}
    </div>
  )
}

function Countdown({ sendAfter }) {
  const [secondsLeft, setSecondsLeft] = useState(null)
  const ref = useRef(null)

  useEffect(() => {
    const tick = () => {
      const diff = Math.max(0, Math.floor((new Date(sendAfter) - Date.now()) / 1000))
      setSecondsLeft(diff)
    }
    tick()
    ref.current = setInterval(tick, 1000)
    return () => clearInterval(ref.current)
  }, [sendAfter])

  if (secondsLeft === null) return null
  if (secondsLeft === 0) return <span style={{ fontSize: 11, color: '#ff5d6c', fontFamily: 'ui-monospace, monospace' }}>Auto-sent</span>

  const mins = Math.floor(secondsLeft / 60)
  const secs = secondsLeft % 60
  const urgent = secondsLeft < 60
  return (
    <span style={{ fontSize: 11, color: urgent ? '#ff5d6c' : '#fbbf24', fontFamily: 'ui-monospace, monospace' }}>
      {mins}:{String(secs).padStart(2, '0')} until auto-send
    </span>
  )
}

function ScoreRing({ score, size = 36 }) {
  const radius = (size - 5) / 2
  const circumference = 2 * Math.PI * radius
  const pct = Math.max(0, Math.min(10, score ?? 0)) / 10
  const color = scoreColor(score)

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

function SubBadge({ sub, small }) {
  const color = subColor(sub)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: small ? 4 : 6 }}>
      <div style={{ width: small ? 5 : 6, height: small ? 5 : 6, borderRadius: '50%', background: color, flexShrink: 0 }} />
      <span style={{ fontSize: small ? 10.5 : 11.5, color: '#cfcfcf', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        r/{sub}
      </span>
    </div>
  )
}

function StatusPill({ status }) {
  const map = {
    new:       { bg: 'rgba(90,90,90,0.15)',  color: '#9a9a9a' },
    drafted:   { bg: 'rgba(92,194,255,0.15)', color: '#5cc2ff' },
    approved:  { bg: 'rgba(34,211,168,0.15)', color: '#22d3a8' },
    sent:      { bg: 'rgba(34,211,168,0.15)', color: '#22d3a8' },
    cancelled: { bg: 'rgba(255,93,108,0.15)', color: '#ff5d6c' },
  }
  const s = map[status] ?? map.new
  return (
    <span style={{
      fontSize: 10, padding: '2px 7px', borderRadius: 999,
      background: s.bg, color: s.color, fontWeight: 500, whiteSpace: 'nowrap',
    }}>
      {status}
    </span>
  )
}
