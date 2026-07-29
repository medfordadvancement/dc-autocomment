# Discover Crypto — New-Upload Notifier (Telegram)

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

## Setup — Telegram (the only thing left to do)

### Step 1 — Create a bot
1. In Telegram, open a chat with **@BotFather**
2. Send `/newbot`, follow the prompts (give it any name + username)
3. BotFather replies with a **bot token** (looks like `12345678:AAE...`). Keep it.

### Step 2 — Start a chat with your new bot
Search your bot's username in Telegram, open it, and press **Start** (send
`/start`). A bot can't message you until you've started it.

### Step 3 — Get your chat ID
Open a chat with **@userinfobot** and press Start. It replies with your numeric
**Id** — that's your `TELEGRAM_CHAT_ID`.

### Step 4 — Add the two secrets
Go to **https://github.com/medfordadvancement/dc-autocomment/settings/secrets/actions**
and add:

| Secret name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather (Step 1) |
| `TELEGRAM_CHAT_ID` | your Id from @userinfobot (Step 3) |

(The old `OAUTH_*` secrets are no longer used — you can delete them.)

### Step 5 — Test it
Repo → **Actions** → **DC upload notifier** → **Run workflow** → tick the
**test** box → **Run workflow**. You should get a "✅ Test alert" in Telegram
within a few seconds.

Then run it once normally (without the test box) — the first normal run records
your current uploads and sends nothing, so it won't blast you for existing
videos. After that, every new upload triggers an alert.

---

## What each alert looks like
```
🆕 New Discover Crypto upload

<video title>
https://youtu.be/<id>

Comment to post + pin:
Join our community - https://www.skool.com/discovercrypto/about - ...

Open comments to post & pin:
https://studio.youtube.com/video/<id>/comments
```

## Changing the comment text
Edit `COMMENT_TEXT` in `.github/workflows/autocomment.yml`, commit, push.

## Turning it off
Repo → Actions → **DC upload notifier** → ••• → **Disable workflow**.
