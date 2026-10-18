"""Data-access layer, backed by self-hosted Postgres via SQLAlchemy (async).

Replaces the former Supabase (PostgREST) client. The public function names are
unchanged so the watcher/sender/API barely change — only that these are now
awaited. get_setting/get_search_terms still swallow DB errors and return a
safe default so the watcher keeps its config-fallback behaviour.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import POST_RETENTION_DAYS
from app.db import get_session_factory
from app.models import AppSetting, Message, Post, SearchTerm


async def post_exists(reddit_post_id: str) -> bool:
    async with get_session_factory()() as session:
        result = await session.execute(
            select(Post.id).where(Post.reddit_post_id == reddit_post_id).limit(1)
        )
        return result.first() is not None


async def update_post_engagement(reddit_post_id: str, upvotes: int, comments: int) -> None:
    async with get_session_factory()() as session:
        await session.execute(
            update(Post)
            .where(Post.reddit_post_id == reddit_post_id)
            .values(reddit_upvotes=upvotes, num_comments=comments)
        )
        await session.commit()


async def save_post(post_data: dict) -> str:
    async with get_session_factory()() as session:
        post = Post(**post_data)
        session.add(post)
        await session.flush()  # RETURNING populates the server-generated id
        post_id = str(post.id)
        await session.commit()
        return post_id


async def save_message(message_data: dict) -> None:
    async with get_session_factory()() as session:
        session.add(Message(**message_data))
        await session.commit()


async def purge_old_posts() -> int:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=POST_RETENTION_DAYS)
    async with get_session_factory()() as session:
        result = await session.execute(
            delete(Post).where(
                Post.status.in_(["new", "drafted"]),
                Post.detected_at < cutoff,
            )
        )
        await session.commit()
        return result.rowcount or 0


async def get_recent_drafts(limit: int = 5) -> list[str]:
    async with get_session_factory()() as session:
        result = await session.execute(
            select(Message.draft)
            .where(
                Message.status.in_(["sent", "pending", "approved"]),
                Message.draft.isnot(None),
            )
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return [row[0] for row in result.all() if row[0]]


async def get_setting(key: str, default: str = "") -> str:
    try:
        async with get_session_factory()() as session:
            result = await session.execute(
                select(AppSetting.value).where(AppSetting.key == key)
            )
            row = result.first()
            return row[0] if row and row[0] is not None else default
    except Exception:
        return default


async def set_setting(key: str, value: str) -> None:
    async with get_session_factory()() as session:
        stmt = pg_insert(AppSetting).values(key=key, value=value, updated_at=func.now())
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={"value": value, "updated_at": func.now()},
        )
        await session.execute(stmt)
        await session.commit()


async def get_search_terms() -> list[str] | None:
    """Enabled terms from DB. Returns [] when the user disabled all terms
    (watcher should skip the run), None on DB error (watcher falls back to config)."""
    try:
        async with get_session_factory()() as session:
            result = await session.execute(
                select(SearchTerm.term).where(SearchTerm.active.is_(True))
            )
            return [row[0] for row in result.all() if row[0]]
    except Exception:
        return None
