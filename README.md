# Discover Crypto — Auto-Comment on New Uploads

Automatically posts your community comment on every new video / short / live
replay, within ~10 minutes of it going public. You still **pin** each one
manually (YouTube has no pin API — nothing can automate that step).

- **Channel:** Discover Crypto (`UCjemQfjaXAzA-95RKoy9n_g`)
- **Comment posted:**
  > Join our community - https://www.skool.com/discovercrypto/about - to learn how to stop guessing and start investing with a system.
- **Cost:** ~$0/month (inside Google Cloud free tiers)
- **How it runs:** Cloud Scheduler → Cloud Function (Python) → YouTube Data API,
  with a Cloud Storage file remembering which videos it already commented on.

---

## What YOU do vs. what's already built

Already written for you in this folder: `main.py`, `get_refresh_token.py`,
`requirements.txt`. You don't edit code. You do the account/permission steps
below (they need your sign-in) and run the deploy commands.

Steps marked **[you — sign-in required]** are ones the assistant is not allowed
to do for you (they involve signing in / granting access).

---

## Step 1 — Create a Google Cloud project  **[you — sign-in required]**

1. Go to https://console.cloud.google.com/ and sign in with the Google account
   that manages the Discover Crypto channel.
2. Top bar → project dropdown → **New Project**. Name it e.g. `dc-autocomment`.
3. Note the **Project ID** (looks like `dc-autocomment-472913`). You'll use it
   below as `PROJECT_ID`.

## Step 2 — Install the gcloud CLI (one time)

Download: https://cloud.google.com/sdk/docs/install (Windows installer).
Then in a terminal:

```bash
gcloud auth login
gcloud config set project PROJECT_ID
```

## Step 3 — Enable the APIs

```bash
gcloud services enable \
  youtube.googleapis.com \
  cloudfunctions.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  storage.googleapis.com
```

## Step 4 — Create the OAuth client  **[you — sign-in required]**

This is the identity that posts the comment.

1. Console → **APIs & Services → OAuth consent screen**.
   - User type: **External** → Create.
   - Fill app name (e.g. "DC AutoComment"), your email. Save through the steps.
   - On **Scopes**, add `https://www.googleapis.com/auth/youtube.force-ssl`.
   - Add your Google account as a **Test user**.
2. ⚠️ **CRITICAL — publish the app.** Back on the OAuth consent screen, set
   **Publishing status → In production** (click "Publish app" / "Prepare for
   verification" and confirm). If you leave it in *Testing*, your refresh token
   **expires after 7 days** and the automation silently dies every week. In
   production it does not expire. You'll see an "unverified app" warning during
   Step 5 — that's fine, click through it (Advanced → Go to app).
3. Console → **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
   - Application type: **Desktop app**. Create.
   - **Download JSON**, rename it to `client_secret.json`, and put it in this
     folder (next to `get_refresh_token.py`).
   - Also note its **Client ID** and **Client secret** — needed in Step 6.

## Step 5 — Mint your refresh token  **[you — sign-in required]**

On your computer, in this folder:

```bash
pip install google-auth-oauthlib google-auth
python get_refresh_token.py
```

A browser opens. Sign in, pick the **Discover Crypto** channel if asked, click
through the unverified-app warning, and approve. The script prints a
**refresh token** — copy it for Step 6.

## Step 6 — Create the state bucket and deploy the function

Pick a globally-unique bucket name (e.g. `dc-autocomment-state-472913`).

```bash
# state bucket (remembers which videos are already done)
gcloud storage buckets create gs://YOUR_BUCKET_NAME --location=US

# deploy the poller
gcloud functions deploy dc-autocomment \
  --gen2 --runtime=python312 --region=us-central1 \
  --source=. --entry-point=run --trigger-http --no-allow-unauthenticated \
  --set-env-vars=CHANNEL_ID=UCjemQfjaXAzA-95RKoy9n_g,STATE_BUCKET=YOUR_BUCKET_NAME,OAUTH_CLIENT_ID=YOUR_CLIENT_ID,OAUTH_CLIENT_SECRET=YOUR_CLIENT_SECRET,OAUTH_REFRESH_TOKEN=YOUR_REFRESH_TOKEN \
  --set-env-vars=^~^COMMENT_TEXT=Join our community - https://www.skool.com/discovercrypto/about - to learn how to stop guessing and start investing with a system.
```

> The `^~^` before `COMMENT_TEXT` changes the delimiter so the commas/URL in the
> comment don't break the flag. Keep it exactly as shown.

## Step 7 — Schedule it every 10 minutes

```bash
# service account for the scheduler to call the function
gcloud iam service-accounts create dc-autocomment-invoker

PROJECT_ID=$(gcloud config get-value project)
FN_URL=$(gcloud functions describe dc-autocomment --gen2 --region=us-central1 --format='value(serviceConfig.uri)')

# let that service account invoke the function
gcloud run services add-iam-policy-binding dc-autocomment \
  --region=us-central1 \
  --member="serviceAccount:dc-autocomment-invoker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role=roles/run.invoker

# every 10 minutes
gcloud scheduler jobs create http dc-autocomment-job \
  --location=us-central1 --schedule="*/10 * * * *" \
  --uri="${FN_URL}" --http-method=GET \
  --oidc-service-account-email="dc-autocomment-invoker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="${FN_URL}"
```

---

## First run behavior (important)

The **very first** time it runs, it records your current recent uploads as
"already handled" and posts **nothing** — so it won't spam videos that already
exist (you've already done those manually). From then on, only *new* uploads
get a comment. (Controlled by `SEED_ON_FIRST_RUN=true`, the default.)

## How you know what to pin

After each run, the function logs the video ids it commented on. See them at:
Console → the function → **Logs**, or:

```bash
gcloud functions logs read dc-autocomment --gen2 --region=us-central1 --limit=20
```

Each logged `posted` id → open `https://studio.youtube.com/video/THAT_ID/comments`,
find your comment, click ⋮ → **Pin**. (Want pin reminders pushed to you instead?
Tell the assistant — the function can be extended to email/DM you the list.)

## Changing the comment text later

Re-run just the env-var update:

```bash
gcloud functions deploy dc-autocomment --gen2 --region=us-central1 --source=. \
  --set-env-vars=^~^COMMENT_TEXT=Your new comment here
```

## Turning it off

```bash
gcloud scheduler jobs pause dc-autocomment-job --location=us-central1
```
