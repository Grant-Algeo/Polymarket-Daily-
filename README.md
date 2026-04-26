# 🎯 Polymarket Daily

A lightweight, automated prediction market intelligence pipeline that fetches live data from [Polymarket](https://polymarket.com), scores it for signal quality, generates an AI analysis, delivers a styled daily briefing to your inbox, and logs everything to Google Sheets for historical analysis.

---

## What it does

Every day at 8am UTC, the pipeline:

1. **Fetches live market data** from the Polymarket Gamma API across six categories — top volume, fastest growing, sports, geopolitics, culture, and finance
2. **Extracts named outcomes** for every market (e.g. individual candidates in an election, not just a generic YES/NO price)
3. **Scores markets** using a composite signal model combining momentum and uncertainty
4. **Logs every market** to a Google Sheet — one row per market per day — building a compounding time-series dataset
5. **Calls Claude** (Anthropic's AI) to generate a morning briefing — market of the day, key themes, category highlights, watch list, and a contrarian take
6. **Emails the full report** as a styled HTML digest

---

## Signal model

The core analytical layer scores every market using:

```
momentum    = volume_24h / volume_all
uncertainty = 1 - |top_outcome_probability - 0.5| / 0.5
signal      = momentum × uncertainty
```

**Momentum** identifies markets where a disproportionate share of all-time volume has traded in the last 24 hours — something is driving fresh attention right now.

**Uncertainty** discounts near-certain markets and amplifies genuinely contested ones. A market at 50/50 with surging volume is more informationally interesting than a 95% certainty still trading.

**Signal score** combines both — high score means money is moving fast into a market where the outcome is still genuinely open.

---

## Data logging

Every daily run appends a new set of rows to a Google Sheet with the following columns:

| Column | Description |
|---|---|
| Date | UTC date of the snapshot |
| Category | Top Volume / Trending / Sports / Geopolitics / Culture / Finance |
| Title | Full market name |
| Top Outcome | Most probable named outcome |
| Top Outcome % | Implied probability |
| 2nd Outcome | Second most probable outcome |
| 2nd Outcome % | Implied probability |
| Volume 24h | 24-hour trading volume (USD) |
| Volume All-time | Cumulative trading volume (USD) |
| Liquidity | Current liquidity (USD) |
| Momentum Score | 24h vol / all-time vol × 100 |
| Uncertainty Score | Distance from 50/50 × 100 |
| Signal Score | Momentum × Uncertainty |
| Resolve Date | Market resolution date |
| URL | Direct Polymarket link |

After 90 days this becomes a genuine time-series dataset — useful for backtesting the signal model, identifying category trends, and building leading indicator research.

---

## Stack

| Component | Tool |
|---|---|
| Data source | Polymarket Gamma API (public, no auth required) |
| Analysis | Anthropic Claude API (claude-sonnet-4-5) |
| Scheduler | GitHub Actions (cron) |
| Data logging | Google Sheets API (service account) |
| Delivery | Gmail SMTP |
| Language | Python 3.11 |

---

## Repo structure

```
polymarket-daily/
├── .github/
│   └── workflows/
│       └── daily.yml        # Scheduler — runs at 8am UTC daily
├── polymarket_fetch.py      # API ingestion, parsing, signal scoring
├── sheets_logger.py         # Google Sheets logging module
└── send_summary.py          # Claude analysis + email generation
```

---

## Setup

### Prerequisites
- GitHub account
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Gmail account with App Password enabled (requires 2-Step Verification)
- Google Cloud project with Sheets API enabled and a service account

### GitHub Secrets

Add the following as repository secrets (`Settings → Secrets and variables → Actions`):

| Secret | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GMAIL_ADDRESS_ALGGRA` | Gmail address used to send the email |
| `GMAIL_PASSWORD_ALGGRA` | Gmail App Password (16 characters, no spaces) |
| `RECIPIENT_EMAIL` | Address to receive the daily briefing |
| `GOOGLE_SHEET_ID` | ID from your Google Sheet URL |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Base64-encoded service account JSON key |

### Google Sheets setup

1. Create a new Google Sheet and copy the ID from the URL
2. In Google Cloud Console — create a project, enable the Sheets API, create a service account
3. Download the service account JSON key
4. Share the Google Sheet with the service account email (Editor access)
5. Base64 encode the JSON key and add as `GOOGLE_SERVICE_ACCOUNT_JSON` secret:
```powershell
# Windows PowerShell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("path\to\key.json")) | Out-File -FilePath "encoded.txt" -NoNewline
```

### Running manually

Go to `Actions → Polymarket Daily Summary → Run workflow` to trigger immediately.

---

## Cost

| Service | Cost |
|---|---|
| Polymarket API | Free |
| Claude API | ~$0.01–0.02 per run |
| GitHub Actions | Free tier |
| Google Sheets API | Free tier |
| **Total** | **Under £0.50/month** |

---

## Categories tracked

| Category | Coverage |
|---|---|
| 🔥 Top Volume | Highest all-time cumulative trading volume |
| 🚀 Fastest Growing | Largest 24hr volume spike |
| ⚽ Sports | All major sports — esports excluded |
| 🌍 Geopolitics | Wars, elections, international relations |
| 🎭 Culture | Awards, entertainment, celebrity, media |
| 💹 Finance | Fed decisions, economic indicators, earnings |

---

## Roadmap

- [x] Live market data ingestion
- [x] Named outcome extraction
- [x] Momentum × uncertainty signal model
- [x] AI-written morning briefing
- [x] Styled HTML email delivery
- [x] Google Sheets time-series logging
- [ ] Signal model backtesting
- [ ] Price history charts via CLOB API
- [ ] Week-on-week trend analysis
- [ ] Slack/Discord delivery option

---

*Data: [gamma-api.polymarket.com](https://gamma-api.polymarket.com) · Analysis: Claude Sonnet · Not financial advice*
