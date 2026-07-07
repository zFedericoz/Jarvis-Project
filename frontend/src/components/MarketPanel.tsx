import { memo, useState, useEffect, useRef, useCallback } from "react";
import { C, mono } from "../utils/theme";
import { API_URL } from "../utils/constants";
import { fetchWithAuth } from "../utils/fetch";

const DOCKER_API = "";
const STORAGE_KEY = "jarvis_watchlist";
const DEFAULT_WATCHLIST = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOGL", "BTC-USD", "ETH-USD", "^GSPC"];

function loadWatchlist(): string[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : DEFAULT_WATCHLIST;
  } catch { return DEFAULT_WATCHLIST; }
}

function saveWatchlist(list: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

const PERIODS = [
  { label: "1 giorno", period: "1d", interval: "5m" },
  { label: "5 giorni", period: "5d", interval: "30m" },
  { label: "1 mese", period: "1mo", interval: "1d" },
  { label: "6 mesi", period: "6mo", interval: "1wk" },
  { label: "YTD", period: "ytd", interval: "1wk" },
  { label: "1 anno", period: "1y", interval: "1wk" },
  { label: "5 anni", period: "5y", interval: "1mo" },
  { label: "MAX", period: "max", interval: "3mo" },
];

interface Quote { symbol: string; name: string; price: number; change: number; change_pct: number; currency: string; }
interface HistoryPoint { t: number; o: number | null; h: number | null; l: number | null; c: number; v: number; }
interface NewsItem { title: string; publisher: string; link: string; summary: string; time: string; }

function formatTime(ts: number, period: string): string {
  const d = new Date(ts * 1000);
  if (period === "1d") return d.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
  if (period === "5d" || period === "1mo") return d.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
  if (period === "6mo" || period === "ytd" || period === "1y") return d.toLocaleDateString("it-IT", { month: "short", year: "numeric" });
  return d.getFullYear().toString();
}

function niceTicks(min: number, max: number, count: number): number[] {
  const range = max - min || 1;
  const roughStep = range / (count - 1);
  const magnitude = Math.pow(10, Math.floor(Math.log10(roughStep)));
  const residual = roughStep / magnitude;
  let niceStep = residual <= 1.5 ? 1 : residual <= 3 ? 2 : residual <= 7 ? 5 : 10;
  niceStep *= magnitude;
  const niceMin = Math.floor(min / niceStep) * niceStep;
  const niceMax = Math.ceil(max / niceStep) * niceStep;
  const ticks: number[] = [];
  for (let v = niceMin; v <= niceMax + niceStep * 0.001; v += niceStep) ticks.push(v);
  return ticks;
}

function PriceChart({ symbol, color }: { symbol: string; color: string }) {
  const [period, setPeriod] = useState("1mo");
  const [data, setData] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null!);
  const [mouseX, setMouseX] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null!);

  useEffect(() => {
    setLoading(true);
    const pi = PERIODS.find(p => p.period === period) || PERIODS[3];
    fetchWithAuth(`${DOCKER_API}/api/market/history?symbol=${symbol}&period=${period}&interval=${pi.interval}`)
      .then(r => r.json())
      .then(d => { if (Array.isArray(d)) setData(d); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [symbol, period]);

  const sizeCanvas = useCallback(() => {
    const c = canvasRef.current;
    if (!c) return;
    const rect = c.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = rect.width * dpr;
    c.height = rect.height * dpr;
  }, []);

  useEffect(() => {
    sizeCanvas();
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(sizeCanvas);
    ro.observe(el);
    return () => ro.disconnect();
  }, [sizeCanvas]);

  const draw = useCallback(() => {
    const c = canvasRef.current;
    if (!c || data.length === 0) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const W = c.width, H = c.height;

    const yLabelW = 50 * dpr;
    const pad = { top: 12 * dpr, bottom: 22 * dpr, left: yLabelW + 4 * dpr, right: 8 * dpr };
    const chartW = W - pad.left - pad.right;
    const chartH = H - pad.top - pad.bottom;

    ctx.clearRect(0, 0, W, H);

    const validData = data.filter(d => d.c !== null);
    if (validData.length === 0) return;
    const prices = validData.map(d => d.c);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    const ticks = niceTicks(min, max, 5);
    const tickMin = ticks[0], tickMax = ticks[ticks.length - 1];
    const tickRange = tickMax - tickMin || 1;

    ctx.font = `${9 * dpr}px ` + mono;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    for (const t of ticks) {
      const y = pad.top + chartH - ((t - tickMin) / tickRange) * chartH;
      ctx.fillStyle = C.textFaint;
      ctx.fillText(`$${t.toFixed(2)}`, pad.left - 3 * dpr, y);
      ctx.strokeStyle = `${C.border}44`;
      ctx.lineWidth = 0.5 * dpr;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(pad.left + chartW, y);
      ctx.stroke();
    }

    const xLabelCount = Math.min(6, validData.length);
    const xStep = Math.max(1, Math.floor((validData.length - 1) / (xLabelCount - 1)));
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (let i = 0; i < validData.length; i += xStep) {
      const x = pad.left + (i / (validData.length - 1)) * chartW;
      const label = formatTime(validData[i].t, period);
      ctx.fillStyle = C.textFaint;
      ctx.font = `${9 * dpr}px ` + mono;
      ctx.fillText(label, x, pad.top + chartH + 4 * dpr);
      ctx.strokeStyle = `${C.border}33`;
      ctx.lineWidth = 0.5 * dpr;
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, pad.top + chartH);
      ctx.stroke();
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5 * dpr;
    ctx.beginPath();
    for (let i = 0; i < validData.length; i++) {
      const x = pad.left + (i / (validData.length - 1)) * chartW;
      const y = pad.top + chartH - ((validData[i].c - tickMin) / tickRange) * chartH;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    }
    ctx.stroke();

    const grad = ctx.createLinearGradient(0, pad.top, 0, pad.top + chartH);
    grad.addColorStop(0, `${color}44`);
    grad.addColorStop(1, `${color}04`);
    ctx.lineTo(pad.left + chartW, pad.top + chartH);
    ctx.lineTo(pad.left, pad.top + chartH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    if (mouseX !== null && validData.length > 0) {
      const rect = c.getBoundingClientRect();
      const cssW = rect.width;
      const scaleX = W / cssW;
      const canvasX = mouseX * scaleX;
      const idx = Math.round(((canvasX - pad.left) / chartW) * (validData.length - 1));
      const clamped = Math.max(0, Math.min(validData.length - 1, idx));
      const point = validData[clamped];
      const x = pad.left + (clamped / (validData.length - 1)) * chartW;
      const y = pad.top + chartH - ((point.c - tickMin) / tickRange) * chartH;

      ctx.strokeStyle = `${color}66`;
      ctx.lineWidth = 1 * dpr;
      ctx.setLineDash([2 * dpr, 2 * dpr]);
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, pad.top + chartH);
      ctx.stroke();
      ctx.setLineDash([]);

      ctx.font = `bold ${10 * dpr}px ` + mono;
      const timeLabel = formatTime(point.t, period);
      const label = `$${point.c.toFixed(2)}  ${timeLabel}`;
      const labelW = ctx.measureText(label).width + 12 * dpr;
      const labelH = 20 * dpr;
      const labelX = Math.max(pad.left, Math.min(x - labelW / 2, pad.left + chartW - labelW));

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.roundRect(labelX, pad.top - labelH / 2, labelW, labelH, 3 * dpr);
      ctx.fill();

      ctx.fillStyle = "#000";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(label, labelX + labelW / 2, pad.top);

      // time shown in badge above
    }
  }, [data, mouseX, color, period]);

  useEffect(() => { draw(); }, [draw]);

  const handleMouse = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (rect) setMouseX(e.clientX - rect.left);
  };

  const firstPoint = data.length > 0 ? data[0] : null;
  const lastPoint = data.length > 0 ? data[data.length - 1] : null;
  const highPoint = data.length > 0 ? data.reduce((a, b) => (b.h !== null && b.h > (a.h ?? -Infinity)) ? b : a) : null;
  const lowPoint = data.length > 0 ? data.reduce((a, b) => (b.l !== null && b.l < (a.l ?? Infinity)) ? b : a) : null;

  const openPrice = firstPoint?.o ?? firstPoint?.c;
  const closePrice = lastPoint?.c;
  const highPrice = highPoint?.h;
  const lowPrice = lowPoint?.l;
  const change = closePrice && openPrice ? closePrice - openPrice : null;
  const changePct = closePrice && openPrice ? (change! / openPrice) * 100 : null;
  const isUp = change !== null && change >= 0;

  return (
    <div ref={containerRef} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", flexShrink: 0 }}>
        {PERIODS.map(p => (
          <button key={p.period} onClick={() => setPeriod(p.period)}
            style={{
              fontSize: 10, fontFamily: mono, background: period === p.period ? `${color}22` : "transparent",
              border: `1px solid ${period === p.period ? color : C.border}`, color: period === p.period ? color : C.textDim,
              borderRadius: 3, padding: "2px 8px", cursor: "pointer",
            }}>{p.label}</button>
        ))}
        {loading && <span style={{ fontSize: 10, color: C.textFaint, marginLeft: 4 }}>...</span>}
      </div>
      <div style={{ position: "relative" }}>
        <canvas ref={canvasRef}
          onMouseMove={handleMouse} onMouseLeave={() => setMouseX(null)}
          style={{ display: "block", width: "100%", height: 260, cursor: "crosshair", borderRadius: 2, background: "rgba(0,0,0,0.15)" }} />
      </div>
      {lastPoint && (
        <div style={{ flexShrink: 0, display: "flex", gap: 12, padding: "4px 8px", borderTop: `1px solid ${C.border}`, fontSize: 11, fontFamily: mono, color: C.text }}>
          <span>Apertura <strong style={{ color: C.textDim }}>${openPrice?.toFixed(2)}</strong></span>
          <span>Massimo <strong style={{ color: C.green }}>${highPrice?.toFixed(2)}</strong></span>
          <span>Minimo <strong style={{ color: C.red }}>${lowPrice?.toFixed(2)}</strong></span>
          <span>Chiusura <strong style={{ color: C.textDim }}>${closePrice?.toFixed(2)}</strong></span>
          <span>Variazione <strong style={{ color: isUp ? C.green : C.red }}>
            {isUp ? "+" : ""}{change?.toFixed(2)} ({isUp ? "+" : ""}{changePct?.toFixed(2)}%)
          </strong></span>
        </div>
      )}
    </div>
  );
}

function SymbolSearch({ onAdd }: { onAdd: (sym: string) => void }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ symbol: string; name: string; exchange: string }[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (query.length < 1) { setResults([]); return; }
    const t = setTimeout(() => {
      fetchWithAuth(`${DOCKER_API}/api/market/search?q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(d => { if (Array.isArray(d)) setResults(d.slice(0, 6)); })
        .catch(() => {});
    }, 300);
    return () => clearTimeout(t);
  }, [query]);

  return (
    <div style={{ position: "relative" }}>
      <input value={query} onChange={e => { setQuery(e.target.value); setOpen(true); }}
        placeholder="Cerca simbolo..."
        style={{ width: "100%", background: "rgba(0,0,0,0.2)", border: `1px solid ${C.border}`, color: C.text,
          fontSize: 12, padding: "4px 8px", outline: "none", borderRadius: 3, fontFamily: mono, boxSizing: "border-box" }} />
      {open && results.length > 0 && (
        <div style={{ position: "absolute", top: "100%", left: 0, right: 0, background: C.bgPanel,
          border: `1px solid ${C.border}`, borderRadius: 3, zIndex: 100, maxHeight: 180, overflow: "auto" }}>
          {results.map(r => (
            <div key={r.symbol} onClick={() => { onAdd(r.symbol); setQuery(""); setResults([]); setOpen(false); }}
              style={{ padding: "4px 8px", cursor: "pointer", fontSize: 11, fontFamily: mono,
                borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: C.cyan }}>{r.symbol}</span>
              <span style={{ color: C.textDim, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginLeft: 8, flex: 1 }}>{r.name}</span>
              <span style={{ color: C.textFaint, fontSize: 9 }}>{r.exchange}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MiniSparkline({ symbol }: { symbol: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null!);
  useEffect(() => {
    fetchWithAuth(`${DOCKER_API}/api/market/history?symbol=${symbol}&period=1mo&interval=1d`)
      .then(r => r.json())
      .then(data => {
        if (!Array.isArray(data) || data.length < 2) return;
        const c = canvasRef.current;
        if (!c) return;
        const ctx = c.getContext("2d");
        if (!ctx) return;
        const prices = data.filter(d => d.c !== null).map(d => d.c);
        const min = Math.min(...prices), max = Math.max(...prices), range = max - min || 1;
        const startPrice = prices[0], endPrice = prices[prices.length - 1];
        const color = endPrice >= startPrice ? C.green : C.red;
        ctx.clearRect(0, 0, c.width, c.height);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        for (let i = 0; i < prices.length; i++) {
          const x = (i / (prices.length - 1)) * c.width;
          const y = c.height - ((prices[i] - min) / range) * c.height;
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
      })
      .catch(() => {});
  }, [symbol]);
  return <canvas ref={canvasRef} width={60} height={20} style={{ display: "block", width: 60, height: 20, flexShrink: 0 }} />;
}

export const MarketPanel = memo(function MarketPanel() {
  const [watchlist, setWatchlist] = useState<string[]>(loadWatchlist);
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [selected, setSelected] = useState<string>(watchlist[0] || "AAPL");
  const [news, setNews] = useState<NewsItem[]>([]);

  const addSymbol = (sym: string) => {
    const upper = sym.toUpperCase();
    if (!watchlist.includes(upper)) {
      const next = [...watchlist, upper];
      setWatchlist(next);
      saveWatchlist(next);
    }
    setSelected(upper);
  };

  const removeSymbol = (sym: string) => {
    const next = watchlist.filter(s => s !== sym);
    setWatchlist(next);
    saveWatchlist(next);
    if (selected === sym) setSelected(next[0] || "AAPL");
  };

  useEffect(() => {
    if (watchlist.length === 0) return;
    const fetchAll = async () => {
      const results: Record<string, Quote> = {};
      await Promise.all(watchlist.map(async sym => {
        try {
          const r = await fetchWithAuth(`${DOCKER_API}/api/market/quote?symbol=${encodeURIComponent(sym)}`);
          if (r.ok) {
            const d = await r.json();
            if (d.symbol) results[sym] = d;
          }
        } catch {}
      }));
      setQuotes(results);
    };
    fetchAll();
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, [watchlist]);

  useEffect(() => {
    if (!selected) return;
    fetchWithAuth(`${DOCKER_API}/api/market/news?symbol=${encodeURIComponent(selected)}`)
      .then(r => r.json())
      .then(d => { if (Array.isArray(d)) setNews(d.slice(0, 5)); })
      .catch(() => {});
  }, [selected]);

  const selQuote = quotes[selected];

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", gap: 6, padding: "4px 6px", overflow: "hidden" }}>
      <div style={{ flexShrink: 0 }}>
        <SymbolSearch onAdd={addSymbol} />
      </div>

      {watchlist.length === 0 ? (
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: C.textDim, fontFamily: mono, fontSize: 12 }}>
          Cerca un simbolo per iniziare
        </div>
      ) : (
      <div style={{ display: "flex", gap: 6, minHeight: 0, flex: 1, overflow: "hidden" }}>
        <div style={{ width: 180, flexShrink: 0, display: "flex", flexDirection: "column", gap: 2, overflow: "auto" }}>
          {watchlist.map(sym => {
            const q = quotes[sym];
            const pct = q?.change_pct;
            const isUp = pct !== undefined && pct >= 0;
            const isSelected = selected === sym;
            return (
              <div key={sym} onClick={() => setSelected(sym)}
                style={{
                  display: "flex", alignItems: "center", gap: 4, padding: "4px 6px", borderRadius: 3,
                  cursor: "pointer", background: isSelected ? `${C.cyanFaint}` : "transparent",
                  border: isSelected ? `1px solid ${C.border}` : "1px solid transparent",
                }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 11, fontFamily: mono, color: C.text }}>{sym}</div>
                  <div style={{ fontSize: 10, color: C.textFaint }}>
                    {q ? `$${q.price ?? "—"}` : "..."}
                    {pct !== undefined && (
                      <span style={{ color: isUp ? C.green : C.red, marginLeft: 4 }}>
                        {isUp ? "+" : ""}{pct.toFixed(1)}%
                      </span>
                    )}
                  </div>
                </div>
                <MiniSparkline symbol={sym} />
                <span onClick={e => { e.stopPropagation(); removeSymbol(sym); }}
                  style={{ color: C.textFaint, cursor: "pointer", fontSize: 10, padding: 2 }}>✕</span>
              </div>
            );
          })}
        </div>

        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
          {selQuote && (
            <div style={{ flexShrink: 0, display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontFamily: mono, fontSize: 13, color: C.text }}>{selQuote.name}</span>
              <span style={{ fontFamily: mono, fontSize: 22, fontWeight: "bold", color: C.text }}>
                ${selQuote.price}
              </span>
              {selQuote.change_pct !== null && (
                <span style={{ fontFamily: mono, fontSize: 13, color: selQuote.change_pct >= 0 ? C.green : C.red }}>
                  {selQuote.change_pct >= 0 ? "+" : ""}{selQuote.change_pct.toFixed(2)}%
                </span>
              )}
              <span style={{ fontFamily: mono, fontSize: 10, color: C.textFaint }}>{selQuote.currency} · {selQuote.symbol}</span>
            </div>
          )}
          <div style={{ flex: 1, minHeight: 0 }}>
            <PriceChart symbol={selected} color={C.cyan} />
          </div>
          {news.length > 0 && (
            <div style={{ flexShrink: 0, overflow: "auto", borderTop: `1px solid ${C.border}`, paddingTop: 4, resize: "vertical", minHeight: 40, maxHeight: 200 }}>
              <div style={{ fontSize: 9, fontFamily: mono, color: C.textDim, letterSpacing: "0.1em", marginBottom: 2 }}>▸ NOTIZIE</div>
              {news.map((n, i) => (
                <a key={i} href={n.link} target="_blank" rel="noopener noreferrer"
                  style={{ display: "block", fontSize: 10, color: C.text, textDecoration: "none", padding: "2px 0", lineHeight: 1.3 }}>
                  <span style={{ color: C.cyan }}>[{n.time}]</span> {n.title}
                  <span style={{ color: C.textFaint, marginLeft: 4 }}>— {n.publisher}</span>
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  );
});
