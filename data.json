import yfinance as yf
import json
import datetime
from datetime import date, timedelta

# ============ PATRIMONY WEIGHTS (Marco) ============
PATRIMONY_EUR = 6_000_000
WEIGHT_CHF = 0.55
WEIGHT_EUR = 0.40
WEIGHT_USD = 0.05

# ============ HELPERS ============
def fmt(v, dec=2):
    if v is None: return None
    try: return round(float(v), dec)
    except: return None

def pct(curr, ref):
    if curr is None or ref is None or ref == 0: return None
    return fmt(((curr - ref) / ref) * 100, 2)

# ============ TICKER REGISTRY ============
TICKERS = {
    # FX
    "CHFEUR=X":   {"label":"CHF / EUR",      "section":"fx",      "decimals":4},
    "EURUSD=X":   {"label":"USD / EUR",      "section":"fx",      "decimals":4, "invert":True},
    "GBPEUR=X":   {"label":"GBP / EUR",      "section":"fx",      "decimals":4},
    # Indices
    "^GSPC":      {"label":"S&P 500",        "section":"indices", "decimals":0},
    "^IXIC":      {"label":"Nasdaq",         "section":"indices", "decimals":0},
    "^STOXX50E":  {"label":"EuroStoxx 50",   "section":"indices", "decimals":0},
    "FTSEMIB.MI": {"label":"FTSE MIB",       "section":"indices", "decimals":0},
    "^GDAXI":     {"label":"DAX",            "section":"indices", "decimals":0},
    "^FCHI":      {"label":"CAC 40",         "section":"indices", "decimals":0},
    "^SSMI":      {"label":"SMI",            "section":"indices", "decimals":0},
    "^FTSE":      {"label":"FTSE 100",       "section":"indices", "decimals":0},
    "^N225":      {"label":"Nikkei 225",     "section":"indices", "decimals":0},
    "^HSI":       {"label":"Hang Seng",      "section":"indices", "decimals":0},
    "000300.SS":  {"label":"CSI 300",        "section":"indices", "decimals":0},
    # Energy
    "BZ=F":       {"label":"Brent USD/bbl",  "section":"energy",  "decimals":2},
    "CL=F":       {"label":"WTI USD/bbl",    "section":"energy",  "decimals":2},
    "TTF=F":      {"label":"TTF EUR/MWh",    "section":"energy",  "decimals":2},
    "NG=F":       {"label":"Nat Gas USD",    "section":"energy",  "decimals":2},
    # Metals & Crypto
    "GC=F":       {"label":"Gold USD/oz",    "section":"crypto",  "decimals":0},
    "SI=F":       {"label":"Silver USD/oz",  "section":"crypto",  "decimals":2},
    "BTC-EUR":    {"label":"Bitcoin EUR",    "section":"crypto",  "decimals":0},
    "ETH-EUR":    {"label":"Ethereum EUR",   "section":"crypto",  "decimals":0},
    # Rates & risk
    "^VIX":       {"label":"VIX",            "section":"rates",   "decimals":2},
    "^TNX":       {"label":"US 10Y yield",   "section":"rates",   "decimals":2},
    "^TYX":       {"label":"US 30Y yield",   "section":"rates",   "decimals":2},
    "IBTM.MI":    {"label":"BTP 10Y proxy",  "section":"rates",   "decimals":2},
    "IBGS.MI":    {"label":"Bund 10Y proxy", "section":"rates",   "decimals":2},
}

# ============ FETCH HISTORICAL DATA ============
def fetch_history(symbols):
    """Get 2Y daily history for all symbols — single batch call."""
    print(f"Downloading 2Y history for {len(symbols)} symbols...")
    data = yf.download(
        tickers=" ".join(symbols),
        period="2y",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True
    )
    return data

def get_close(hist_df, sym, target_date):
    """Get close price on or just before target_date."""
    try:
        if len(symbols_to_fetch) == 1:
            df = hist_df
        else:
            df = hist_df[sym] if sym in hist_df.columns.levels[0] else None
        if df is None or df.empty: return None
        df = df.dropna(subset=["Close"])
        df_idx = df.index.date if hasattr(df.index, 'date') else df.index
        mask = [d <= target_date for d in df_idx]
        filtered = df[mask]
        if filtered.empty: return None
        return float(filtered["Close"].iloc[-1])
    except Exception as e:
        return None

# ============ DATE REFERENCES ============
today = date.today()
yesterday = today - timedelta(days=1)
first_of_month = today.replace(day=1)
mtd_ref = first_of_month - timedelta(days=1)
quarter = (today.month - 1) // 3
first_quarter_month = quarter * 3 + 1
first_of_quarter = today.replace(month=first_quarter_month, day=1)
qtd_ref = first_of_quarter - timedelta(days=1)
ytd_ref = date(today.year - 1, 12, 31)
two_y_ref = today - timedelta(days=730)

print(f"References: 1D={yesterday} MTD={mtd_ref} QTD={qtd_ref} YTD={ytd_ref} 2Y={two_y_ref}")

# ============ FETCH ALL ============
symbols_to_fetch = list(TICKERS.keys())
hist = fetch_history(symbols_to_fetch)

# ============ ECB FX ============
def get_fx_ecb():
    import urllib.request
    try:
        url = "https://api.frankfurter.app/latest?from=EUR&symbols=CHF,USD,GBP"
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read())
        rates = d.get("rates", {})
        return {
            "CHFEUR=X": 1/rates["CHF"] if rates.get("CHF") else None,
            "EURUSD=X": rates.get("USD"),
            "GBPEUR=X": 1/rates["GBP"] if rates.get("GBP") else None,
        }
    except Exception as e:
        print(f"  ECB FX error: {e}")
        return {}

print("Fetching ECB FX...")
fx_ecb = get_fx_ecb()

# ============ BUILD INSTRUMENT DATA ============
def get_series(sym):
    try:
        if len(symbols_to_fetch) == 1:
            df = hist
        else:
            df = hist[sym]
        df = df.dropna(subset=["Close"])
        if df.empty: return [], []
        dates = [d.date() for d in df.index.to_pydatetime()]
        closes = [float(v) for v in df["Close"].tolist()]
        return dates, closes
    except Exception as e:
        print(f"  series error {sym}: {e}")
        return [], []

def build_instrument(sym):
    meta = TICKERS[sym]
    dates, closes = get_series(sym)
    if not closes:
        return None

    current = closes[-1]
    invert = meta.get("invert", False)
    if invert: current = 1 / current

    def find_close(ref_date):
        for i in range(len(dates)-1, -1, -1):
            if dates[i] <= ref_date:
                v = closes[i]
                return (1/v) if invert else v
        return None

    prev_close = closes[-2] if len(closes) >= 2 else None
    if prev_close and invert: prev_close = 1/prev_close

    ref_1d  = prev_close
    ref_mtd = find_close(mtd_ref)
    ref_qtd = find_close(qtd_ref)
    ref_ytd = find_close(ytd_ref)
    ref_2y  = find_close(two_y_ref)

    if sym in fx_ecb and fx_ecb[sym]:
        current_display = fx_ecb[sym]
    else:
        current_display = current

    return {
        "symbol": sym,
        "label": meta["label"],
        "section": meta["section"],
        "decimals": meta["decimals"],
        "current": fmt(current_display, meta["decimals"]),
        "raw_current": current,
        "changes": {
            "1D":  pct(current, ref_1d),
            "MTD": pct(current, ref_mtd),
            "QTD": pct(current, ref_qtd),
            "YTD": pct(current, ref_ytd),
            "2Y":  pct(current, ref_2y),
        },
        "series_1y": serialize_series(dates, closes, "1y", invert),
        "series_2y": serialize_series(dates, closes, "2y", invert),
    }

def serialize_series(dates, closes, span, invert):
    if not dates or not closes: return {"labels":[],"values":[]}
    cutoff = today - (timedelta(days=365) if span=="1y" else timedelta(days=730))
    pairs = [(d, c) for d, c in zip(dates, closes) if d >= cutoff]
    if not pairs: return {"labels":[],"values":[]}
    step = max(1, len(pairs) // 60)
    sampled = pairs[::step]
    if sampled[-1] != pairs[-1]: sampled.append(pairs[-1])
    labels = [d.strftime("%b %y") for d, _ in sampled]
    values = [(1/c if invert else c) for _, c in sampled]
    return {"labels": labels, "values": [round(v, 4) for v in values]}

print("Building instruments...")
instruments = {}
for sym in TICKERS:
    print(f"  {sym}")
    inst = build_instrument(sym)
    if inst:
        instruments[sym] = inst

def get(sym):
    return instruments.get(sym)

# ============ PATRIMONY CALCULATION ============
def calc_patrimony():
    chf_eur = instruments.get("CHFEUR=X", {}).get("raw_current")
    usd_eur_raw = instruments.get("EURUSD=X", {}).get("raw_current")
    if not chf_eur or not usd_eur_raw: return None
    usd_eur = 1 / usd_eur_raw

    chf_value_in_chf = (PATRIMONY_EUR * WEIGHT_CHF) / chf_eur
    eur_value = PATRIMONY_EUR * WEIGHT_EUR
    usd_value_in_usd = (PATRIMONY_EUR * WEIGHT_USD) / usd_eur

    current_eur = chf_value_in_chf * chf_eur + eur_value + usd_value_in_usd * usd_eur

    def patrimony_at(ref_pct_chf, ref_pct_usd):
        if ref_pct_chf is None or ref_pct_usd is None: return None
        chf_then = chf_eur / (1 + ref_pct_chf/100)
        usd_then = usd_eur / (1 + ref_pct_usd/100)
        return chf_value_in_chf * chf_then + eur_value + usd_value_in_usd * usd_then

    chf_changes = instruments.get("CHFEUR=X", {}).get("changes", {})
    usd_changes = instruments.get("EURUSD=X", {}).get("changes", {})

    def chg_pct(period):
        then = patrimony_at(chf_changes.get(period), usd_changes.get(period))
        return pct(current_eur, then) if then else None

    return {
        "current_eur": round(current_eur),
        "chf_amount": round(chf_value_in_chf),
        "eur_amount": round(eur_value),
        "usd_amount": round(usd_value_in_usd),
        "changes": {p: chg_pct(p) for p in ["1D","MTD","QTD","YTD","2Y"]}
    }

print("Computing patrimony...")
patrimony = calc_patrimony()

# ============ CHARTS REGISTRY ============
SECTION_CHARTS = {
    "fx":      ["CHFEUR=X","EURUSD=X","GBPEUR=X"],
    "indices": ["^GSPC","^GDAXI","FTSEMIB.MI","^N225"],
    "energy":  ["BZ=F","CL=F","TTF=F"],
    "crypto":  ["GC=F","BTC-EUR"],
    "rates":   ["^VIX","^TNX","IBTM.MI","IBGS.MI"],
}

# ============ COMMENTARY ============
def commentary_for_section(section_key, items):
    if not items: return ""
    changes_1d = [i["changes"].get("1D") for i in items if i["changes"].get("1D") is not None]
    if not changes_1d: return ""
    avg_1d = sum(changes_1d) / len(changes_1d)
    pos = sum(1 for c in changes_1d if c > 0)
    neg = sum(1 for c in changes_1d if c < 0)
    items_with_chg = [(i, i["changes"].get("1D")) for i in items if i["changes"].get("1D") is not None]
    items_with_chg.sort(key=lambda x: abs(x[1]), reverse=True)
    top = items_with_chg[0] if items_with_chg else None

    direction = "broadly positive" if avg_1d > 0.2 else "broadly negative" if avg_1d < -0.2 else "mixed"
    parts = [
        f"Section {direction} today ({pos} up / {neg} down, avg {avg_1d:+.2f}%)."
    ]
    if top:
        parts.append(f"Biggest mover: {top[0]['label']} ({top[1]:+.2f}%).")

    ytd_changes = [i["changes"].get("YTD") for i in items if i["changes"].get("YTD") is not None]
    if ytd_changes:
        avg_ytd = sum(ytd_changes)/len(ytd_changes)
        parts.append(f"YTD section average: {avg_ytd:+.1f}%.")

    return " ".join(parts)

def section_data(section_key):
    items = [instruments[s] for s in TICKERS if TICKERS[s]["section"] == section_key and s in instruments]
    return {
        "instruments": items,
        "charts": [instruments[s] for s in SECTION_CHARTS.get(section_key, []) if s in instruments],
        "commentary": commentary_for_section(section_key, items)
    }

# ============ NEWS ============
def get_news():
    import urllib.request
    from xml.etree import ElementTree as ET
    headlines = []
    feeds = [
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=BZ=F,CL=F,XOM,TTF=F&region=US&lang=en-US", "Energy"),
        ("https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^GDAXI,^FTSEMIB&region=US&lang=en-US", "Macro/Equity"),
    ]
    for url, cat in feeds:
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                tree = ET.parse(r)
            for item in tree.findall(".//item")[:5]:
                headlines.append({
                    "title":       item.findtext("title") or "",
                    "link":        item.findtext("link") or "",
                    "source":      item.findtext("source") or "Yahoo Finance",
                    "date":        item.findtext("pubDate") or "",
                    "description": (item.findtext("description") or "")[:300],
                    "category":    cat,
                })
        except Exception as e:
            print(f"  News {cat} error: {e}")
    return headlines

print("Fetching news...")
news = get_news()

# ============ FINAL OUTPUT ============
data = {
    "updated": datetime.datetime.utcnow().strftime("%d %b %Y %H:%M UTC"),
    "references": {
        "mtd": mtd_ref.strftime("%d %b %Y"),
        "qtd": qtd_ref.strftime("%d %b %Y"),
        "ytd": ytd_ref.strftime("%d %b %Y"),
        "2y":  two_y_ref.strftime("%d %b %Y"),
    },
    "patrimony": patrimony,
    "sections": {
        "fx":      section_data("fx"),
        "indices": section_data("indices"),
        "energy":  section_data("energy"),
        "crypto":  section_data("crypto"),
        "rates":   section_data("rates"),
    },
    "news": news,
}

brent = instruments.get("BZ=F", {}).get("raw_current")
wti   = instruments.get("CL=F", {}).get("raw_current")
if brent and wti:
    data["sections"]["energy"]["instruments"].append({
        "symbol": "SPREAD",
        "label": "Brent − WTI",
        "section": "energy",
        "decimals": 2,
        "current": round(brent - wti, 2),
        "changes": {"1D": None, "MTD": None, "QTD": None, "YTD": None, "2Y": None},
    })

with open("data.json", "w") as f:
    json.dump(data, f, indent=2, default=str)

print(f"Done — {len(instruments)} instruments, {len(news)} headlines, patrimony: €{patrimony['current_eur']:,}" if patrimony else "Done — patrimony failed")
