# 🎯 Polymarket Daily

A lightweight, automated prediction market intelligence pipeline that fetches live data from [Polymarket](https://polymarket.com), scores it for signal quality, generates an AI analysis, and delivers a styled daily briefing to your inbox every morning.

---

## What it does

Every day at 8am UTC, the pipeline:

1. **Fetches live market data** from the Polymarket Gamma API across six categories — top volume, fastest growing, sports, geopolitics, culture, and finance
2. **Extracts named outcomes** for every market (e.g. individual candidates in an election, not just a generic YES/NO price)
3. **Scores markets** using a composite signal model combining momentum and uncertainty
4. **Calls Claude** (Anthropic's AI) to generate a morning briefing — market of the day, key themes, category highlights, watch list, and a contrarian take
5. **Emails the full report** as a styled HTML digest

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

## Stack

| Component | Tool |
|---|---|
| Data source | Polymarket Gamma API (public, no auth required) |
| Analysis | Anthropic Claude API (claude-sonnet-4-5) |
| Scheduler | GitHub Actions (cron) |
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
└── send_summary.py          # Claude analysis + email generation
```

---

## Setup

### Prerequisites
- GitHub account
- Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- Gmail account with App Password enabled (requires 2-Step Verification)

### Configuration

Add the following as GitHub repository secrets (`Settings → Secrets and variables → Actions`):

| Secret | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GMAIL_ADDRESS_ALGGRA` | Gmail address used to send the email |
| `GMAIL_PASSWORD_ALGGRA` | Gmail App Password (16 characters, no spaces) |
| `RECIPIENT_EMAIL` | Address to receive the daily briefing |

### Running manually

Go to `Actions → Polymarket Daily Summary → Run workflow` to trigger immediately without waiting for the scheduled run.

---

## Cost

- **Polymarket API**: Free, no key required
- **Claude API**: ~$0.01–0.02 per run (pay-per-use, no subscription)
- **GitHub Actions**: Free tier covers this comfortably
- **Total**: Under £0.50/month

---

## Categories tracked

| Category | Coverage |
|---|---|
| 🔥 Top Volume | Highest all-time cumulative trading volume across all markets |
| 🚀 Fastest Growing | Largest 24hr volume spike — what the crowd is piling into right now |
| ⚽ Sports | All major sports (football, tennis, NBA, NFL, cricket, etc.) — esports excluded |
| 🌍 Geopolitics | Wars, elections, international relations, treaties |
| 🎭 Culture | Awards, entertainment, celebrity, media |
| 💹 Finance | Fed decisions, economic indicators, company earnings |

---

## Roadmap

- [ ] Google Sheets export for historical logging
- [ ] Price history charts via CLOB API
- [ ] Week-on-week signal comparison
- [ ] Configurable category selection
- [ ] Slack/Discord delivery option

---

*Data: [gamma-api.polymarket.com](https://gamma-api.polymarket.com) · Analysis: Claude Sonnet · Not financial advice*
