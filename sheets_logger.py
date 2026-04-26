import os
import json
import base64
import datetime
import requests

# ─── GOOGLE SHEETS CONFIG ────────────────────────────────────────────────────
SHEETS_SCOPE    = "https://www.googleapis.com/auth/spreadsheets"
SHEETS_API_BASE = "https://sheets.googleapis.com/v4/spreadsheets"

SHEET_HEADERS = [
    "Date",
    "Category",
    "Title",
    "Top Outcome",
    "Top Outcome %",
    "2nd Outcome",
    "2nd Outcome %",
    "Volume 24h (USD)",
    "Volume All-time (USD)",
    "Liquidity (USD)",
    "Momentum Score",
    "Uncertainty Score",
    "Signal Score",
    "Resolve Date",
    "URL",
]


def get_access_token(service_account_json: dict) -> str:
    """
    Exchange a service account JSON key for a short-lived OAuth2 access token
    using Google's JWT flow — no external libraries needed.
    """
    import time
    import hmac
    import hashlib
    import struct

    def base64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    now = int(time.time())
    header  = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss":   service_account_json["client_email"],
        "scope": SHEETS_SCOPE,
        "aud":   "https://oauth2.googleapis.com/token",
        "iat":   now,
        "exp":   now + 3600,
    }

    h = base64url(json.dumps(header).encode())
    p = base64url(json.dumps(payload).encode())
    signing_input = f"{h}.{p}".encode()

    # Sign with RSA-SHA256 using the private key
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    private_key = serialization.load_pem_private_key(
        service_account_json["private_key"].encode(),
        password=None
    )
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    jwt = f"{h}.{p}.{base64url(signature)}"

    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion":  jwt,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def ensure_headers(spreadsheet_id: str, token: str):
    """
    Check if the Daily Log sheet has headers. If the sheet is empty, write them.
    Creates the 'Daily Log' sheet tab if it doesn't exist.
    """
    headers_auth = {"Authorization": f"Bearer {token}"}

    # First check if 'Daily Log' sheet exists — create it if not
    meta = requests.get(
        f"{SHEETS_API_BASE}/{spreadsheet_id}",
        headers=headers_auth,
        timeout=10
    ).json()

    sheet_names = [s["properties"]["title"] for s in meta.get("sheets", [])]

    if "Daily Log" not in sheet_names:
        requests.post(
            f"{SHEETS_API_BASE}/{spreadsheet_id}:batchUpdate",
            headers={**headers_auth, "Content-Type": "application/json"},
            json={"requests": [{"addSheet": {"properties": {"title": "Daily Log"}}}]},
            timeout=10,
        )
        print("Created 'Daily Log' sheet tab.")

    # Check if headers row exists
    resp = requests.get(
        f"{SHEETS_API_BASE}/{spreadsheet_id}/values/Daily Log!A1:Z1",
        headers=headers_auth,
        timeout=10,
    ).json()

    existing = resp.get("values", [])
    if not existing:
        # Write headers
        requests.put(
            f"{SHEETS_API_BASE}/{spreadsheet_id}/values/Daily Log!A1",
            headers={**headers_auth, "Content-Type": "application/json"},
            params={"valueInputOption": "RAW"},
            json={"values": [SHEET_HEADERS]},
            timeout=10,
        )
        print("Written headers to Daily Log.")


def build_rows(data: dict, today: str) -> list:
    """
    Convert the full data snapshot into a flat list of rows — one per market.
    Deduplicates by title so the same market doesn't appear twice.
    """
    rows = []
    seen = set()

    sections = [
        ("Top Volume",   data["top_volume"],    "volume_all"),
        ("Trending",     data["fastest"],        "volume_24h"),
        ("Sports",       data["sports"],         "volume_24h"),
        ("Geopolitics",  data["geo"],            "volume_24h"),
        ("Culture",      data["culture"],        "volume_24h"),
        ("Finance",      data["finance"],        "volume_24h"),
    ]

    # Build a signal score lookup from the signal feed
    signal_lookup = {}
    for event, cat in data["signal_ranked"]:
        signal_lookup[event["title"]] = event

    for category, events, _ in sections:
        for e in events:
            if e["title"] in seen:
                continue
            seen.add(e["title"])

            # Outcomes
            top_label   = e["outcomes"][0][0] if len(e["outcomes"]) > 0 else ""
            top_prob    = round(e["outcomes"][0][1], 2) if len(e["outcomes"]) > 0 else ""
            sec_label   = e["outcomes"][1][0] if len(e["outcomes"]) > 1 else ""
            sec_prob    = round(e["outcomes"][1][1], 2) if len(e["outcomes"]) > 1 else ""

            # Signal scores — from signal_ranked if available
            sig = signal_lookup.get(e["title"])
            momentum    = round(sig["momentum"] * 100, 2)    if sig else ""
            uncertainty = round(sig["uncertainty"] * 100, 2) if sig else ""
            signal      = round(sig["signal_score"] * 100, 2) if sig else ""

            rows.append([
                today,
                category,
                e["title"],
                top_label,
                top_prob,
                sec_label,
                sec_prob,
                round(e["volume_24h"], 2),
                round(e["volume_all"], 2),
                round(e["liquidity"], 2),
                momentum,
                uncertainty,
                signal,
                e["end_date"],
                e["url"],
            ])

    return rows


def append_to_sheet(spreadsheet_id: str, rows: list, token: str):
    """Append rows to the Daily Log sheet."""
    if not rows:
        print("No rows to append.")
        return

    resp = requests.post(
        f"{SHEETS_API_BASE}/{spreadsheet_id}/values/Daily Log!A1:append",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        params={
            "valueInputOption": "RAW",
            "insertDataOption": "INSERT_ROWS",
        },
        json={"values": rows},
        timeout=15,
    )
    resp.raise_for_status()
    updates = resp.json().get("updates", {})
    print(f"Logged {updates.get('updatedRows', len(rows))} rows to Google Sheets.")


def log_to_sheets(data: dict):
    """
    Main entry point — called from send_summary.py after data is fetched.
    Reads credentials and spreadsheet ID from environment variables.
    """
    spreadsheet_id      = os.environ.get("GOOGLE_SHEET_ID")
    service_account_b64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")

    if not spreadsheet_id or not service_account_b64:
        print("Sheets logging skipped — GOOGLE_SHEET_ID or GOOGLE_SERVICE_ACCOUNT_JSON not set.")
        return

    try:
        service_account_json = json.loads(
            base64.b64decode(service_account_b64).decode("utf-8")
        )
        token  = get_access_token(service_account_json)
        today  = datetime.datetime.utcnow().strftime("%Y-%m-%d")

        ensure_headers(spreadsheet_id, token)
        rows = build_rows(data, today)
        append_to_sheet(spreadsheet_id, rows, token)

    except Exception as e:
        # Never let Sheets logging break the email send
        print(f"Sheets logging error (non-fatal): {e}")
