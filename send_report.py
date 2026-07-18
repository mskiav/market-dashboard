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
