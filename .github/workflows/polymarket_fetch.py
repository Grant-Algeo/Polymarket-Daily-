import requests
import json
from datetime import datetime

BASE_URL = "https://gamma-api.polymarket.com"

TAG_IDS = {
    "sports":      100639,
    "geopolitics": 100265,
    "culture":     596,
    "finance":     120,
}

ESPORTS_EXCLUDE = {
    "esports", "dota 2", "dota2", "cs:go", "csgo", "counter-strike",
    "league of legends", "valorant", "overwatch", "rocket league",
    "fortnite", "pubg", "starcraft", "hearthstone", "call of duty",
    "apex legends", "rainbow six", "mobile legends", "king of glory",
}

HEADERS = {"Accept": "application/json"}


def fetch_events(tag_id=None, order="volume", limit=25):
    params = {
        "limit":     limit,
        "closed":    "false",
        "order":     order,
        "ascending": "false",
        "active":    "true",
    }
    if tag_id:
        params["tag_id"]       = tag_id
        params["related_tags"] = "true"
    resp = requests.get(f"{BASE_URL}/events", params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


def parse_event(event):
    markets = event.get("markets", [])
    outcomes = []

    for m in markets:
        question     = m.get("groupItemTitle") or m.get("question") or m.get("title") or ""
        prices_raw   = m.get("outcomePrices", "[]")
        outcomes_raw = m.get("outcomes", "[]")
        try:
            prices         = json.loads(prices_raw)   if isinstance(prices_raw, str)   else prices_raw
            outcome_labels = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
        except (json.JSONDecodeError, ValueError):
            prices, outcome_labels = [], []

        if question and len(outcome_labels) == 2 and outcome_labels[0].lower() == "yes":
            try:
                outcomes.append((question, float(prices[0]) * 100))
            except (IndexError, ValueError):
                pass
        elif outcome_labels and prices:
            for label, price in zip(outcome_labels, prices):
                try:
                    outcomes.append((label, float(price) * 100))
                except ValueError:
                    pass
            break

    outcomes = sorted(outcomes, key=lambda x: x[1], reverse=True)

    return {
        "title":      event.get("title") or event.get("question", "Untitled"),
        "outcomes":   outcomes,
        "volume_24h": float(event.get("volume24hr") or 0),
        "volume_all": float(event.get("volume") or 0),
        "liquidity":  float(event.get("liquidity") or 0),
        "end_date":   (event.get("endDate") or event.get("startDate", ""))[:10],
        "tags":       [t.get("label", "") for t in event.get("tags", []) if t.get("label")],
        "url":        f"https://polymarket.com/event/{event.get('slug', '')}",
    }


def is_esports(event, raw):
    tags_lower = {t.lower() for t in event["tags"]}
    if tags_lower & ESPORTS_EXCLUDE:
        return True
    title_lower = (raw.get("title") or "").lower()
    return any(term in title_lower for term in ESPORTS_EXCLUDE)


def compute_signal(event):
    vol_all  = event["volume_all"]
    vol_24h  = event["volume_24h"]
    momentum = vol_24h / vol_all if vol_all > 0 else 0

    if event["outcomes"]:
        top_prob    = event["outcomes"][0][1] / 100
        uncertainty = 1 - abs(top_prob - 0.5) / 0.5
    else:
        uncertainty = 0.5

    return {
        **event,
        "momentum":     momentum,
        "uncertainty":  uncertainty,
        "signal_score": momentum * uncertainty,
    }


def fmt_usd(val):
    if val >= 1_000_000:
        return f"${val/1_000_000:.1f}M"
    elif val >= 1_000:
        return f"${val/1_000:.1f}K"
    return f"${val:.2f}"


def fetch_all():
    """
    Fetches all categories and returns a structured dict ready
    for both the email template and the Claude prompt.
    """
    # Category fetches
    raw_volume  = fetch_events(order="volume",    limit=10)
    raw_fastest = fetch_events(order="volume24hr", limit=10)
    raw_sports  = fetch_events(tag_id=TAG_IDS["sports"],      order="volume24hr", limit=25)
    raw_geo     = fetch_events(tag_id=TAG_IDS["geopolitics"], order="volume24hr", limit=10)
    raw_culture = fetch_events(tag_id=TAG_IDS["culture"],     order="volume24hr", limit=10)
    raw_finance = fetch_events(tag_id=TAG_IDS["finance"],     order="volume24hr", limit=10)

    top_volume = sorted([parse_event(e) for e in raw_volume],  key=lambda x: x["volume_all"], reverse=True)
    fastest    = sorted([parse_event(e) for e in raw_fastest], key=lambda x: x["volume_24h"], reverse=True)

    sports_parsed = [(parse_event(e), e) for e in raw_sports]
    sports        = sorted([p for p, r in sports_parsed if not is_esports(p, r)],
                           key=lambda x: x["volume_24h"], reverse=True)

    geo     = sorted([parse_event(e) for e in raw_geo],     key=lambda x: x["volume_24h"], reverse=True)
    culture = sorted([parse_event(e) for e in raw_culture], key=lambda x: x["volume_24h"], reverse=True)
    finance = sorted([parse_event(e) for e in raw_finance], key=lambda x: x["volume_24h"], reverse=True)

    # Deduplicated signal pool
    all_raw = (
        [(e, "Sports")      for e in sports]    +
        [(e, "Geopolitics") for e in geo]       +
        [(e, "Culture")     for e in culture]   +
        [(e, "Finance")     for e in finance]   +
        [(e, "Top Volume")  for e in top_volume]+
        [(e, "Trending")    for e in fastest]
    )
    seen, unique = set(), []
    for e, cat in all_raw:
        if e["title"] not in seen:
            seen.add(e["title"])
            unique.append((e, cat))

    signal_ranked = sorted(
        [(compute_signal(e), cat) for e, cat in unique],
        key=lambda x: x[0]["signal_score"],
        reverse=True
    )

    return {
        "timestamp":      datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "top_volume":     top_volume[:3],
        "fastest":        fastest[:3],
        "sports":         sports[:3],
        "geo":            geo[:3],
        "culture":        culture[:3],
        "finance":        finance[:3],
        "signal_ranked":  signal_ranked[:10],
    }


def format_outcomes(outcomes, limit=5):
    """Returns a plain text summary of outcomes for prompts and emails."""
    lines = []
    for label, prob in outcomes[:limit]:
        lines.append(f"    {label}: {prob:.1f}%")
    if len(outcomes) > limit:
        lines.append(f"    ... +{len(outcomes) - limit} more")
    return "\n".join(lines)


def build_data_summary(data):
    """
    Builds the structured plain-text data block passed to Claude.
    Keeps it tight — Claude doesn't need formatting, just clean facts.
    """
    lines = [f"POLYMARKET DATA SNAPSHOT — {data['timestamp']}\n"]

    sections = [
        ("TOP 3 BY TOTAL VOLUME",        data["top_volume"], "volume_all"),
        ("TOP 3 FASTEST GROWING (24hr)", data["fastest"],    "volume_24h"),
        ("TOP 3 SPORTS",                 data["sports"],     "volume_24h"),
        ("TOP 3 GEOPOLITICS",            data["geo"],        "volume_24h"),
        ("TOP 3 CULTURE",                data["culture"],    "volume_24h"),
        ("TOP 3 FINANCE",                data["finance"],    "volume_24h"),
    ]

    for section_title, events, vol_key in sections:
        lines.append(f"\n{section_title}")
        lines.append("-" * 40)
        for i, e in enumerate(events, 1):
            vol = e[vol_key]
            lines.append(f"{i}. {e['title']}")
            lines.append(f"   Volume: {fmt_usd(vol)} | Liquidity: {fmt_usd(e['liquidity'])} | Resolves: {e['end_date']}")
            if e["outcomes"]:
                lines.append(format_outcomes(e["outcomes"]))
            lines.append(f"   {e['url']}")

    lines.append(f"\nTOP 10 SIGNAL FEED (momentum x uncertainty)")
    lines.append("-" * 40)
    for i, (e, cat) in enumerate(data["signal_ranked"], 1):
        lines.append(f"{i}. [{cat}] {e['title']}")
        lines.append(f"   Signal: {e['signal_score']*100:.1f} | Momentum: {e['momentum']*100:.1f}% | Uncertainty: {e['uncertainty']*100:.1f}%")
        lines.append(f"   24h Vol: {fmt_usd(e['volume_24h'])} | Total: {fmt_usd(e['volume_all'])}")
        if e["outcomes"]:
            lines.append(format_outcomes(e["outcomes"], limit=3))

    return "\n".join(lines)
