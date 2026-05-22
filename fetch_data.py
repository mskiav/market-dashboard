import yfinance as yf
import json
import datetime

def fmt(v, dec=2):
    if v is None:
        return None
    try:
        return round(float(v), dec)
    except:
        return None

def get_quotes(symbols):
    result = []
    try:
        tickers = yf.Tickers(" ".join(symbols))
        for sym in symbols:
            try:
                t = tickers.tickers[sym]
                info = t.fast_info
                price = fmt(info.last_price)
                prev  = fmt(info.previous_close)
                chg   = fmt(((price - prev) / prev * 100) if price and prev else 0)
                result.append({"symbol": sym, "price": price, "change1d": chg})
            except Exception as e:
                print(f"  Warning {sym}: {e}")
                result.append({"symbol": sym, "price": None, "change1d": 0})
    except Exception as e:
        print(f"get_quotes error: {e}")
    return result

def get_chart(sym, period="1y", interval="1mo"):
    try:
        t = yf.Ticker(sym)
        hist = t.history(period=period, interval=interval)
        if hist.empty:
            return None
        closes = [fmt(v) for v in hist["Close"].tolist()]
        labels = [d.strftime("%b %y") for d in hist.index.to_pydatetime()]
        valid  = [v for v in closes if v is not None]
        chg1y  = fmt(((valid[-1] - valid[0]) / valid[0] * 100) if len(valid) >= 2 else 0, 1)
        return {"labels": labels, "values": closes, "change1y": chg1y}
    except Exception as e:
        print(f"  Chart error {sym}: {e}")
        return None

def get_fx_ecb():
    import urllib.request
    try:
        url = "https://api.frankfurter.app/latest?from=EUR&symbols=CHF,USD,GBP"
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read())
        rates = d.get("rates", {})
        return {
            "CHFEUR": fmt(1/rates["CHF"], 4) if rates.get("CHF") else None,
            "USDEUR": fmt(1/rates["USD"], 4) if rates.get("USD") else None,
            "GBPEUR": fmt(1/rates["GBP"], 4) if rates.get("GBP") else None,
        }
    except Exception as e:
        print(f"  ECB FX error: {e}")
        return {}

def get_news():
    import urllib.request
    from xml.etree import ElementTree as ET
    headlines = []
    try:
        url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BZ=F,CL=F,XOM,TTF=F&region=US&lang=en-US"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            tree = ET.parse(r)
        for item in tree.findall(".//item")[:6]:
            title  = item.findtext("title") or ""
            source = item.findtext("source") or "Yahoo Finance"
            date   = item.findtext("pubDate") or ""
            headlines.append({"title": title, "source": source, "date": date})
    except Exception as e:
        print(f"  News error: {e}")
    return headlines

print("Fetching FX (ECB)...")
fx_ecb = get_fx_ecb()

fx_symbols  = ["CHFEUR=X", "EURUSD=X", "GBPEUR=X"]
idx_symbols = ["^GSPC","^IXIC","^STOXX50E","^FTSEMIB","^GDAXI","^FCHI","^SSMI","^FTSE","^N225","^HSI","000300.SS"]
en_symbols  = ["BZ=F","CL=F","TTF=F","NG=F"]
cr_symbols  = ["GC=F","SI=F","BTC-EUR","ETH-EUR"]

print("Fetching quotes...")
all_quotes = get_quotes(fx_symbols + idx_symbols + en_symbols + cr_symbols)

def q(sym):
    return next((x for x in all_quotes if x["symbol"] == sym), {"symbol": sym, "price": None, "change1d": 0})

brent  = q("BZ=F")["price"]
wti    = q("CL=F")["price"]
spread = fmt(brent - wti) if brent and wti else None

labels = {
    "CHFEUR=X":"CHF/EUR","EURUSD=X":"USD/EUR","GBPEUR=X":"GBP/EUR",
    "^GSPC":"S&P 500","^IXIC":"Nasdaq","^STOXX50E":"EuroStoxx 50",
    "^FTSEMIB":"FTSE MIB","^GDAXI":"DAX","^FCHI":"CAC 40",
    "^SSMI":"SMI","^FTSE":"FTSE 100","^N225":"Nikkei 225",
    "^HSI":"Hang Seng","000300.SS":"CSI 300",
    "BZ=F":"Brent USD/bbl","CL=F":"WTI USD/bbl",
    "TTF=F":"TTF EUR/MWh","NG=F":"Nat Gas USD",
    "GC=F":"Gold USD/oz","SI=F":"Silver USD/oz",
    "BTC-EUR":"Bitcoin EUR","ETH-EUR":"Ethereum EUR"
}

def price_fmt(sym, price):
    if price is None:
        return "—"
    if sym in ("BTC-EUR","ETH-EUR","GC=F","^GSPC","^IXIC","^FTSEMIB","^GDAXI","^N225","^HSI","000300.SS","^STOXX50E","^FCHI","^SSMI","^FTSE"):
        return f"{price:,.0f}"
    if sym in ("CHFEUR=X","EURUSD=X","GBPEUR=X"):
        return f"{price:.4f}"
    return f"{price:.2f}"

def make_tiles(syms):
    tiles = []
    for sym in syms:
        d = q(sym)
        price = d["price"]
        if sym == "CHFEUR=X" and fx_ecb.get("CHFEUR"):
            price = fx_ecb["CHFEUR"]
        elif sym == "EURUSD=X" and fx_ecb.get("USDEUR"):
            price = fx_ecb["USDEUR"]
        elif sym == "GBPEUR=X" and fx_ecb.get("GBPEUR"):
            price = fx_ecb["GBPEUR"]
        tiles.append({
            "label": labels.get(sym, sym),
            "value": price_fmt(sym, price),
            "change1d": d["change1d"] or 0
        })
    return tiles

print("Building charts...")
chart_defs = [
    ("CHFEUR=X","CHF/EUR 1Y"),("EURUSD=X","USD/EUR 1Y"),
    ("BZ=F","Brent 1Y"),("CL=F","WTI 1Y"),
    ("^GSPC","S&P 500 1Y"),("^GDAXI","DAX 1Y"),
    ("^FTSEMIB","FTSE MIB 1Y"),("GC=F","Gold 1Y"),
    ("BTC-EUR","Bitcoin EUR 1Y"),
]
charts = []
for sym, lbl in chart_defs:
    print(f"  chart: {sym}")
    c = get_chart(sym)
    if c:
        c["label"] = lbl
        charts.append(c)

print("Fetching news...")
news = get_news()

data = {
    "updated": datetime.datetime.utcnow().strftime("%d %b %Y %H:%M UTC"),
    "fx":      make_tiles(fx_symbols),
    "indices": make_tiles(idx_symbols),
    "energy":  make_tiles(en_symbols) + [{"label":"Brent−WTI spread","value": f"{spread:.2f} USD" if spread else "—","change1d":0}],
    "crypto":  make_tiles(cr_symbols),
    "charts":  charts,
    "news":    news,
}

with open("data.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"Done — data.json written ({len(news)} headlines, {len(charts)} charts)")
