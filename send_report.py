import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def fmt_chg(v):
    if v is None: return '<span style="color:#999">—</span>'
    sign = "+" if v > 0 else ""
    color = "#1a7a4a" if v > 0 else "#c0392b" if v < 0 else "#666"
    return f'<span style="color:{color};font-weight:700">{sign}{v:.2f}%</span>'

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
    if chf_chg is None or usd_chg is None: return None
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
    "fx":      ("FX",                   "#1a5fa8", "#e8f0fa"),
    "indices": ("GLOBAL INDICES",       "#1a7a4a", "#e8f5ee"),
    "energy":  ("ENERGY & COMMODITIES", "#a06010", "#fdf3e3"),
    "crypto":  ("METALS & CRYPTO",      "#6e2da8", "#f3eafd"),
    "rates":   ("RATES & RISK",         "#a02020", "#fdeaea"),
}

subject_tag = "Morning" if now_hour < 8 else "Afternoon" if now_hour < 14 else "Evening"

html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,Helvetica,sans-serif;color:#1a1a2e">
<div style="max-width:660px;margin:0 auto;padding:12px">

  <div style="background:#1a1a2e;border-radius:8px;padding:12px 18px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="font-size:10px;color:#888;letter-spacing:0.15em;text-transform:uppercase">Market Dashboard</div>
      <div style="font-size:18px;font-weight:700;color:#fff;margin-top:2px">{time_of_day} Report</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:11px;color:#aaa">{updated}</div>
      <a href="https://mskiav.github.io/market-dashboard/" style="font-size:11px;color:#ffb84d;text-decoration:none">Open dashboard &#8594;</a>
    </div>
  </div>

  <div style="background:#fff;border-radius:8px;padding:12px 16px;margin-bottom:10px;border-left:4px solid #ffb84d">
    <div style="font-size:10px;color:#ffb84d;letter-spacing:0.15em;text-transform:uppercase;font-weight:700;margin-bottom:8px">&#9658; Patrimony</div>
    <div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:4px">
      <div style="font-size:26px;font-weight:700;color:#1a1a2e">&#8364; {round(eur_now):,}</div>
      {'<div style="font-size:12px;color:#666">Start '+ start_fmt +': &#8364; '+ f"{round(eur_then):,}" +'&nbsp;&nbsp;<span style="color:' + ("#1a7a4a" if delta>=0 else "#c0392b") + ';font-weight:700">' + ("+" if delta>=0 else "") + f"&#8364; {abs(round(delta)):,} ({delta_pct:+.2f}%)</span></div>" if eur_then else ""}
    </div>
    <div style="font-size:10px;color:#888;margin-bottom:8px">EUR {cfg['eur']:,} &nbsp;&middot;&nbsp; CHF {cfg['chf']:,} &nbsp;&middot;&nbsp; USD {cfg['usd']:,}</div>
    <table style="width:100%;border-collapse:collapse;font-size:12px">
      <tr style="background:#f8f8f8">
        <td style="padding:3px 8px;color:#666;font-size:10px;font-weight:700;width:15%">PERIOD</td>
        <td style="padding:3px 8px;color:#666;font-size:10px;font-weight:700;text-align:right;width:22%">CHANGE %</td>
        <td style="padding:3px 8px;color:#666;font-size:10px;font-weight:700;text-align:right">CHANGE &#8364;</td>
        <td style="padding:3px 8px;color:#666;font-size:10px;font-weight:700;text-align:right">CHF/EUR</td>
        <td style="padding:3px 8px;color:#666;font-size:10px;font-weight:700;text-align:right">USD/EUR</td>
      </tr>"""

for period, pval, chf_v, usd_v in [
    ("1D",  pat_1d,  chf_inst.get("changes",{}).get("1D")  if chf_inst else None, usd_inst.get("changes",{}).get("1D")  if usd_inst else None),
    ("MTD", pat_mtd, chf_inst.get("changes",{}).get("MTD") if chf_inst else None, usd_inst.get("changes",{}).get("MTD") if usd_inst else None),
    ("YTD", pat_ytd, chf_inst.get("changes",{}).get("YTD") if chf_inst else None, usd_inst.get("changes",{}).get("YTD") if usd_inst else None),
]:
    def fc(v):
        if v is None: return '<span style="color:#999">—</span>'
        col = "#1a7a4a" if v>=0 else "#c0392b"
        return f'<span style="color:{col};font-weight:700">{"+" if v>=0 else ""}{v:.2f}%</span>'
    def fe(v):
        if v is None: return "—"
        e = round(eur_now*v/100)
        col = "#1a7a4a" if e>=0 else "#c0392b"
        return f'<span style="color:{col};font-weight:700">{"+" if e>=0 else ""}&#8364;{abs(e):,}</span>'
    html += f"""
      <tr style="border-top:1px solid #eee">
        <td style="padding:3px 8px;font-weight:700;font-size:12px">{period}</td>
        <td style="padding:3px 8px;text-align:right">{fc(pval)}</td>
        <td style="padding:3px 8px;text-align:right">{fe(pval)}</td>
        <td style="padding:3px 8px;text-align:right;font-size:11px">{fc(chf_v)}</td>
        <td style="padding:3px 8px;text-align:right;font-size:11px">{fc(usd_v)}</td>
      </tr>"""

html += f"""
    </table>
  </div>

  <div style="background:#fff;border-radius:8px;padding:10px 16px;margin-bottom:10px">
    <div style="font-size:10px;color:#888;letter-spacing:0.15em;text-transform:uppercase;font-weight:700;margin-bottom:6px">&#9658; Market averages — all instruments</div>
    <table style="width:100%;border-collapse:collapse">
      <tr>
        <td style="padding:2px 8px;color:#666;font-size:10px;font-weight:700;width:20%"></td>
        <td style="padding:2px 8px;color:#666;font-size:10px;font-weight:700;text-align:center;width:26%">1D</td>
        <td style="padding:2px 8px;color:#666;font-size:10px;font-weight:700;text-align:center;width:26%">MTD</td>
        <td style="padding:2px 8px;color:#666;font-size:10px;font-weight:700;text-align:center">YTD</td>
      </tr>
      <tr style="background:#f8f8f8">
        <td style="padding:3px 8px;font-size:12px;font-weight:700">Average</td>
        <td style="padding:3px 8px;text-align:center;font-size:13px">{fmt_chg(avg_1d)}</td>
        <td style="padding:3px 8px;text-align:center;font-size:13px">{fmt_chg(avg_mtd)}</td>
        <td style="padding:3px 8px;text-align:center;font-size:13px">{fmt_chg(avg_ytd)}</td>
      </tr>
    </table>
  </div>
"""

for sec_key, (title, color, bg) in SECTION_TITLES.items():
    sec = sections.get(sec_key, {})
    instruments = sec.get("instruments", [])
    if not instruments: continue

    s1d  = avg_chg(instruments, "1D")
    smtd = avg_chg(instruments, "MTD")
    sytd = avg_chg(instruments, "YTD")

    rows = ""
    for inst in instruments:
        label   = inst.get("label","")
        val     = inst.get("current")
        dec     = inst.get("decimals",2)
        chg_1d  = inst.get("changes",{}).get("1D")
        chg_mtd = inst.get("changes",{}).get("MTD")
        chg_ytd = inst.get("changes",{}).get("YTD")
        val_str = fmt_val(val,dec) if isinstance(val,(int,float)) else str(val) if val else "—"

        def fc2(v):
            if v is None: return '<span style="color:#999">—</span>'
            col = "#1a7a4a" if v>=0 else "#c0392b"
            return f'<span style="color:{col};font-weight:700">{"+" if v>=0 else ""}{v:.2f}%</span>'

        rows += f"""
        <tr style="border-top:1px solid #eee">
          <td style="padding:3px 8px;color:#333;font-size:12px">{label}</td>
          <td style="padding:3px 8px;color:#1a1a2e;font-size:12px;text-align:right;font-weight:700">{val_str}</td>
          <td style="padding:3px 8px;text-align:right;font-size:11px">{fc2(chg_1d)}</td>
          <td style="padding:3px 8px;text-align:right;font-size:11px">{fc2(chg_mtd)}</td>
          <td style="padding:3px 8px;text-align:right;font-size:11px">{fc2(chg_ytd)}</td>
        </tr>"""

    html += f"""
  <div style="background:{bg};border-radius:8px;padding:10px 14px;margin-bottom:8px;border-left:4px solid {color}">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;flex-wrap:wrap;gap:4px">
      <div style="font-size:10px;color:{color};letter-spacing:0.15em;text-transform:uppercase;font-weight:700">{title}</div>
      <div style="font-size:10px;color:#666">avg &nbsp; 1D: {fmt_chg(s1d)} &nbsp;&middot;&nbsp; MTD: {fmt_chg(smtd)} &nbsp;&middot;&nbsp; YTD: {fmt_chg(sytd)}</div>
    </div>
    <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:6px;overflow:hidden">
      <tr style="background:#f0f0f0">
        <th style="padding:2px 8px;color:#666;font-size:10px;text-align:left;font-weight:600">INSTRUMENT</th>
        <th style="padding:2px 8px;color:#666;font-size:10px;text-align:right;font-weight:600">VALUE</th>
        <th style="padding:2px 8px;color:#666;font-size:10px;text-align:right;font-weight:600">1D</th>
        <th style="padding:2px 8px;color:#666;font-size:10px;text-align:right;font-weight:600">MTD</th>
        <th style="padding:2px 8px;color:#666;font-size:10px;text-align:right;font-weight:600">YTD</th>
      </tr>
      {rows}
    </table>
  </div>"""

news = d.get("news", [])
if news:
    news_rows = ""
    for i, n in enumerate(news[:6]):
        title_text = n.get("title","")
        source     = n.get("source","")
        link       = n.get("link","")
        bg_row = "#fff" if i % 2 == 0 else "#f8f8f8"
        news_rows += f"""
        <tr style="background:{bg_row};border-top:1px solid #eee">
          <td style="padding:4px 10px">
            {'<a href="'+link+'" style="color:#1a1a2e;text-decoration:none;font-size:12px;font-weight:600">'+title_text+'</a>' if link else '<span style="font-size:12px;font-weight:600">'+title_text+'</span>'}
            <span style="font-size:10px;color:#888;margin-left:6px">{source}</span>
          </td>
        </tr>"""
    html += f"""
  <div style="background:#fff;border-radius:8px;padding:10px 14px;margin-bottom:10px">
    <div style="font-size:10px;color:#888;letter-spacing:0.15em;text-transform:uppercase;font-weight:700;margin-bottom:6px">&#9658; Headlines</div>
    <table style="width:100%;border-collapse:collapse">{news_rows}</table>
  </div>"""

html += f"""
  <div style="text-align:center;padding:10px;font-size:11px;color:#888">
    <a href="https://mskiav.github.io/market-dashboard/" style="color:#1a5fa8;text-decoration:none;font-weight:600">Open full dashboard &#8594;</a>
    &nbsp;&middot;&nbsp; {updated}
  </div>
</div>
</body>
</html>"""

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

print(f"Sending to {mail_to}...")
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
        server.login(gmail_user, gmail_pwd)
        server.sendmail(gmail_user, mail_to, msg.as_string())
        print(f"Email sent to {mail_to}")
except smtplib.SMTPAuthenticationError as e:
    print(f"AUTH ERROR: {e}")
    raise
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    raise
