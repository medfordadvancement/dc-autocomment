# Discover Crypto — Auto-Comment on New Uploads (GitHub Actions)

Automatically posts your community comment on every new video / short / live
replay, within ~10 minutes of it going public. You still **pin** each one
manually (YouTube has no pin API — nothing can automate that step).

- **Channel:** Discover Crypto (`UCjemQfjaXAzA-95RKoy9n_g`)
- **Comment posted:**
  > Join our community - https://www.skool.com/discovercrypto/about - to learn how to stop guessing and start investing with a system.
- **Cost:** free (GitHub Actions, no credit card)
- **How it runs:** a GitHub Actions cron job (every ~10 min) runs `poller.py`, which checks the channel's `feeds/videos.xml` and posts the
  comment on new public uploads.
  `seen.json` (committed back after each run) remembers what's already done.

---

## Status so far

- ✅ Google Cloud project `dc-autocomment` created
- ✅ YouTube Data API enabled on it
- ✅ Code written and committed locally in this folder
- ⬜ **Steps below need you** (they require your Google + GitHub sign-in)

Steps marked **[you]** need your sign-in/consent and can't be done for you.

---

## Step 1 — Create the OAuth client  **[you]**

This is the identity that posts the comment.

1. https://console.cloud.google.com/ → make sure the project is **dc-autocomment**.
2. **APIs & Services → OAuth consent screen**
   - User type: **External** → Create. Fill app name (e.g. "DC AutoComment")
     and your email; save through the pages.
   - Add scope `https://www.googleapis.com/auth/youtube.force-ssl`.
   - Add your Google account under **Test users**.
3. ⚠️ **CRITICAL — publish to production.** On the OAuth consent screen set
   **Publishing status → In production** ("Publish app" → confirm). If you leave
   it in *Testing*, your refresh token **expires after 7 days** and the whole
   thing silently dies every week. In production it never expires. You'll see an
   "unverified app" warning later — that's expected, click through it.
4. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
   - Application type: **Desktop app** → Create.
   - **Download JSON**, rename to `client_secret.json`, put it in this folder.
     (It's gitignored — it will not be uploaded to GitHub.)

## Step 2 — Mint your refresh token  **[you]**

In this folder, on your computer:

```bash
pip install -r requirements.txt
python get_refresh_token.py
```

A browser opens. Sign in, **pick the Discover Crypto channel if asked**, click
through the unverified-app warning, approve. It prints a **refresh token** —
keep it for Step 4. (This is the step that ties the automation to your channel.)

## Step 3 — Put the code on GitHub  **[you sign-in, I can run the push]**

Create an **empty** repo (a **public** repo is recommended — it keeps Actions
100% free with no minute limits, and contains no secrets; your tokens live in
encrypted repo secrets, never in the code):

- Easiest: install GitHub CLI (https://cli.github.com/), run `gh auth login`,
  then tell the assistant — it will create the repo and push for you.
- Or manually: create a new empty repo at https://github.com/new (no README),
  then in this folder:
  ```bash
  git branch -M main
  git remote add origin https://github.com/YOURNAME/dc-autocomment.git
  git push -u origin main
  ```

## Step 4 — Add the three secrets  **[you]**

In the GitHub repo → **Settings → Secrets and variables → Actions → New
repository secret**. Add exactly these three (names must match):

| Secret name | Value |
|---|---|
| `OAUTH_CLIENT_ID` | Client ID from Step 1.4 |
| `OAUTH_CLIENT_SECRET` | Client secret from Step 1.4 |
| `OAUTH_REFRESH_TOKEN` | The refresh token from Step 2 |

(The channel id and comment text are not secret — they're in the workflow file.)

## Step 5 — Turn it on

Repo → **Actions** tab → enable workflows if prompted. The job runs every
~10 min on its own. To test immediately: Actions → **DC auto-comment** → **Run
workflow**.

---

## First run behavior (important)

The **very first** run records your current recent uploads as "already handled"
and posts **nothing** — so it won't spam videos that already exist. After that,
only *new* uploads get a comment.

## How you know what to pin

Each run logs the exact Studio links to pin. See them in: repo → **Actions** →
click the latest run → **post** job → "Run poller" step. Any `COMMENTED — pin
these now:` lines are your to-do. Open each → find your comment → ⋮ → **Pin**.

(Want those pin links emailed/DM'd to you instead of checking the Actions log?
Ask the assistant — easy to add.)

## Changing the comment later

Edit `COMMENT_TEXT` in `.github/workflows/autocomment.yml`, commit, push.

## Turning it off

Repo → Actions → **DC auto-comment** → ••• → **Disable workflow**.
