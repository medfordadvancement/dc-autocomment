"""
Discover Crypto - new-upload notifier with A/B comment rotation (GitHub Actions).

Every run (~10 min):
  1. Reads the channel's public upload feed (videos + shorts + live replays).
     No login/OAuth needed - the feed is public.
  2. For any upload it hasn't seen before, it:
       - detects whether it's a Short or a long-form video/live,
       - picks the next A/B comment variant (alternates A, B, A, B, ...),
       - sends you a Telegram message with the title, the variant, the comment
         to paste, and a direct link to the comments page,
       - logs the choice to ab_log.csv so you can compare which variant drives
         more Skool signups.
  3. Records the video id in seen.json so it never alerts twice.

Config (env vars set by the workflow / GitHub secrets):
  CHANNEL_ID                                            (workflow file)
  COMMENT_TEXT_A, COMMENT_TEXT_B                        (long-form / live)
  COMMENT_TEXT_SHORTS_A, COMMENT_TEXT_SHORTS_B          (Shorts)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID                  (GitHub secrets)
  SEED_ON_FIRST_RUN  (optional, default "true")
  STATE_FILE         (optional, default "seen.json")
  TEST_ALERT         (optional; "true" sends one test message and exits)
"""

import csv
import datetime
import json
import os
import xml.etree.ElementTree as ET

import requests

CHANNEL_ID = os.environ["CHANNEL_ID"]
COMMENT_A = os.environ["COMMENT_TEXT_A"]
COMMENT_B = os.environ["COMMENT_TEXT_B"]
COMMENT_SHORTS_A = os.environ["COMMENT_TEXT_SHORTS_A"]
COMMENT_SHORTS_B = os.environ["COMMENT_TEXT_SHORTS_B"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

SEED_ON_FIRST_RUN = os.environ.get("SEED_ON_FIRST_RUN", "true").lower() == "true"
STATE_FILE = os.environ.get("STATE_FILE", "seen.json")
TEST_ALERT = os.environ.get("TEST_ALERT", "").lower() == "true"
AB_LOG = "ab_log.csv"

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


def ab_count():
    # Number of alerts already logged, used to alternate A / B.
    if not os.path.exists(AB_LOG):
        return 0
    with open(AB_LOG, encoding="utf-8") as f:
        return max(0, sum(1 for _ in f) - 1)  # minus the header row


def log_ab(vid, kind, variant, title):
    new_file = not os.path.exists(AB_LOG)
    with open(AB_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp_utc", "video_id", "kind", "variant", "title"])
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        w.writerow([stamp, vid, kind, variant, title])


def pick_comment(short, variant):
    if short:
        return COMMENT_SHORTS_A if variant == "A" else COMMENT_SHORTS_B
    return COMMENT_A if variant == "A" else COMMENT_B


def send_telegram(text):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    r.raise_for_status()


def send_alert(vid, title, kind, variant, comment):
    send_telegram(
        f"New Discover Crypto {kind}  (test variant {variant})\n\n"
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
            "Test alert from your Discover Crypto upload notifier. "
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

    count = ab_count()
    alerted = []
    # Oldest first so A/B alternation follows publish order.
    for vid, title in reversed(uploads):
        if vid in seen:
            continue
        try:
            short = is_short(vid)
            kind = "Short" if short else "video"
            variant = "A" if count % 2 == 0 else "B"
            comment = pick_comment(short, variant)
            send_alert(vid, title, kind, variant, comment)
            log_ab(vid, kind, variant, title)
            count += 1
            seen.add(vid)
            alerted.append((vid, kind, variant))
        except Exception as e:  # noqa: BLE001 - log and keep going
            print(f"Alert failed for {vid}: {e}")

    save_seen(seen)
    print(f"Alerted on {len(alerted)}: {alerted}" if alerted else "No new uploads.")


if __name__ == "__main__":
    main()
