import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import anthropic

from polymarket_fetch import fetch_all, build_data_summary, fmt_usd, format_outcomes

# ─── CONFIG ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
GMAIL_ADDRESS      = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
RECIPIENT          = GMAIL_ADDRESS  # sends to yourself; change if needed


# ─── STEP 1: FETCH DATA ──────────────────────────────────────────────────────
print("Fetching Polymarket data...")
data = fetch_all()
data_summary = build_data_summary(data)
print("Data fetched.")


# ─── STEP 2: CALL CLAUDE FOR ANALYSIS ────────────────────────────────────────
print("Calling Claude for analysis...")

SYSTEM_PROMPT = """You are a sharp, concise analyst who reads prediction market data 
and extracts genuine insight. You write in plain English — no fluff, no filler. 
You think like a trader and a journalist at once: what does this data actually mean, 
what is the crowd pricing in, and what should a smart reader pay attention to today."""

USER_PROMPT = f"""Here is today's Polymarket data snapshot:

{data_summary}

Please provide a morning briefing with the following structure:

1. MARKET OF THE DAY
   The single most interesting signal from the data. Explain what's moving, 
   why the momentum and uncertainty combination makes it worth watching, 
   and what outcome the crowd is currently pricing in.

2. KEY THEMES
   2-3 sentences on the broader narrative across today's top markets. 
   Are there connections between categories? Any contradictions worth noting?

3. CATEGORY HIGHLIGHTS
   One sentence per category (Sports, Geopolitics, Culture, Finance) 
   on the most notable market in each.

4. WATCH LIST
   2-3 markets from the signal feed that aren't already covered above 
   but deserve attention today. Brief explanation for each.

5. ONE CONTRARIAN TAKE
   Pick one market where the crowd's implied probability seems off 
   or where you'd push back on the consensus. Say why.

Keep the whole thing under 500 words. Be direct and specific — 
reference actual market names and probabilities from the data."""

client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
message  = client.messages.create(
    model      = "claude-sonnet-4-20250514",
    max_tokens = 1000,
    messages   = [{"role": "user", "content": USER_PROMPT}],
    system     = SYSTEM_PROMPT,
)
analysis = message.content[0].text
print("Analysis complete.")


# ─── STEP 3: BUILD EMAIL ─────────────────────────────────────────────────────

def fmt_event_block(event, vol_key="volume_24h"):
    vol   = event[vol_key]
    lines = [
        f"<b>{event['title']}</b>",
        f"Volume: {fmt_usd(vol)} &nbsp;|&nbsp; Liquidity: {fmt_usd(event['liquidity'])} &nbsp;|&nbsp; Resolves: {event['end_date']}",
    ]
    if event["outcomes"]:
        outcome_lines = []
        for label, prob in event["outcomes"][:5]:
            bar_len  = int(prob / 5)
            bar_html = (
                f'<span style="color:#2563eb;">{"█" * bar_len}</span>'
                f'<span style="color:#e5e7eb;">{"█" * (20 - bar_len)}</span>'
            )
            outcome_lines.append(
                f'<span style="font-family:monospace;">{label[:30]:<30} {bar_html} {prob:5.1f}%</span>'
            )
        lines.append("<br>".join(outcome_lines))
    lines.append(f'<a href="{event["url"]}" style="color:#6366f1;">View on Polymarket →</a>')
    return "<br>".join(lines)


def section_html(title, events, vol_key="volume_24h"):
    rows = ""
    for i, e in enumerate(events, 1):
        rows += f"""
        <tr>
          <td style="padding:4px 8px;color:#6b7280;font-weight:bold;">#{i}</td>
          <td style="padding:4px 8px;">{fmt_event_block(e, vol_key)}</td>
        </tr>
        <tr><td colspan="2"><hr style="border:none;border-top:1px solid #f3f4f6;margin:4px 0;"></td></tr>
        """
    return f"""
    <h3 style="color:#1e293b;border-left:3px solid #6366f1;padding-left:10px;margin-top:24px;">{title}</h3>
    <table style="width:100%;border-collapse:collapse;">{rows}</table>
    """


def signal_row_html(event, cat, rank):
    score = event["signal_score"] * 100
    mom   = event["momentum"] * 100
    unc   = event["uncertainty"] * 100
    top_outcome = f"{event['outcomes'][0][0]}: {event['outcomes'][0][1]:.1f}%" if event["outcomes"] else "N/A"
    return f"""
    <tr style="background:{'#f8fafc' if rank % 2 == 0 else 'white'};">
      <td style="padding:6px 8px;color:#6b7280;font-weight:bold;">#{rank}</td>
      <td style="padding:6px 8px;">
        <b>{event['title']}</b><br>
        <span style="color:#6b7280;font-size:12px;">{cat}</span>
      </td>
      <td style="padding:6px 8px;text-align:center;">
        <span style="background:#ede9fe;color:#6d28d9;padding:2px 8px;border-radius:12px;font-size:12px;">
          {score:.1f}
        </span>
      </td>
      <td style="padding:6px 8px;font-size:12px;color:#6b7280;">
        Mom: {mom:.1f}%<br>Unc: {unc:.1f}%
      </td>
      <td style="padding:6px 8px;font-size:12px;">{top_outcome}</td>
    </tr>
    """


signal_rows = "".join(
    signal_row_html(e, cat, i)
    for i, (e, cat) in enumerate(data["signal_ranked"], 1)
)

analysis_html = analysis.replace("\n", "<br>").replace("**", "")

html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:700px;margin:0 auto;padding:20px;color:#1e293b;background:#ffffff;">

  <!-- HEADER -->
  <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);
              padding:24px;border-radius:12px;margin-bottom:24px;">
    <h1 style="color:white;margin:0;font-size:22px;">🎯 Polymarket Daily</h1>
    <p style="color:#e0e7ff;margin:4px 0 0;">{data['timestamp']}</p>
  </div>

  <!-- CLAUDE ANALYSIS -->
  <div style="background:#f8fafc;border:1px solid #e2e8f0;
              border-radius:10px;padding:20px;margin-bottom:24px;">
    <h2 style="margin-top:0;color:#1e293b;font-size:16px;">
      ✦ Morning Analysis
    </h2>
    <div style="line-height:1.7;color:#334155;">
      {analysis_html}
    </div>
  </div>

  <!-- CATEGORY SECTIONS -->
  {section_html("🔥 Top 3 by Total Volume",        data["top_volume"], "volume_all")}
  {section_html("🚀 Fastest Growing (24hr)",        data["fastest"],    "volume_24h")}
  {section_html("⚽ Sports",                        data["sports"],     "volume_24h")}
  {section_html("🌍 Geopolitics",                   data["geo"],        "volume_24h")}
  {section_html("🎭 Culture",                       data["culture"],    "volume_24h")}
  {section_html("💹 Finance",                       data["finance"],    "volume_24h")}

  <!-- SIGNAL FEED -->
  <h3 style="color:#1e293b;border-left:3px solid #6366f1;
             padding-left:10px;margin-top:24px;">
    ⚡ Signal Feed — Momentum × Uncertainty
  </h3>
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="background:#f1f5f9;color:#64748b;">
        <th style="padding:8px;">#</th>
        <th style="padding:8px;text-align:left;">Market</th>
        <th style="padding:8px;">Score</th>
        <th style="padding:8px;">Metrics</th>
        <th style="padding:8px;text-align:left;">Top Outcome</th>
      </tr>
    </thead>
    <tbody>{signal_rows}</tbody>
  </table>

  <!-- FOOTER -->
  <div style="margin-top:32px;padding-top:16px;border-top:1px solid #e2e8f0;
              color:#94a3b8;font-size:12px;text-align:center;">
    Data: gamma-api.polymarket.com &nbsp;·&nbsp;
    Analysis: Claude Sonnet &nbsp;·&nbsp;
    Not financial advice
  </div>

</body>
</html>
"""


# ─── STEP 4: SEND EMAIL ───────────────────────────────────────────────────────
print("Sending email...")

date_str = datetime.utcnow().strftime("%a %d %b")
msg = MIMEMultipart("alternative")
msg["Subject"] = f"🎯 Polymarket Daily — {date_str}"
msg["From"]    = GMAIL_ADDRESS
msg["To"]      = RECIPIENT
msg.attach(MIMEText(html_body, "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    server.sendmail(GMAIL_ADDRESS, RECIPIENT, msg.as_string())

print(f"Email sent to {RECIPIENT}.")
