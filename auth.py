"""
Step 1 — Secure login.

Google Ads has no password-based API login: this runs the official OAuth2
"installed app" flow. A browser tab opens, YOU log in to Google directly on
Google's own page (this script never sees your password), and Google hands
back a refresh token which is saved locally in google-ads.yaml.

Usage:
    python auth.py
"""
import sys
import yaml
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    sys.exit(
        "Missing dependency. Run: pip install google-auth-oauthlib --break-system-packages"
    )

CONFIG_PATH = Path("google-ads.yaml")
SCOPES = ["https://www.googleapis.com/auth/adwords"]


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit(
            "google-ads.yaml not found. Copy config.example.yaml to google-ads.yaml "
            "and fill in developer_token / client_id / client_secret first."
        )
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def save_refresh_token(config: dict, refresh_token: str) -> None:
    config["refresh_token"] = refresh_token
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)
    print(f"Refresh token saved to {CONFIG_PATH}. Keep this file private (chmod 600).")


def main():
    config = load_config()
    if not config.get("client_id") or "YOUR_OAUTH_CLIENT_ID" in config.get("client_id", ""):
        sys.exit("Set client_id and client_secret in google-ads.yaml before running auth.")

    client_config = {
        "installed": {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    print("Opening browser for Google login and consent...")
    credentials = flow.run_local_server(port=0)

    save_refresh_token(config, credentials.refresh_token)
    print("Login complete. You can now run: python main.py analyze --customer-id <id>")


if __name__ == "__main__":
    main()
