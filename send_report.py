import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def fmt_chg(v):
    if v is None: return "  —   "
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%"

def fmt_val(v, dec=2):
    if v is None: return "—"
    if isinstance(v, (int, float)):
        return f"{v:,.{dec}f}"
    return str(v)

def find_fx_rate(series, target_date_str):
    """Find FX rate from series closest to target date."""
    if not series or not series.get("labels") or not series.get("values"):
        return None
    target = datetime.strptime(target_date_str, "%Y-%m-%d")
    month_map = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                 "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    labels = series["labels"]
    values = series["values"]
    best_idx, best_diff = 0, float("inf")
    for i, lbl in enumerate(labels):
        parts = lbl.split()
        if len(parts) < 2: continue
        m = month_map.get(parts[0])
        y = 2000 + int(parts[1]) if len(parts[1]) == 2 else int(parts[1])
        if not m: continue
        d = datetime(y, m, 15)
        diff = abs((d - target).days)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return values[best_idx] if values else None

# Load data and config
with open("data.json") as f:
    d = json.load(f)

with open("patrimony_config.json") as f:
    cfg = json.load(f)

updated = d.get("updated", "—")
sections = d.get("sections", {})

# Get current FX rates from instruments
def get_inst(sym):
    for sec in sections.values():
        for inst in sec.get("instruments", []):
            if inst.get("symbol") == sym:
                return inst
    return None

chf_inst = get_inst("CHFEUR=X")
usd_inst = get_inst("EURUSD=X")

chf_eur_now = chf_inst.get("raw_current") if chf_inst else None
usd_eur_raw = usd_inst.get("raw_current") if usd_inst else None
usd_eur_now = (1 / usd_eur_raw) if usd_eur_raw else None

# Current patrimony in EUR
if chf_eur_now and usd_eur_now:
    eur_now = cfg["eur"] + (cfg["chf"] * chf_eur_now) + (cfg["usd"] * usd_eur_now)
else:
    eur_now = cfg["eur"]  # fallback

# Historical FX at start date
chf_series = chf_inst.get("series_2y") or chf_inst.get("series_1y") if chf_inst else None
usd_series = usd_inst.get("series_2y") or usd_inst.get("series_1y") if usd_inst else None

chf_eur_then = find_fx_rate(chf_series, cfg["start_date"]) if chf_series else None
usd_eur_then = find_fx_rate(usd_series, cfg["start_date"]) if usd_series else None

if chf_eur_then and usd_eur_then:
    eur_then = cfg["eur"] + (cfg["chf"] * chf_eur_then) + (cfg["usd"] * usd_eur_then)
    delta = eur_now - eur_then
    delta_pct = (delta / eur_then) * 100
else:
    eur_then = delta = delta_pct = None

start_fmt = datetime.strptime(cfg["start_date"], "%Y-%m-%d").strftime("%d %b %Y")

# Build email body
lines = []
lines.append("=" * 58)
lines.append(f"  MARKET REPORT — {updated}")
lines.append("=" * 58)

lines.append("")
lines.append(f"PATRIMONY — since {start_fmt}")
lines.append(f"  EUR {cfg['eur']:>12,}  CHF {cfg['chf']:>12,}  USD {cfg['usd']:>12,}")
lines.append("-" * 44)
lines.append(f"  Current value : € {round(eur_now):,}")
if eur_then:
    lines.append(f"  Start value   : € {round(eur_then):,}  ({start_fmt})")
    sign = "+" if delta >= 0 else ""
    lines.append(f"  Delta         : {sign}€ {round(delta):,}  ({sign}{delta_pct:.2f}%)")
if chf_eur_now:
    lines.append(f"  CHF/EUR now   : {chf_eur_now:.4f}" + (f"  then: {chf_eur_then:.4f}" if chf_eur_then else ""))
if usd_eur_now:
    lines.append(f"  USD/EUR now   : {usd_eur_now:.4f}" + (f"  then: {usd_eur_then:.4f}" if usd_eur_then else ""))

SECTION_TITLES = {
    "fx":      "FX",
    "indices": "GLOBAL INDICES",
    "energy":  "ENERGY & COMMODITIES",
    "crypto":  "METALS & CRYPTO",
    "rates":   "RATES & RISK",
}

for sec_key, title in SECTION_TITLES.items():
    sec = sections.get(sec_key, {})
    instruments = sec.get("instruments", [])
    if not instruments: continue
    lines.append("")
    lines.append(title)
    lines.append("-" * 44)
    for inst in instruments:
        label = inst.get("label", "")
        val   = inst.get("current")
        chg   = inst.get("changes", {}).get("1D")
        dec   = inst.get("decimals", 2)
        val_str = fmt_val(val, dec) if isinstance(val, (int, float)) else str(val) if val else "—"
        lines.append(f"  {label:<22} {val_str:>10}   {fmt_chg(chg)}")
    commentary = sec.get("commentary", "")
    if commentary:
        words = commentary.split()
        line_buf, wrapped = [], []
        for w in words:
            if len(" ".join(line_buf + [w])) > 54:
                wrapped.append("  » " + " ".join(line_buf))
                line_buf = [w]
            else:
                line_buf.append(w)
        if line_buf:
            wrapped.append("  » " + " ".join(line_buf))
        lines.extend(wrapped)

news = d.get("news", [])
if news:
    lines.append("")
    lines.append("HEADLINES")
    lines.append("-" * 44)
    for i, n in enumerate(news[:6], 1):
        lines.append(f"  {i}. {n.get('title','')}")
        if n.get("source"): lines.append(f"     {n['source']}")
        if n.get("link"):   lines.append(f"     {n['link']}")
        lines.append("")

lines.append("=" * 58)
lines.append(f"  Dashboard: https://mskiav.github.io/market-dashboard/")
lines.append("=" * 58)

body = "\n".join(lines)

gmail_user = os.environ["GMAIL_USER"]
gmail_pwd  = os.environ["GMAIL_APP_PASSWORD"]
mail_to    = os.environ["MAIL_TO"]

now_hour = datetime.utcnow().hour
subject_tag = "Morning" if now_hour < 10 else "Afternoon"
subject = f"[Market] {subject_tag} Report — {updated}"

msg = MIMEMultipart()
msg["From"]    = gmail_user
msg["To"]      = mail_to
msg["Subject"] = subject
msg.attach(MIMEText(body, "plain", "utf-8"))

try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_pwd)
        server.sendmail(gmail_user, mail_to, msg.as_string())
    print(f"Email sent to {mail_to}")
except Exception as e:
    print(f"Email error: {e}")
    raise
