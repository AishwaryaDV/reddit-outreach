import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAILS

logger = logging.getLogger(__name__)


def send_notification(post: dict, score: int, reason: str, draft: str):
    if not GMAIL_USER or not GMAIL_APP_PASSWORD or not NOTIFY_EMAILS:
        logger.debug("Email notifications not configured — skipping")
        return

    subreddit = post.get("subreddit", "unknown")
    title = post.get("title", "")
    author = post.get("author", "")
    reddit_post_id = post.get("reddit_post_id", "")
    post_url = f"https://reddit.com/comments/{reddit_post_id}"

    urgency = "🔴 HIGH" if score >= 8 else "🟡 MEDIUM" if score >= 5 else "🟢 LOW"

    body = f"""New Reddit hiring post detected — score {score}/10

{urgency} — {reason}

Post: {title}
Subreddit: r/{subreddit}
Author: u/{author}
Link: {post_url}

---
Drafted message:

{draft or "(No draft — add Anthropic API key to enable)"}

---
Open your dashboard to review, edit, or cancel before it auto-sends.
"""

    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(NOTIFY_EMAILS)
    msg["Subject"] = f"[{score}/10] New hiring post: {title[:60]}"
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, NOTIFY_EMAILS, msg.as_string())
        logger.info("Notification sent for post %s", reddit_post_id)
    except smtplib.SMTPException as e:
        logger.error("Failed to send notification: %s", e)
