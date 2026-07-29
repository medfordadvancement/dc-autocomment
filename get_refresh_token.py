"""
ONE-TIME local script — you run this yourself on your own computer.

It opens a browser, asks you to sign in and grant permission to post
comments, then prints a long-lived REFRESH TOKEN. You paste that token into
the cloud deployment (see README, Step 6).

Why you run this and not the assistant: it requires signing into your Google
account and approving access — a credential/consent step that must be yours.

Prerequisites:
  1. Python 3 installed.
  2. In this folder, a file named  client_secret.json  — this is the OAuth
     "Desktop app" client you download from Google Cloud (README Step 4).
  3. Install the two libraries:
        pip install google-auth-oauthlib google-auth

Then run:
        python get_refresh_token.py

IMPORTANT: On the Google consent screen, if you're asked which channel /
account to use, choose the **Discover Crypto** brand channel (or the account
that manages it). The refresh token is tied to whatever you pick here.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

# Full manage scope is required to POST comments.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def main():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    # access_type=offline + prompt=consent forces Google to return a
    # refresh token (not just a short-lived access token).
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )
    print("\n=================== COPY THIS REFRESH TOKEN ===================\n")
    print(creds.refresh_token)
    print("\n===============================================================")
    print("Paste it as OAUTH_REFRESH_TOKEN when you deploy (README Step 6).")


if __name__ == "__main__":
    main()
