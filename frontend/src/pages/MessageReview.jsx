import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import ScoreBadge from '../components/ScoreBadge'
import UrgencyDot from '../components/UrgencyDot'

function Countdown({ sendAfter, onExpire }) {
  const [secondsLeft, setSecondsLeft] = useState(null)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!sendAfter) return

    const tick = () => {
      const diff = Math.max(0, Math.floor((new Date(sendAfter) - Date.now()) / 1000))
      setSecondsLeft(diff)
      if (diff === 0) {
        clearInterval(intervalRef.current)
        onExpire?.()
      }
    }

    tick()
    intervalRef.current = setInterval(tick, 1000)
    return () => clearInterval(intervalRef.current)
  }, [sendAfter])

  if (secondsLeft === null) return null

  const mins = Math.floor(secondsLeft / 60)
  const secs = secondsLeft % 60
  const urgent = secondsLeft < 60
  const expired = secondsLeft === 0

  if (expired) return (
    <span className="text-xs text-red-400 font-medium">Auto-sent</span>
  )

  return (
    <span className={`text-xs font-mono font-medium ${urgent ? 'text-red-400' : 'text-yellow-400'}`}>
      {mins}:{String(secs).padStart(2, '0')} until auto-send
    </span>
  )
}

export default function MessageReview() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [post, setPost] = useState(null)
  const [message, setMessage] = useState(null)
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState(null) // 'approving' | 'cancelling'

  useEffect(() => {
    async function load() {
      const { data: postData } = await supabase
        .from('posts')
        .select('*')
        .eq('id', id)
        .single()

      if (!postData) { navigate('/'); return }
      setPost(postData)

      const { data: msgData } = await supabase
        .from('messages')
        .select('*')
        .eq('post_id', id)
        .in('status', ['pending', 'approved'])
        .order('created_at', { ascending: false })
        .limit(1)
        .single()

      if (msgData) {
        setMessage(msgData)
        setDraft(msgData.draft ?? '')
      }

      setLoading(false)
    }
    load()
  }, [id])

  async function handleApprove() {
    if (!message) return
    setAction('approving')
    await supabase
      .from('messages')
      .update({ status: 'approved', final_message: draft })
      .eq('id', message.id)
    await supabase
      .from('posts')
      .update({ status: 'approved' })
      .eq('id', id)
    navigate('/')
  }

  async function handleCancel() {
    setAction('cancelling')
    if (message) {
      await supabase.from('messages').update({ status: 'cancelled' }).eq('id', message.id)
    }
    await supabase.from('posts').update({ status: 'cancelled' }).eq('id', id)
    navigate('/')
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-slate-500 text-sm">Loading...</div>
  )

  if (!post) return null

  const postUrl = `https://reddit.com/comments/${post.reddit_post_id}`

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <button
          onClick={() => navigate('/')}
          className="text-slate-500 hover:text-white text-sm transition-colors"
        >
          ← Back
        </button>
        <span className="text-slate-700">/</span>
        <span className="text-slate-400 text-sm">r/{post.subreddit}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left — post content */}
        <div className="bg-white/3 border border-white/8 rounded-xl p-5 flex flex-col gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-slate-500">r/{post.subreddit}</span>
            <span className="text-slate-700">·</span>
            <UrgencyDot postedAt={post.posted_at} />
            <ScoreBadge score={post.score} />
          </div>

          <h2 className="text-white font-medium leading-snug">{post.title}</h2>

          {post.score_reason && (
            <p className="text-xs text-slate-500 bg-white/3 rounded-lg px-3 py-2 border border-white/5">
              {post.score_reason}
            </p>
          )}

          <div className="flex-1 text-sm text-slate-400 leading-relaxed whitespace-pre-wrap break-words max-h-96 overflow-y-auto scrollbar-thin">
            {post.body || <span className="text-slate-600 italic">No post body</span>}
          </div>

          <a
            href={postUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-slate-500 hover:text-white transition-colors"
          >
            View on Reddit →
          </a>
        </div>

        {/* Right — draft message */}
        <div className="bg-white/3 border border-white/8 rounded-xl p-5 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Draft message</h3>
            {message?.send_after && (
              <Countdown sendAfter={message.send_after} />
            )}
          </div>

          {message ? (
            <>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={8}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-sm text-slate-200 leading-relaxed resize-none outline-none focus:border-white/20 transition-colors"
                placeholder="Draft message..."
              />

              <p className="text-xs text-slate-600">
                Editing will update the final message before it sends.
                Portfolio link must stay in the last line.
              </p>

              <div className="flex gap-3 mt-auto">
                <button
                  onClick={handleApprove}
                  disabled={!!action}
                  className="flex-1 bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-white text-sm font-medium rounded-lg py-2.5 transition-colors"
                >
                  {action === 'approving' ? 'Approving...' : 'Approve & Queue'}
                </button>
                <button
                  onClick={handleCancel}
                  disabled={!!action}
                  className="px-4 bg-white/5 hover:bg-white/10 disabled:opacity-50 text-slate-400 hover:text-white text-sm rounded-lg py-2.5 transition-colors border border-white/8"
                >
                  {action === 'cancelling' ? '...' : 'Cancel'}
                </button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center py-8">
              <p className="text-slate-500 text-sm">No draft yet</p>
              <p className="text-slate-600 text-xs max-w-xs">
                Add your Anthropic API key to enable Claude message drafting.
                Posts will be scored and drafted automatically.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
