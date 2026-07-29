# Discover Crypto - New-Upload Notifier (Telegram)

Alerts you on Telegram the moment a new video / short / live publishes, with the
comment text ready to paste and a direct link to that video's comments page. You
paste + pin (~20 seconds).

> Why not auto-post? Posting/pinning as Discover Crypto requires **owner-level**
> API access to the channel, which isn't available (manager access can't
> authorize it, and Google blocks unverified apps on the owner account). Detecting
> uploads needs no login at all, so this half is rock-solid.

- **Channel:** Discover Crypto (`UCjemQfjaXAzA-95RKoy9n_g`)
- **Comment sent in each alert:**
  > Join our community - https://www.skool.com/discovercrypto/about - to learn how to stop guessing and start investing with a system.
- **Cost:** free (GitHub Actions + Telegram)
- **How it runs:** a GitHub Actions cron job (every ~10 min) runs `poller.py`,
  which checks the public feed and messages you on Telegram for new uploads.
  `seen.json` remembers what's already been alerted.

---

## Setup - Telegram (the only thing left to do)

### Step 1 - Create a bot
1. In Telegram, open a chat with **@BotFather**
2. Send `/newbot`, follow the prompts (give it any name + username)
3. BotFather replies with a **bot token** (looks like `12345678:AAE...`). Keep it.

### Step 2 - Start a chat with your new bot
Search your bot's username in Telegram, open it, and press **Start** (send
`/start`). A bot can't message you until you've started it.

### Step 3 - Get your chat ID
Open a chat with **@userinfobot** and press Start. It replies with your numeric
**Id** - that's your `TELEGRAM_CHAT_ID`.

### Step 4 - Add the two secrets
Go to **https://github.com/medfordadvancement/dc-autocomment/settings/secrets/actions**
and add:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather (Step 1) |
| `TELEGRAM_CHAT_ID` | your Id from @userinfobot (Step 3) |
| `ANTHROPIC_API_KEY` | an Anthropic API key (writes the per-video comment; optional) |

`ANTHROPIC_API_KEY` is optional: with it, each comment is written to match the
video. Without it, the notifier uses the fallback comments in the workflow file.
(The old `OAUTH_*` secrets are no longer used - you can delete them.)

### Step 5 - Test it
Repo → **Actions** → **DC upload notifier** → **Run workflow** → tick the
**test** box → **Run workflow**. You should get a "✅ Test alert" in Telegram
within a few seconds.

Then run it once normally (without the test box) - the first normal run records
your current uploads and sends nothing, so it won't blast you for existing
videos. After that, every new upload triggers an alert.

---

## What each alert looks like
Two Telegram messages. First the context + a one-tap link to the comments page:
```
New Discover Crypto video  (AI comment)

<video title>
https://youtu.be/<id>

Tap to open its comments page (post + pin here):
https://studio.youtube.com/video/<id>/comments

The exact comment to pin is in the next message - tap it to copy.
```
Then the bare comment as its own message, so one tap copies exactly it.

## How the comment is written
For each new upload the notifier writes a comment **tailored to the video title,
in the partner's voice** (short, value-first, e.g. "Learn to build wealth with
crypto"), using the Claude API:
- **Long-form / live** ends with the clickable Skool link.
- **Shorts** end with "Tap our channel and hit the top link" (Shorts links are
  not clickable, so viewers are sent to the channel's top link).

The alert header shows `AI comment` when it was written by the model, or
`fallback comment` when the AI call was skipped or failed (in which case it uses
`COMMENT_FALLBACK` / `COMMENT_FALLBACK_SHORTS` from the workflow file). Every
comment that goes out is logged to `comment_log.csv` in the repo (timestamp,
video id, kind, source, comment) so you can review what was sent.

To change the model's style, edit the guidance in `poller.py` (the
`SYSTEM_PROMPT`). To change the fallback wording, edit the workflow file.

## Turning it off
Repo → Actions → **DC upload notifier** → ••• → **Disable workflow**.
