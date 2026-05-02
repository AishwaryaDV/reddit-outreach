-- Run this in Supabase SQL Editor (project: reddit-outreach)

create table posts (
  id              uuid default gen_random_uuid() primary key,
  reddit_post_id  text unique not null,
  subreddit       text,
  title           text,
  body            text,
  author          text,
  posted_at       timestamptz,
  detected_at     timestamptz default now(),
  score           integer,
  score_reason    text,
  status          text default 'new'
  -- status values: new | drafted | approved | sent | cancelled
);

create table messages (
  id            uuid default gen_random_uuid() primary key,
  post_id       uuid references posts(id) on delete cascade,
  draft         text,
  final_message text,
  send_after    timestamptz,
  sent_at       timestamptz,
  created_at    timestamptz default now(),
  status        text default 'pending',
  -- status values: pending | approved | sent | cancelled
  reply_received boolean default false,
  replied_at    timestamptz,
  outcome       text
  -- outcome values: ignored | responded | hired | ongoing
);

-- Index for fast deduplication lookups
create index posts_reddit_post_id_idx on posts(reddit_post_id);

-- Index for queue queries (pending messages ordered by send_after)
create index messages_status_send_after_idx on messages(status, send_after);
