"""
One-time script to obtain a Google OAuth2 refresh token for Search Console.

Usage:
    python scripts/get_gsc_refresh_token.py \
        --client-id YOUR_CLIENT_ID \
        --client-secret YOUR_CLIENT_SECRET

The script will open a browser, ask you to sign in with the Google account
that already has Search Console access for https://www.lcpsych.com, and then
print the refresh token to the terminal.

Copy the refresh token into .env:
    GSC_OAUTH_CLIENT_ID=...
    GSC_OAUTH_CLIENT_SECRET=...
    GSC_OAUTH_REFRESH_TOKEN=...
"""

import argparse
import json
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
REDIRECT_URI = "http://localhost:8765"

_auth_code: str | None = None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _auth_code
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _auth_code = params.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Authorization complete. You can close this tab.</h2>")

    def log_message(self, *args):
        pass  # suppress request logs


def main():
    parser = argparse.ArgumentParser(description="Get GSC OAuth2 refresh token")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    args = parser.parse_args()

    params = urllib.parse.urlencode({
        "client_id": args.client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    })
    url = f"{AUTH_URL}?{params}"
    print(f"\nOpening browser for authorization...\n{url}\n")
    webbrowser.open(url)

    server = HTTPServer(("localhost", 8765), _Handler)
    server.handle_request()

    if not _auth_code:
        print("ERROR: No authorization code received.")
        return

    body = urllib.parse.urlencode({
        "code": _auth_code,
        "client_id": args.client_id,
        "client_secret": args.client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()

    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    refresh_token = data.get("refresh_token")
    if not refresh_token:
        print(f"ERROR: No refresh token in response: {data}")
        return

    print("\n--- Add these to your .env ---")
    print(f"GSC_OAUTH_CLIENT_ID={args.client_id}")
    print(f"GSC_OAUTH_CLIENT_SECRET={args.client_secret}")
    print(f"GSC_OAUTH_REFRESH_TOKEN={refresh_token}")


if __name__ == "__main__":
    main()
