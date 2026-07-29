"""
Discover Crypto - new-upload notifier with AI-written pinned comments.

Every run (~10 min):
  1. Reads the channel's public upload feed (videos + shorts + live replays).
     No login needed - the feed is public.
  2. For any upload not seen before, it:
       - detects Short vs long-form video/live,
       - writes a comment tailored to the video title, in the partner's voice
         (via the Claude API), ending in the Skool link for long-form or the
         "tap our channel" CTA for Shorts,
       - falls back to a static comment if the AI call fails or no key is set,
       - sends you a Telegram alert with the comment to paste and a direct link
         to the comments page,
       - logs the comment to comment_log.csv so you can review what went out.
  3. Records the video id in seen.json so it never alerts twice.

Config (env vars set by the workflow / GitHub secrets):
  CHANNEL_ID                                (workflow file)
  SKOOL_LINK           (optional, defaults to the discovercrypto about page)
  COMMENT_FALLBACK, COMMENT_FALLBACK_SHORTS (workflow file; used if AI fails)
  ANTHROPIC_API_KEY    (GitHub secret; if unset, always uses the fallback)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID      (GitHub secrets)
  SEED_ON_FIRST_RUN    (optional, default "true")
  STATE_FILE           (optional, default "seen.json")
  TEST_ALERT           (optional; "true" sends one test message and exits)
"""

import csv
import datetime
import json
import os
import xml.etree.ElementTree as ET

import requests

CHANNEL_ID = os.environ["CHANNEL_ID"]
SKOOL_LINK = os.environ.get("SKOOL_LINK", "https://www.skool.com/discovercrypto/about")
FALLBACK = os.environ["COMMENT_FALLBACK"]
FALLBACK_SHORTS = os.environ["COMMENT_FALLBACK_SHORTS"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")  # optional

SEED_ON_FIRST_RUN = os.environ.get("SEED_ON_FIRST_RUN", "true").lower() == "true"
STATE_FILE = os.environ.get("STATE_FILE", "seen.json")
TEST_ALERT = os.environ.get("TEST_ALERT", "").lower() == "true"
LOG_FILE = "comment_log.csv"

FEED_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}
MAX_STATE = 500
SHORTS_CTA = "Tap our channel and hit the top link."


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


SYSTEM_PROMPT = (
    "You write ONE pinned comment for a new Discover Crypto YouTube upload, "
    "tailored to the video's topic. Voice: short, one line, value and education "
    "first, calm and confident. Never hype, never salesy.\n\n"
    "Match the style of these real examples exactly:\n"
    "- Learn how to short so you can make money regardless of the market direction\n"
    "- Learn to build wealth with crypto\n"
    "- Follow our wealth building strategies\n"
    "- We teach these strategies here\n\n"
    "Rules:\n"
    "- One short sentence, clearly tied to the video title's topic.\n"
    "- Frame it as what the viewer will learn or what the community teaches.\n"
    "- No hashtags, no emojis, no quotation marks.\n"
    "- Never use the word 'free'.\n"
    "- Never use em dashes; use plain hyphens or rephrase.\n"
    "- Do NOT include any link or URL.\n"
    "- Output only the sentence, with no preamble or explanation."
)


def generate_comment(title, short):
    import anthropic  # imported lazily so a missing dep never blocks fallbacks

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        output_config={"effort": "low"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Video title: {title}"}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = text.strip('"').strip("'").strip()
    if not text:
        raise ValueError("empty generation")
    if short:
        if not text.endswith((".", "!", "?")):
            text += "."
        return f"{text} {SHORTS_CTA}"
    return f"{text.rstrip('.')} - {SKOOL_LINK}"


def build_comment(title, short):
    if ANTHROPIC_API_KEY:
        try:
            return generate_comment(title, short), "AI"
        except Exception as e:  # noqa: BLE001 - fall back, never block the alert
            print(f"AI generation failed for '{title}': {e}")
    return (FALLBACK_SHORTS if short else FALLBACK), "fallback"


def log_comment(vid, kind, source, comment):
    new_file = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp_utc", "video_id", "kind", "source", "comment"])
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        w.writerow([stamp, vid, kind, source, comment])


def send_telegram(text):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True},
        timeout=30,
    )
    r.raise_for_status()


def send_alert(vid, title, kind, source, comment):
    # Message 1: what it is + one-tap link to its comments page.
    send_telegram(
        f"New Discover Crypto {kind}  ({source} comment)\n\n"
        f"{title}\n"
        f"https://youtu.be/{vid}\n\n"
        "Tap to open its comments page (post + pin here):\n"
        f"https://studio.youtube.com/video/{vid}/comments\n\n"
        "The exact comment to pin is in the next message - tap it to copy."
    )
    # Message 2: the bare comment, so a single tap copies exactly it.
    send_telegram(comment)


def main():
    if TEST_ALERT:
        sample_title = "LEGENDARY Bitcoin Bottom Signal RETURNS!"
        try:
            comment, source = build_comment(sample_title, False)
            status = "working" if source == "AI" else "using FALLBACK (check ANTHROPIC_API_KEY)"
            send_telegram(
                f"Test alert. AI comment generation is {status}.\n\n"
                f"Sample comment for a video titled '{sample_title}':\n\n{comment}"
            )
            print(f"Test alert sent. Source: {source}")
        except Exception as e:  # noqa: BLE001
            send_telegram(f"Test alert. Something errored: {e}")
            print(f"Test error: {e}")
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
    # Oldest first so alerts arrive in publish order.
    for vid, title in reversed(uploads):
        if vid in seen:
            continue
        try:
            short = is_short(vid)
            kind = "Short" if short else "video"
            comment, source = build_comment(title, short)
            send_alert(vid, title, kind, source, comment)
            log_comment(vid, kind, source, comment)
            seen.add(vid)
            alerted.append((vid, source))
        except Exception as e:  # noqa: BLE001 - log and keep going
            print(f"Alert failed for {vid}: {e}")

    save_seen(seen)
    print(f"Alerted on {len(alerted)}: {alerted}" if alerted else "No new uploads.")


if __name__ == "__main__":
    main()
