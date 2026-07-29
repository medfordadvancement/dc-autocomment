"""
Discover Crypto — auto-comment poller (runs on GitHub Actions).

Each run:
  1. Reads the channel's public upload feed (videos + shorts + live replays).
  2. For any upload not seen before AND public, posts the configured comment
     via the YouTube Data API (commentThreads.insert).
  3. Records the video id in seen.json so it never double-posts. The workflow
     commits seen.json back to the repo after each run.

Pinning is NOT done here — YouTube has no pin API. You pin each auto-posted
comment manually; the run log prints exactly which video ids to pin.

Config comes from environment variables (set by the workflow):
  CHANNEL_ID, COMMENT_TEXT               (from the workflow file)
  OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET,
  OAUTH_REFRESH_TOKEN                     (from GitHub repo secrets)
  SEED_ON_FIRST_RUN  (optional, default "true")
  STATE_FILE         (optional, default "seen.json")
"""

import json
import os
import xml.etree.ElementTree as ET

import requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CHANNEL_ID = os.environ["CHANNEL_ID"]
COMMENT_TEXT = os.environ["COMMENT_TEXT"]
CLIENT_ID = os.environ["OAUTH_CLIENT_ID"]
CLIENT_SECRET = os.environ["OAUTH_CLIENT_SECRET"]
REFRESH_TOKEN = os.environ["OAUTH_REFRESH_TOKEN"]

SEED_ON_FIRST_RUN = os.environ.get("SEED_ON_FIRST_RUN", "true").lower() == "true"
STATE_FILE = os.environ.get("STATE_FILE", "seen.json")

FEED_URL = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={CHANNEL_ID}"
NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}
MAX_STATE = 500  # keep seen.json bounded


def youtube():
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.force-ssl"],
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def load_seen():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    trimmed = sorted(seen)[-MAX_STATE:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, indent=0)


def recent_video_ids():
    r = requests.get(FEED_URL, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.text)
    out = []
    for entry in root.findall("atom:entry", NS):
        vid = entry.find("yt:videoId", NS)
        if vid is not None and vid.text:
            out.append(vid.text)
    return out


def is_public(yt, video_id):
    resp = yt.videos().list(part="status", id=video_id).execute()
    items = resp.get("items", [])
    return bool(items) and items[0]["status"]["privacyStatus"] == "public"


def post_comment(yt, video_id):
    yt.commentThreads().insert(
        part="snippet",
        body={
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": COMMENT_TEXT}},
            }
        },
    ).execute()


def main():
    seen = load_seen()
    ids = recent_video_ids()

    # First-ever run: record existing uploads, comment on none of them.
    if not seen and SEED_ON_FIRST_RUN:
        save_seen(set(ids))
        print(f"Seeded {len(ids)} existing uploads; posted nothing.")
        return

    yt = youtube()
    posted, skipped = [], []
    for vid in ids:
        if vid in seen:
            continue
        try:
            if not is_public(yt, vid):
                # Not public yet (scheduled/premiere/processing). Leave
                # unmarked so a later run picks it up once it's live.
                skipped.append(f"{vid} (not public yet)")
                continue
            post_comment(yt, vid)
            seen.add(vid)
            posted.append(vid)
        except Exception as e:  # noqa: BLE001 — log and keep going
            skipped.append(f"{vid} (error: {e})")

    save_seen(seen)

    if posted:
        print("COMMENTED — pin these now:")
        for vid in posted:
            print(f"  https://studio.youtube.com/video/{vid}/comments")
    else:
        print("No new public uploads to comment on.")
    if skipped:
        print("Skipped:")
        for s in skipped:
            print(f"  {s}")


if __name__ == "__main__":
    main()
