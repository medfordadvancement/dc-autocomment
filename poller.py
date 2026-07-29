"""
Discover Crypto — new-upload notifier (runs on GitHub Actions).

Every run (~10 min):
  1. Reads the channel's public upload feed (videos + shorts + live replays).
     No login/OAuth needed — the feed is public.
  2. For any upload it hasn't seen before, sends you a Telegram message with the
     title, the ready-to-paste comment, and a direct link to its comments page.
  3. Records the video id in seen.json so it never alerts twice.

You then paste the comment and pin it (~20 seconds). Posting/pinning stays
manual because YouTube won't let a manager account do it via API.

Config (env vars set by the workflow / GitHub secrets):
  CHANNEL_ID, COMMENT_TEXT     (workflow file)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   (GitHub secrets)
  SEED_ON_FIRST_RUN  (optional, default "true")
  STATE_FILE         (optional, default "seen.json")
  TEST_ALERT         (optional; "true" sends one test message and exits)
"""

import json
import os
import xml.etree.ElementTree as ET

import requests

CHANNEL_ID = os.environ["CHANNEL_ID"]
COMMENT_TEXT = os.environ["COMMENT_TEXT"]              # for long-form videos + lives
COMMENT_TEXT_SHORTS = os.environ["COMMENT_TEXT_SHORTS"]  # for Shorts (links aren't clickable)
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

SEED_ON_FIRST_RUN = os.environ.get("SEED_ON_FIRST_RUN", "true").lower() == "true"
STATE_FILE = os.environ.get("STATE_FILE", "seen.json")
TEST_ALERT = os.environ.get("TEST_ALERT", "").lower() == "true"

FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}
MAX_STATE = 500


def load_seen():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(seen)[-MAX_STATE:], f, indent=0)


def recent_uploads():
    r = requests.get(FEED_URL, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    out = []
    for e in root.findall("atom:entry", NS):
        vid = e.find("yt:videoId", NS)
        title = e.find("atom:title", NS)
        if vid is not None and vid.text:
            out.append((vid.text, title.text if title is not None else "(untitled)"))
    return out


def is_short(vid):
    # A Short stays on /shorts/<id> (HTTP 200); a normal video or live redirects
    # (303) to /watch. Falls back to treating it as a normal video on any error.
    try:
        r = requests.head(
            f"https://www.youtube.com/shorts/{vid}",
            allow_redirects=False,
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def send_telegram(text):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    r.raise_for_status()


def alert(vid, title):
    short = is_short(vid)
    kind = "Short" if short else "video"
    comment = COMMENT_TEXT_SHORTS if short else COMMENT_TEXT
    send_telegram(
        f"🆕 New Discover Crypto {kind}\n\n"
        f"{title}\n"
        f"https://youtu.be/{vid}\n\n"
        "Comment to post + pin:\n"
        f"{comment}\n\n"
        "Open comments to post & pin:\n"
        f"https://studio.youtube.com/video/{vid}/comments"
    )


def main():
    if TEST_ALERT:
        send_telegram(
            "✅ Test alert from your Discover Crypto upload notifier. "
            "If you can read this, notifications are working."
        )
        print("Sent test alert.")
        return

    seen = load_seen()
    uploads = recent_uploads()
    ids = [u[0] for u in uploads]

    # First-ever run: record existing uploads, alert on none of them.
    if not seen and SEED_ON_FIRST_RUN:
        save_seen(set(ids))
        print(f"Seeded {len(ids)} existing uploads; no alerts sent.")
        return

    alerted = []
    for vid, title in uploads:
        if vid in seen:
            continue
        try:
            alert(vid, title)
            seen.add(vid)
            alerted.append(vid)
        except Exception as e:  # noqa: BLE001 — log and keep going
            print(f"Alert failed for {vid}: {e}")

    save_seen(seen)
    print(f"Alerted on {len(alerted)} new upload(s): {alerted}" if alerted
          else "No new uploads.")


if __name__ == "__main__":
    main()
