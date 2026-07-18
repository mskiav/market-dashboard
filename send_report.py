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

with open("data.json") as f:
    d = json.load(f)

updated = d.get("updated", "—")
pat = d.get("patrimony", {})
sections = d.get("sections", {})

lines = []
lines.append("=" * 58)
lines.append(f"  MARKET REPORT — {updated}")
lines.append("=" * 58)

if pat:
    eur_val = pat.get("current_eur", 0)
    chg_1d  = pat.get("changes", {}).get("1D")
    chg_ytd = pat.get("changes", {}).get("YTD")
    delta_1d_eur = round(eur_val * chg_1d / 100) if chg_1d else None
    lines.append("")
    lines.append("PATRIMONY (CHF 55% / EUR 40% / USD 5%)")
    lines.append(f"  Current value : € {eur_val:,}")
    lines.append(f"  1D            : {fmt_chg(chg_1d)}" + (f"  (€ {delta_1d_eur:+,})" if delta_1d_eur else ""))
    lines.append(f"  YTD           : {fmt_chg(chg_ytd)}")

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
        chg_str = fmt_chg(chg)
        lines.append(f"  {label:<22} {val_str:>10}   {chg_str}")
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
