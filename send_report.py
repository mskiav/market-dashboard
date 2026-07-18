import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def fmt_chg(v):
    if v is None: return '<span style="color:#666">—</span>'
    sign = "+" if v > 0 else ""
    color = "#00c87a" if v > 0 else "#ff5566" if v < 0 else "#888"
    return f'<span style="color:{color};font-weight:600">{sign}{v:.2f}%</span>'

def fmt_val(v, dec=2):
    if v is None: return "—"
    if isinstance(v, (int, float)):
        return f"{v:,.{dec}f}"
    return str(v) if v else "—"

def avg_chg(instruments, period):
    vals = [i.get("changes",{}).get(period) for i in instruments if i.get("changes",{}).get(period) is not None]
    return sum(vals)/len(vals) if vals else None

def find_fx_rate(series, target_date_str):
    if not series or not series.get("labels") or not series.get("values"):
        return None
    target = datetime.strptime(target_date_str, "%Y-%m-%d")
    month_map = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
                 "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    best_idx, best_diff = 0, float("inf")
    for i, lbl in enumerate(series["labels"]):
        parts = lbl.split()
        if len(parts) < 2: continue
        m = month_map.get(parts[0])
        y = 2000 + int(parts[1]) if len(parts[1]) == 2 else int(parts[1])
        if not m: continue
        diff = abs((datetime(y, m, 15) - target).days)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return series["values"][best_idx] if series["values"] else None

# Load
with open("data.json") as f:
    d = json.load(f)
with open("patrimony_config.json") as f:
    cfg = json.load(f)

updated  = d.get("updated", "—")
sections = d.get("sections", {})

def get_inst(sym):
    for sec in sections.values():
        for inst in sec.get("instruments", []):
            if inst.get("symbol") == sym:
                return inst
    return None

chf_inst    = get_inst("CHFEUR=X")
usd_inst    = get_inst("EURUSD=X")
chf_eur_now = chf_inst.get("raw_current") if chf_inst else None
usd_eur_raw = usd_inst.get("raw_current") if usd_inst else None
usd_eur_now = (1/usd_eur_raw) if usd_eur_raw else None

eur_now = cfg["eur"] + (cfg["chf"]*chf_eur_now) + (cfg["usd"]*usd_eur_now) if chf_eur_now and usd_eur_now else cfg["eur"]

chf_series   = (chf_inst.get("series_2y") or chf_inst.get("series_1y")) if chf_inst else None
usd_series   = (usd_inst.get("series_2y") or usd_inst.get("series_1y")) if usd_inst else None
chf_eur_then = find_fx_rate(chf_series, cfg["start_date"]) if chf_series else None
usd_eur_then = find_fx_rate(usd_series, cfg["start_date"]) if usd_series else None

if chf_eur_then and usd_eur_then:
    eur_then  = cfg["eur"] + (cfg["chf"]*chf_eur_then) + (cfg["usd"]*usd_eur_then)
    delta     = eur_now - eur_then
    delta_pct = (delta/eur_then)*100
else:
    eur_then = delta = delta_pct = None

def pat_chg(period):
    chf_chg = chf_inst.get("changes",{}).get(period) if chf_inst else None
    usd_chg = usd_inst.get("changes",{}).get(period) if usd_inst else None
    if chg_chg is None or usd_chg is None: return None
    chf_base = chf_eur_now/(1+chf_chg/100) if chf_eur_now else None
    usd_base = usd_eur_now/(1+usd_chg/100) if usd_eur_now else None
    if not chf_base or not usd_base: return None
    base = cfg["eur"] + cfg["chf"]*chf_base + cfg["usd"]*usd_base
    return ((eur_now-base)/base)*100 if base else None

pat_1d  = pat_chg("1D")
pat_mtd = pat_chg("MTD")
pat_ytd = pat_chg("YTD")

all_instruments = [i for sec in sections.values() for i in sec.get("instruments",[])]
avg_1d  = avg_chg(all_instruments, "1D")
avg_mtd = avg_chg(all_instruments, "MTD")
avg_ytd = avg_chg(all_instruments, "YTD")

start_fmt = datetime.strptime(cfg["start_date"], "%Y-%m-%d").strftime("%d %b %Y")

SECTION_TITLES = {
    "fx":      ("FX", "#5aa7ff"),
    "indices": ("GLOBAL INDICES", "#00d488"),
    "energy":  ("ENERGY & COMMODITIES", "#ffb84d"),
    "crypto":  ("METALS & CRYPTO", "#bf76ff"),
    "rates":   ("RATES & RISK", "#ff5566"),
}

def chg_row(label, v):
    if v is None: return ""
    sign = "+" if v >= 0 else ""
    col  = "#00c87a" if v >= 0 else "#ff5566"
    eur_delta = round(eur_now * v / 100)
    eur_sign  = "+" if eur_delta >= 0 else ""
    return f"""
    <tr>
      <td style="padding:4px 10px;color:#aaa;font-size:13px">{label}</td>
      <td style="padding:4px 10px;color:{col};font-weight:700;font-size:15px;text-align:right">{sign}{v:.2f}%</td>
      <td style="padding:4px 10px;color:{col};font-size:13px;text-align:right">{eur_sign}€ {abs(eur_delta):,}</td>
    </tr>"""

html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#06080a;font-family:'Courier New',monospace;color:#eef2f7">
<div style="max-width:680px;margin:0 auto;padding:20px">

  <div style="background:#0e1116;border:1px solid #2a3340;border-radius:8px;padding:20px 24px;margin-bottom:16px">
    <div style="font-size:11px;color:#475568;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:6px">Market Dashboard</div>
    <div style="font-size:22px;font-weight:700;color:#eef2f7">{"Morning" if datetime.utcnow().hour < 10 else "Afternoon"} Report</div>
    <div style="font-size:12px;color:#475568;margin-top:4px">{updated}</div>
  </div>

  <div style="background:#0e1116;border:1px solid #2a3340;border-radius:8px;padding:20px 24px;margin-bottom:16px">
    <div style="font-size:10px;color:#ffb84d;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:14px">&#9658; Patrimony</div>
    <div style="font-size:11px;color:#475568;margin-bottom:10px">EUR {cfg['eur']:,} &nbsp;&middot;&nbsp; CHF {cfg['chf']:,} &nbsp;&middot;&nbsp; USD {cfg['usd']:,}</div>
    <div style="font-size:32px;font-weight:700;color:#eef2f7;letter-spacing:-0.02em">&#8364; {round(eur_now):,}</div>
    {'<div style="font-size:13px;color:#475568;margin-top:6px">Start value '+ start_fmt +': &#8364; '+ f"{round(eur_then):,}" +'&nbsp;&nbsp;<span style="color:' + ("#00c87a" if delta>=0 else "#ff5566") + ';font-weight:600">' + ("+" if delta>=0 else "") + f"&#8364; {abs(round(delta)):,} ({delta_pct:+.2f}%)</span></div>" if eur_then else ""}
    <table style="width:100%;margin-top:16px;border-collapse:collapse">
      <tr style="border-bottom:1px solid #1e2630">
        <td style="padding:6px 10px;color:#475568;font-size:11px;letter-spacing:0.1em">PERIOD</td>
        <td style="padding:6px 10px;color:#475568;font-size:11px;letter-spacing:0.1em;text-align:right">CHANGE %</td>
        <td style="padding:6px 10px;color:#475568;font-size:11px;letter-spacing:0.1em;text-align:right">CHANGE &#8364;</td>
      </tr>
      {chg_row("1D", pat_1d)}
      {chg_row("MTD", pat_mtd)}
      {chg_row("YTD", pat_ytd)}
    </table>
    <div style="margin-top:12px;font-size:11px;color:#475568">
      CHF/EUR: {f"{chf_eur_now:.4f}" if chf_eur_now else "&#8212;"}
      {f"(start: {chf_eur_then:.4f})" if chf_eur_then else ""}
      &nbsp;&middot;&nbsp;
      USD/EUR: {f"{usd_eur_now:.4f}" if usd_eur_now else "&#8212;"}
      {f"(start: {usd_eur_then:.4f})" if usd_eur_then else ""}
    </div>
  </div>

  <div style="background:#0e1116;border:1px solid #2a3340;border-radius:8px;padding:16px 24px;margin-bottom:16px">
    <div style="font-size:10px;color:#ffb84d;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:12px">&#9658; Market averages (all instruments)</div>
    <table style="width:100%;border-collapse:collapse">
      <tr>
        <td style="padding:4px 10px;color:#475568;font-size:12px;width:30%">1D average</td>
        <td style="padding:4px 10px;font-size:15px;font-weight:700">{fmt_chg(avg_1d)}</td>
      </tr>
      <tr>
        <td style="padding:4px 10px;color:#475568;font-size:12px">MTD average</td>
        <td style="padding:4px 10px;font-size:15px;font-weight:700">{fmt_chg(avg_mtd)}</td>
      </tr>
      <tr>
        <td style="padding:4px 10px;color:#475568;font-size:12px">YTD average</td>
        <td style="padding:4px 10px;font-size:15px;font-weight:700">{fmt_chg(avg_ytd)}</td>
      </tr>
    </table>
  </div>
"""

for sec_key, (title, color) in SECTION_TITLES.items():
    sec = sections.get(sec_key, {})
    instruments = sec.get("instruments", [])
    if not instruments: continue

    s1d  = avg_chg(instruments, "1D")
    smtd = avg_chg(instruments, "MTD")
    sytd = avg_chg(instruments, "YTD")
    commentary = sec.get("commentary", "")

    rows = ""
    for inst in instruments:
        label   = inst.get("label","")
        val     = inst.get("current")
        dec     = inst.get("decimals",2)
        chg_1d  = inst.get("changes",{}).get("1D")
        chg_mtd = inst.get("changes",{}).get("MTD")
        chg_ytd = inst.get("changes",{}).get("YTD")
        val_str = fmt_val(val,dec) if isinstance(val,(int,float)) else str(val) if val else "&#8212;"
        rows += f"""
        <tr style="border-bottom:1px solid #1a2030">
          <td style="padding:7px 10px;color:#ccc;font-size:13px">{label}</td>
          <td style="padding:7px 10px;color:#eef2f7;font-size:13px;text-align:right;font-weight:600">{val_str}</td>
          <td style="padding:7px 10px;text-align:right;font-size:13px">{fmt_chg(chg_1d)}</td>
          <td style="padding:7px 10px;text-align:right;font-size:13px">{fmt_chg(chg_mtd)}</td>
          <td style="padding:7px 10px;text-align:right;font-size:13px">{fmt_chg(chg_ytd)}</td>
        </tr>"""

    html += f"""
  <div style="background:#0e1116;border:1px solid #2a3340;border-left:3px solid {color};border-radius:8px;padding:16px 24px;margin-bottom:12px">
    <div style="font-size:10px;color:{color};letter-spacing:0.18em;text-transform:uppercase;margin-bottom:12px">&#9658; {title}</div>
    <div style="font-size:11px;color:#475568;margin-bottom:10px">avg &nbsp; 1D: {fmt_chg(s1d)} &nbsp;&middot;&nbsp; MTD: {fmt_chg(smtd)} &nbsp;&middot;&nbsp; YTD: {fmt_chg(sytd)}</div>
    <table style="width:100%;border-collapse:collapse">
      <tr style="border-bottom:1px solid #2a3340">
        <th style="padding:5px 10px;color:#475568;font-size:10px;letter-spacing:0.1em;text-align:left;font-weight:400">INSTRUMENT</th>
        <th style="padding:5px 10px;color:#475568;font-size:10px;letter-spacing:0.1em;text-align:right;font-weight:400">VALUE</th>
        <th style="padding:5px 10px;color:#475568;font-size:10px;letter-spacing:0.1em;text-align:right;font-weight:400">1D</th>
        <th style="padding:5px 10px;color:#475568;font-size:10px;letter-spacing:0.1em;text-align:right;font-weight:400">MTD</th>
        <th style="padding:5px 10px;color:#475568;font-size:10px;letter-spacing:0.1em;text-align:right;font-weight:400">YTD</th>
      </tr>
      {rows}
    </table>
    {f'<div style="margin-top:10px;font-size:11px;color:#475568;font-style:italic">{commentary}</div>' if commentary else ""}
  </div>"""

news = d.get("news", [])
if news:
    news_rows = ""
    for n in news[:6]:
        title_text = n.get("title","")
        source     = n.get("source","")
        link       = n.get("link","")
        news_rows += f"""
        <tr style="border-bottom:1px solid #1a2030">
          <td style="padding:8px 10px">
            {'<a href="'+link+'" style="color:#eef2f7;text-decoration:none;font-size:13px;font-weight:500">'+title_text+'</a>' if link else '<span style="font-size:13px">'+title_text+'</span>'}
            <div style="font-size:11px;color:#475568;margin-top:3px">{source}</div>
          </td>
        </tr>"""
    html += f"""
  <div style="background:#0e1116;border:1px solid #2a3340;border-radius:8px;padding:16px 24px;margin-bottom:16px">
    <div style="font-size:10px;color:#ffb84d;letter-spacing:0.18em;text-transform:uppercase;margin-bottom:12px">&#9658; Headlines</div>
    <table style="width:100%;border-collapse:collapse">{news_rows}</table>
  </div>"""

html += f"""
  <div style="text-align:center;padding:16px;font-size:11px;color:#475568">
    <a href="https://mskiav.github.io/market-dashboard/" style="color:#ffb84d;text-decoration:none">Open full dashboard &#8594;</a>
    <div style="margin-top:6px">Generated automatically &middot; {updated}</div>
  </div>
</div>
</body>
</html>"""

# Send
gmail_user  = os.environ["GMAIL_USER"]
gmail_pwd   = os.environ["GMAIL_APP_PASSWORD"]
mail_to     = os.environ["MAIL_TO"]
now_hour    = datetime.utcnow().hour
subject_tag = "Morning" if now_hour < 10 else "Afternoon"
subject     = f"[Market] {subject_tag} Report — {updated}"

msg = MIMEMultipart("alternative")
msg["From"]    = gmail_user
msg["To"]      = mail_to
msg["Subject"] = subject
msg.attach(MIMEText(html, "html", "utf-8"))

print(f"Connecting to Gmail SMTP...")
print(f"From: {gmail_user}")
print(f"To: {mail_to}")
print(f"HTML length: {len(html)} chars")

try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        print("Connected to SMTP server")
        server.login(gmail_user, gmail_pwd)
        print("Logged in successfully")
        server.sendmail(gmail_user, mail_to, msg.as_string())
        print(f"Email sent to {mail_to}")
except smtplib.SMTPAuthenticationError as e:
    print(f"AUTH ERROR: {e} — check GMAIL_APP_PASSWORD secret")
    raise
except smtplib.SMTPException as e:
    print(f"SMTP ERROR: {e}")
    raise
except Exception as e:
    print(f"GENERAL ERROR: {type(e).__name__}: {e}")
    raise
