"""Extract actionable contact / apply links from a post body.

Post-shadow-ban, DMing is the risky channel — the best hires come through the
Google Form / email / Discord the poster drops in the body. So we surface those
separately in the dashboard and the user applies there first, manually.
"""
import re

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_URL_RE = re.compile(r"https?://[^\s)\]>\"']+")

# Media / noise domains that are never a contact channel.
_NOISE = ("imgur.", "i.redd.it", "redd.it", "reddit.com", "youtu", "giphy.",
          "tenor.", "gfycat.", "streamable.", "prnt.sc")

# Priority order — forms/email are the channels that actually land hires.
_ORDER = {"form": 0, "email": 1, "discord": 2, "telegram": 3, "link": 4}


def _classify(url: str) -> tuple[str, str] | None:
    low = url.lower()
    if any(n in low for n in _NOISE):
        return None
    if "forms.gle" in low or "docs.google.com/forms" in low or "/forms/" in low:
        return "form", "Google Form"
    if "typeform.com" in low:
        return "form", "Typeform"
    if "airtable.com" in low:
        return "form", "Airtable form"
    if "tally.so" in low:
        return "form", "Tally form"
    if "discord.gg" in low or "discord.com/invite" in low:
        return "discord", "Discord"
    if "t.me/" in low or "telegram.me" in low:
        return "telegram", "Telegram"
    if "calendly.com" in low or "cal.com" in low:
        return "link", "Scheduling"
    return "link", "Link"


def extract_contacts(text: str) -> list[dict]:
    """Return actionable contacts found in `text`, best channels first:
    [{"kind": "form"|"email"|"discord"|"telegram"|"link", "value": ..., "label": ...}]."""
    if not text:
        return []
    found: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, value: str, label: str) -> None:
        v = value.rstrip(".,);]}>\"'")
        key = v.lower()
        if key in seen:
            return
        seen.add(key)
        found.append({"kind": kind, "value": v, "label": label})

    for email in _EMAIL_RE.findall(text):
        add("email", email, "Email")
    for url in _URL_RE.findall(text):
        c = _classify(url)
        if c:
            add(c[0], url, c[1])

    found.sort(key=lambda c: _ORDER.get(c["kind"], 9))
    return found
