from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from app.config import SUPABASE_URL, SUPABASE_KEY, POST_RETENTION_DAYS

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def post_exists(reddit_post_id: str) -> bool:
    result = get_client().table("posts").select("id").eq("reddit_post_id", reddit_post_id).execute()
    return len(result.data) > 0


def save_post(post_data: dict) -> str:
    result = get_client().table("posts").insert(post_data).execute()
    return result.data[0]["id"]


def save_message(message_data: dict):
    get_client().table("messages").insert(message_data).execute()


def purge_old_posts() -> int:
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=POST_RETENTION_DAYS)).isoformat()
    result = (
        get_client()
        .table("posts")
        .delete()
        .in_("status", ["new", "drafted"])
        .lt("detected_at", cutoff)
        .execute()
    )
    return len(result.data)


def get_recent_drafts(limit: int = 5) -> list[str]:
    result = (
        get_client()
        .table("messages")
        .select("draft")
        .in_("status", ["sent", "pending", "approved"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return [row["draft"] for row in result.data if row.get("draft")]
