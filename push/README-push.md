# Instant Push Notifier (Cloudflare Worker)

Replaces the ~hourly GitHub polling with **instant** alerts: YouTube's WebSub hub
pushes to this Worker the second you publish, and it fires the Telegram alert in
a few seconds. Free, no credit card, always on.

You already have the three values it needs (from the GitHub setup): your
**Anthropic API key**, **Telegram bot token**, and **Telegram chat id**. You will
re-enter them in Cloudflare.

Everything is done in the Cloudflare dashboard. No install, no command line.

---

## Step 1 - Make a Cloudflare account
Go to **https://dash.cloudflare.com/sign-up**, sign up (free, no card).

## Step 2 - Create the Worker
1. Left sidebar → **Workers & Pages** → **Create** → **Create Worker**.
2. Name it `dc-notify` → **Deploy**.
3. Note the URL it gives you, like `https://dc-notify.<your-subdomain>.workers.dev`.
   This is your **WORKER_URL** (base only, no trailing slash).
4. Click **Edit code**, delete the sample, paste the entire contents of
   [worker.js](worker.js), then **Deploy**.

## Step 3 - Create the dedup storage (KV)
1. Left sidebar → **Storage & Databases** → **KV** → **Create a namespace**.
2. Name it `dc-notify-seen` → **Add**.
3. Back on the Worker: **Settings** → **Bindings** → **Add** → **KV namespace**.
   - **Variable name:** `SEEN`  (exactly this)
   - **KV namespace:** pick `dc-notify-seen` → **Deploy**.

## Step 4 - Add the variables and secrets
On the Worker: **Settings** → **Variables and Secrets** → add each of these
(**Secret** for the two tokens and the API key, **Text** for the rest):

| Name | Type | Value |
|---|---|---|
| `ANTHROPIC_API_KEY` | Secret | your Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | Secret | your Telegram bot token |
| `TELEGRAM_CHAT_ID` | Text | your Telegram chat id |
| `CHANNEL_ID` | Text | `UCjemQfjaXAzA-95RKoy9n_g` |
| `WORKER_URL` | Text | your worker URL from Step 2 (no trailing slash) |
| `PATH_TOKEN` | Text | `d4481a7dcc7a0b52830e28774a5a7672` |
| `SKOOL_LINK` | Text | `https://www.skool.com/discovercrypto/about` |
| `COMMENT_FALLBACK` | Text | `We teach these strategies here - https://www.skool.com/discovercrypto/about` |
| `COMMENT_FALLBACK_SHORTS` | Text | `We teach these strategies here. Tap our channel and hit the top link.` |

Click **Deploy** after adding them.

## Step 5 - Keep the subscription alive (cron)
On the Worker: **Settings** → **Triggers** → **Cron Triggers** → **Add**.
Enter `0 0 */5 * *` (re-subscribes every 5 days; the lease lasts 10). **Add**.

## Step 6 - Turn it on
In your browser, visit (replace the host with your real WORKER_URL):
```
https://dc-notify.<your-subdomain>.workers.dev/yt/d4481a7dcc7a0b52830e28774a5a7672?action=subscribe
```
You should see: `seeded N existing uploads; subscribe returned 202`. That records
your current uploads (so it won't blast you for old ones) and subscribes to the
push feed. Within a minute or two the subscription is verified and live.

## Step 7 - Stop the old GitHub poller (so you don't get double alerts)
Repo → **Actions** → **DC upload notifier** → **•••** → **Disable workflow**.
(Leave it disabled but present - it's your fallback if you ever want polling back.)

---

## Test it
Publish anything (even unlisted, then delete) or wait for your next real upload.
The alert should arrive within seconds. If it doesn't, check the Worker's **Logs**
tab (Workers & Pages → dc-notify → Logs) for errors.

## What changed vs the GitHub version
- **Speed:** seconds, not up to an hour.
- Same AI-written, partner-voice comments and same two-message Telegram format.
- Dedup lives in Cloudflare KV (handles duplicate pings and title-edit re-pings).
- No `seen.json` / `comment_log.csv` here; the Worker's Logs tab shows activity.

## If push ever stops
Re-run Step 6's subscribe URL. If it still misbehaves, re-enable the GitHub
workflow (Step 7 in reverse) as a fallback while you debug.
