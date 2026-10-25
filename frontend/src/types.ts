// Shared data shapes for the backend JSON API.

export interface Post {
  id: string
  reddit_post_id?: string
  subreddit?: string
  title?: string
  body?: string
  author?: string
  posted_at?: string | null
  detected_at?: string
  status: string
  score?: number | null
  score_reason?: string | null
  num_comments: number
  reddit_upvotes: number
  contact_links?: { kind: string; value: string; label: string }[]
}

export interface Message {
  id: string
  post_id: string
  draft?: string
  final_message?: string | null
  status: string
  send_after?: string | null
  sent_at?: string | null
  created_at?: string
  outcome?: string | null
  replied_at?: string | null
}

// The message-review / queue / tracker endpoints return a message joined with
// its post (sometimes nested, sometimes with a few post fields flattened).
export interface MessageWithPost extends Message {
  post?: Post
  title?: string
  subreddit?: string
  author?: string
  body?: string
  score?: number | null
}

export interface PostsPage {
  posts: Post[]
  total: number
}

export interface SearchTerm {
  id: string
  term: string
  active: boolean
}

export interface Config {
  portfolio_url: string
  daily_dm_cap: number
  approval_window_min: number
  approval_window_max: number
  auto_send_enabled: boolean
  scoring_enabled: boolean
  watcher_interval_minutes: number
  post_retention_days: number
  daily_llm_cap: number
  gmail_configured: boolean
}

export interface MetricsData {
  calls: {
    total: number
    today: number
    parse_ok_pct: number | null
    fell_back: number
    by_backend: Record<string, number>
  }
  cost: { total_usd: number; today_usd: number }
  latency_ms: { p50: number | null; p95: number | null }
  per_day: { day: string; calls: number; cost: number }[]
  funnel: { posts: Record<string, number>; messages: Record<string, number> }
  approve_rate_by_bucket: { bucket: string; total: number; approved: number }[]
  rejects_by_score: Record<string, number>
  quota: { daily_cap: number; today: number; paused: boolean }
}
