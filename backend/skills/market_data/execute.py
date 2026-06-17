import logging, json, requests
from datetime import datetime

logger = logging.getLogger("jarvis.skills.market_data")

YF_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
YF_SEARCH = "https://query1.finance.yahoo.com/v1/finance/search"
CG_BASE = "https://api.coingecko.com/api/v3"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})

_CRYPTO_IDS = {
    "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana", "XRP": "ripple",
    "ADA": "cardano", "DOT": "polkadot", "DOGE": "dogecoin", "AVAX": "avalanche-2",
    "LINK": "chainlink", "MATIC": "matic-network", "UNI": "uniswap",
    "ATOM": "cosmos", "LTC": "litecoin", "BCH": "bitcoin-cash", "XLM": "stellar",
}


def _is_crypto(symbol: str) -> bool:
    return symbol.upper().endswith("-USD") and symbol.upper().split("-")[0] in _CRYPTO_IDS


def _fetch_yahoo_json(url: str, params: dict) -> dict | None:
    try:
        r = SESSION.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        logger.warning(f"Yahoo HTTP {r.status_code} per {url}")
    except Exception as e:
        logger.warning(f"Yahoo error: {e}")
    return None


def _quote_yahoo(symbol: str) -> dict:
    data = _fetch_yahoo_json(f"{YF_BASE}/{symbol}", {"range": "5d", "interval": "1d"})
    if not data or "chart" not in data or not data["chart"].get("result"):
        return {"error": f"Nessun dato per {symbol}"}
    result = data["chart"]["result"][0]
    meta = result.get("meta", {})
    quotes = result.get("indicators", {}).get("quote", [{}])[0]
    closes = quotes.get("close", [])
    opens = quotes.get("open", [])
    current = (closes or [None])[-1]
    prev_close = meta.get("chartPreviousClose") or (closes[-2] if len(closes) > 1 else current)
    change = (current - prev_close) if (current and prev_close) else 0
    change_pct = (change / prev_close * 100) if prev_close else 0
    ts = result.get("timestamp", [])
    date_str = datetime.fromtimestamp(ts[-1]).strftime("%Y-%m-%d %H:%M") if ts else ""
    return {
        "symbol": symbol.upper(),
        "name": meta.get("shortName", meta.get("longName", "")),
        "price": round(current, 2) if current else None,
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "prev_close": round(prev_close, 2) if prev_close else None,
        "currency": meta.get("currency", "USD"),
        "market": meta.get("exchangeName", ""),
        "volume": int(quotes.get("volume", [0])[-1] or 0) if quotes.get("volume") else 0,
        "high": round(quotes.get("high", [None])[-1], 2) if quotes.get("high") and quotes["high"][-1] else None,
        "low": round(quotes.get("low", [None])[-1], 2) if quotes.get("low") and quotes["low"][-1] else None,
        "timestamp": date_str,
    }


def _quote_crypto(symbol: str) -> dict:
    coin_id = _CRYPTO_IDS.get(symbol.upper().split("-")[0], symbol.upper().split("-")[0].lower())
    try:
        r = SESSION.get(f"{CG_BASE}/simple/price", params={
            "ids": coin_id, "vs_currencies": "usd",
            "include_24hr_vol": "true", "include_24hr_change": "true",
        }, timeout=10)
        if r.status_code == 200:
            data = r.json().get(coin_id, {})
            price = data.get("usd")
            change_pct = data.get("usd_24h_change")
            return {
                "symbol": symbol.upper(),
                "name": coin_id.capitalize(),
                "price": price,
                "change": None,
                "change_pct": round(change_pct, 2) if change_pct else None,
                "currency": "USD",
                "market": "CoinGecko",
                "volume": data.get("usd_24h_vol"),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
    except Exception as e:
        logger.warning(f"CoinGecko error: {e}")
    return _quote_yahoo(symbol)


def _history_yahoo(symbol: str, period: str = "1mo", interval: str = "1d") -> list:
    data = _fetch_yahoo_json(f"{YF_BASE}/{symbol}", {"range": period, "interval": interval})
    if not data or not data["chart"].get("result"):
        return []
    result = data["chart"]["result"][0]
    ts = result.get("timestamp", [])
    quotes = result.get("indicators", {}).get("quote", [{}])[0]
    opens = quotes.get("open", [])
    highs = quotes.get("high", [])
    lows = quotes.get("low", [])
    closes = quotes.get("close", [])
    volumes = quotes.get("volume", [])
    out = []
    for i in range(len(ts)):
        if closes[i] is not None:
            out.append({
                "t": ts[i],
                "o": round(opens[i], 2) if opens[i] else None,
                "h": round(highs[i], 2) if highs[i] else None,
                "l": round(lows[i], 2) if lows[i] else None,
                "c": round(closes[i], 2),
                "v": int(volumes[i]) if volumes[i] else 0,
            })
    return out


def _search_yahoo(query: str) -> list:
    data = _fetch_yahoo_json(YF_SEARCH, {"q": query, "quotes_count": 8, "news_count": 0})
    if not data:
        return []
    results = []
    for q in data.get("quotes", []):
        if q.get("symbol") and q.get("quoteType") not in ("CRYPTOCURRENCY",):
            results.append({
                "symbol": q["symbol"],
                "name": q.get("shortname", q.get("longname", "")),
                "exchange": q.get("exchange", ""),
                "type": q.get("quoteType", ""),
            })
    return results


def _news_yahoo(symbol: str) -> list:
    data = _fetch_yahoo_json(YF_SEARCH, {"q": symbol, "quotes_count": 0, "news_count": 5})
    if not data:
        return []
    items = []
    for n in data.get("news", []):
        items.append({
            "title": n.get("title", ""),
            "publisher": n.get("publisher", ""),
            "link": n.get("link", ""),
            "summary": n.get("summary", ""),
            "time": datetime.fromtimestamp(n.get("providerPublishTime", 0)).strftime("%Y-%m-%d %H:%M") if n.get("providerPublishTime") else "",
        })
    return items


def execute(action: str, symbol: str = "", query: str = "", period: str = "1mo", interval: str = "1d") -> str:
    try:
        if action == "quote":
            if not symbol:
                return "Simbolo mancante."
            if _is_crypto(symbol):
                data = _quote_crypto(symbol)
            else:
                data = _quote_yahoo(symbol)
            if "error" in data:
                return data["error"]
            pct = data.get("change_pct")
            pct_str = f" ({pct:+.2f}%)" if pct is not None else ""
            return json.dumps(data, ensure_ascii=False)

        elif action == "history":
            if not symbol:
                return "Simbolo mancante."
            hist = _history_yahoo(symbol, period, interval)
            return json.dumps(hist, ensure_ascii=False)

        elif action == "search":
            if not query:
                return "Query di ricerca mancante."
            results = _search_yahoo(query)
            return json.dumps(results, ensure_ascii=False)

        elif action == "news":
            if not symbol:
                return "Simbolo mancante."
            news = _news_yahoo(symbol)
            return json.dumps(news, ensure_ascii=False)

        return f"Azione '{action}' non riconosciuta."
    except Exception as e:
        logger.exception(f"market_data fallita: {e}")
        return f"Errore: {e}"
