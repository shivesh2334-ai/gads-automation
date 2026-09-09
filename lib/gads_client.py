"""
Authenticated Google Ads client + GAQL query helper.

Credentials resolution order:
  1. Environment variables (used on Vercel — set these in Project Settings > Environment Variables):
       GOOGLE_ADS_DEVELOPER_TOKEN
       GOOGLE_ADS_CLIENT_ID
       GOOGLE_ADS_CLIENT_SECRET
       GOOGLE_ADS_REFRESH_TOKEN
       GOOGLE_ADS_LOGIN_CUSTOMER_ID   (optional, manager account id)
  2. Local google-ads.yaml file (used by the CLI scripts / auth.py during local dev)

The refresh token itself is always generated locally (python auth.py) — Vercel's
serverless functions can't run the interactive OAuth consent flow, so that step
stays a one-time thing you do on your own machine, then paste the resulting
refresh token into Vercel's encrypted environment variables.
"""
import os
import sys
from pathlib import Path

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
except ImportError:
    sys.exit("Missing dependency. Run: pip install google-ads --break-system-packages")

CONFIG_PATH = Path("google-ads.yaml")

ENV_KEYS = {
    "developer_token": "GOOGLE_ADS_DEVELOPER_TOKEN",
    "client_id": "GOOGLE_ADS_CLIENT_ID",
    "client_secret": "GOOGLE_ADS_CLIENT_SECRET",
    "refresh_token": "GOOGLE_ADS_REFRESH_TOKEN",
    "login_customer_id": "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
}


def _config_from_env() -> dict | None:
    developer_token = os.environ.get(ENV_KEYS["developer_token"])
    client_id = os.environ.get(ENV_KEYS["client_id"])
    client_secret = os.environ.get(ENV_KEYS["client_secret"])
    refresh_token = os.environ.get(ENV_KEYS["refresh_token"])
    if not all([developer_token, client_id, client_secret, refresh_token]):
        return None
    config = {
        "developer_token": developer_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    }
    login_customer_id = os.environ.get(ENV_KEYS["login_customer_id"])
    if login_customer_id:
        config["login_customer_id"] = login_customer_id
    return config


def get_client() -> "GoogleAdsClient":
    env_config = _config_from_env()
    if env_config:
        return GoogleAdsClient.load_from_dict(env_config)

    if not CONFIG_PATH.exists():
        sys.exit(
            "No credentials found. Either set the GOOGLE_ADS_* environment variables "
            "(for Vercel) or create google-ads.yaml locally (see README, `python auth.py`)."
        )
    try:
        return GoogleAdsClient.load_from_storage(str(CONFIG_PATH))
    except Exception as e:
        sys.exit(f"Failed to load Google Ads credentials from google-ads.yaml: {e}")


def run_query(client: "GoogleAdsClient", customer_id: str, query: str) -> list:
    """Run a GAQL query and return rows as a plain list (proto-plus objects)."""
    customer_id = customer_id.replace("-", "")
    ga_service = client.get_service("GoogleAdsService")
    try:
        response = ga_service.search_stream(customer_id=customer_id, query=query)
        rows = []
        for batch in response:
            rows.extend(batch.results)
        return rows
    except GoogleAdsException as ex:
        errors = "; ".join(e.message for e in ex.failure.errors)
        raise RuntimeError(f"Google Ads API error (request id {ex.request_id}): {errors}")
