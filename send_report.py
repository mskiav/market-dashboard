import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def fmt_chg(v, width=8):
    if v is None: return " " * width
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.2f}%".rjust(width)

def fmt_val(v, dec=2):
    if v is None: return "—"
    if isinstance(v, (int, float)):
        return f"{v:,.{dec}f}"
    return str(v)

def avg_chg(instruments, period):
    vals = [i.get("changes",{}).get(period) for i in instruments if i.get("changes",{}).get(period) is not None]
    return sum(vals)/len(vals) if vals else None

def find_fx_rate(series, target_date_str):
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

# Get current FX rates
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
eur_now = cfg["eur"] + (cfg["chf"] * chf_eur_now) + (cfg["usd"] * usd_eur_now) if chf_eur_now and usd_eur_now else cfg["eur"]

# Historical FX at start date
chf_series = (chf_inst.get("series_2y") or chf_inst.get("series_1y")) if chf_inst else None
usd_series = (usd_inst.get("series_2y") or usd_inst.get("series_1y")) if usd_inst else None
chf_eur_then = find_fx_rate(chf_series, cfg["start_date"]) if chf_series else None
usd_eur_then = find_fx_rate(usd_series, cfg["start_date"]) if usd_series else None

if chf_eur_then and usd_eur_then:
    eur_then = cfg["eur"] + (cfg["chf"] * chf_eur_then) + (cfg["usd"] * usd_eur_then)
    delta = eur_now - eur_then
    delta_pct = (delta / eur_then) * 100
else:
    eur_then = delta = delta_pct = None

# Patrimony changes using FX changes
def pat_chg(period):
    chf_chg = chf_inst.get("changes",{}).get(period) if chf_inst else None
    usd_chg = usd_inst.get("changes",{}).get(period) if usd_inst else None
    if chf_chg is None or usd_chg is None: return None
    # approximate: weighted average of FX moves on CHF and USD portions
    chf_eur_base = chf_eur_now / (1 + chf_chg/100) if chf_eur_now else None
    usd_eur_base = usd_eur_now / (1 + usd_chg/100) if usd_eur_now else None
    if not chf_eur_base or not usd_eur_base: return None
    eur_base = cfg["eur"] + cfg["chf"] * chf_eur_base + cfg["usd"] * usd_eur_base
    return ((eur_now - eur_base) / eur_base) * 100 if eur_base else None

pat_1d  = pat_chg("1D")
pat_mtd = pat_chg("MTD")
pat_ytd = pat_chg("YTD")

start_fmt = datetime.strptime(cfg["start_date"], "%Y-%m-%d").strftime("%d %b %Y")

# Collect all instruments for cross-section averages
all_instruments = []
for sec in sections.values():
    all_instruments.extend(sec.get("instruments", []))

avg_1d  = avg_chg(all_instruments, "1D")
avg_mtd = avg_chg(all_instruments, "MTD")
avg_ytd = avg_chg(all_instruments, "YTD")

# ============ BUILD EMAIL ============
SEP  = "=" * 62
SEP2 = "-" * 62
SEP3 = "·" * 62

lines = []
lines.append(SEP)
lines.append(f"  MARKET REPORT — {updated}")
lines.append(SEP)

# Patrimony block
lines.append("")
lines.append("┌─ PATRIMONY ────────────────────────────────────────────────┐")
lines.append(f"│  Composition: EUR {cfg['eur']:>10,} · CHF {cfg['chf']:>10,} · USD {cfg['usd']:>10,}")
lines.append(f"│  Current EUR value : € {round(eur_now):>12,}")
if eur_then:
    sign = "+" if delta >= 0 else ""
    lines.append(f"│  Start value ({start_fmt}): € {round(eur_then):>12,}")
    lines.append(f"│  Delta since start : {sign}€ {round(abs(delta)):>10,}  ({sign}{delta_pct:.2f}%)")
lines.append("│")
lines.append(f"│  Performance via FX moves:")
lines.append(f"│    1D   {fmt_chg(pat_1d).strip():>8}  ·  {'+' if pat_1d and pat_1d>=0 else ''}€ {abs(round(eur_now*(pat_1d or 0)/100)):,}" if pat_1d else f"│    1D   —")
lines.append(f"│    MTD  {fmt_chg(pat_mtd).strip():>8}  ·  {'+' if pat_mtd and pat_mtd>=0 else ''}€ {abs(round(eur_now*(pat_mtd or 0)/100)):,}" if pat_mtd else f"│    MTD  —")
lines.append(f"│    YTD  {fmt_chg(pat_ytd).strip():>8}  ·  {'+' if pat_ytd and pat_ytd>=0 else ''}€ {abs(round(eur_now*(pat_ytd or 0)/100)):,}" if pat_ytd else f"│    YTD  —")
lines.append("│")
lines.append(f"│  CHF/EUR: {chf_eur_now:.4f} (then: {chf_eur_then:.4f})" if chf_eur_then else f"│  CHF/EUR: {chf_eur_now:.4f}" if chf_eur_now else "│  CHF/EUR: —")
lines.append(f"│  USD/EUR: {usd_eur_now:.4f} (then: {usd_eur_then:.4f})" if usd_eur_then else f"│  USD/EUR: {usd_eur_now:.4f}" if usd_eur_now else "│  USD/EUR: —")
lines.append("└────────────────────────────────────────────────────────────┘")

# Market averages
lines.append("")
lines.append("┌─ MARKET AVERAGES (all instruments) ────────────────────────┐")
lines.append(f"│  1D avg  {fmt_chg(avg_1d).strip():>8}  ·  MTD avg {fmt_chg(avg_mtd).strip():>8}  ·  YTD avg {fmt_chg(avg_ytd).strip():>8}")
lines.append("└────────────────────────────────────────────────────────────┘")

# Sections
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

    s1d  = avg_chg(instruments, "1D")
    smtd = avg_chg(instruments, "MTD")
    sytd = avg_chg(instruments, "YTD")

    lines.append("")
    lines.append(f"  {title}")
    lines.append(f"  {'─'*44}")
    lines.append(f"  {'Avg':>26}  {fmt_chg(s1d)}  {fmt_chg(smtd)}  {fmt_chg(sytd)}")
    lines.append(f"  {'─'*44}")
    lines.append(f"  {'':22}  {'':>10}  {'1D':>8}  {'MTD':>8}  {'YTD':>8}")

    for inst in instruments:
        label   = inst.get("label", "")[:22]
        val     = inst.get("current")
        dec     = inst.get("decimals", 2)
        chg_1d  = inst.get("changes", {}).get("1D")
        chg_mtd = inst.get("changes", {}).get("MTD")
        chg_ytd = inst.get("changes", {}).get("YTD")
        val_str = fmt_val(val, dec) if isinstance(val, (int, float)) else str(val) if val else "—"
        lines.append(f"  {label:<22}  {val_str:>10}  {fmt_chg(chg_1d)}  {fmt_chg(chg_mtd)}  {fmt_chg(chg_ytd)}")

    commentary = sec.get("commentary", "")
    if commentary:
        words = commentary.split()
        line_buf, wrapped = [], []
        for w in words:
            if len(" ".join(line_buf + [w])) > 56:
                wrapped.append("  » " + " ".join(line_buf))
                line_buf = [w]
            else:
                line_buf.append(w)
        if line_buf:
            wrapped.append("  » " + " ".join(line_buf))
        lines.extend(wrapped)

# News
news = d.get("news", [])
if news:
    lines.append("")
    lines.append("  HEADLINES")
    lines.append(f"  {'─'*44}")
    for i, n in enumerate(news[:6], 1):
        lines.append(f"  {i}. {n.get('title','')}")
        if n.get("source"): lines.append(f"     {n['source']}")
        if n.get("link"):   lines.append(f"     {n['link']}")
        lines.append("")

lines.append(SEP)
lines.append(f"  Dashboard: https://mskiav.github.io/market-dashboard/")
lines.append(SEP)

body = "\n".join(lines)

# Send
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
