from __future__ import annotations
from typing import Optional
import numpy as np, pandas as pd

def ema(s: pd.Series, p: int) -> pd.Series: return s.ewm(span=p, adjust=False).mean()
def sma(s: pd.Series, p: int) -> pd.Series: return s.rolling(p).mean()
def rsi(s: pd.Series, p: int = 14) -> pd.Series:
    d = s.diff(); g = d.clip(lower=0); l = -d.clip(upper=0)
    ag, al = g.ewm(alpha=1/p, adjust=False).mean(), l.ewm(alpha=1/p, adjust=False).mean()
    return 100 - (100 / (1 + ag / al.replace(0, np.nan)))
def macd(s: pd.Series, f: int = 12, sl: int = 26, sig: int = 9):
    l = ema(s, f) - ema(s, sl); s_line = ema(l, sig); return l, s_line, l - s_line
def atr(df: pd.DataFrame, p: int = 14) -> pd.Series:
    tr = pd.concat([df["high"] - df["low"], (df["high"] - df["close"].shift()).abs(), (df["low"] - df["close"].shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/p, adjust=False).mean()
def bollinger(s: pd.Series, p: int = 20, std: float = 2.0):
    m = sma(s, p); sd = s.rolling(p).std(); return m + std * sd, m, m - std * sd
def _last(s: pd.Series, d: float = float("nan")) -> float:
    try: v = s.iloc[-1]; return float(v) if pd.notna(v) else d
    except: return d
def swing_points(df: pd.DataFrame, l: int = 3, r: int = 3):
    h, lw = df["high"].values, df["low"].values; sh, sl = np.zeros(len(df), dtype=bool), np.zeros(len(df), dtype=bool)
    for i in range(l, len(df) - r):
        if h[i] == h[i-l:i+r+1].max(): sh[i] = True
        if lw[i] == lw[i-l:i+r+1].min(): sl[i] = True
    return sh, sl
def last_swings(df: pd.DataFrame, n: int = 4):
    sh, sl = swing_points(df); return df["high"][sh].tail(n).tolist(), df["low"][sl].tail(n).tolist()
def sr_levels(df: pd.DataFrame, lb: int = 200, tol_f: float = 0.5):
    d = df.tail(lb).copy()
    if len(d) < 30:
        p = float(d["close"].iloc[-1]); return {"level": p*0.995, "touches": 0}, {"level": p*1.005, "touches": 0}
    p = float(d["close"].iloc[-1]); a = _last(atr(d), p*0.001); tol = max(a * tol_f, p * 0.0002)
    hs, ls = last_swings(d, 12); c = [(float(x), "res") for x in hs] + [(float(x), "sup") for x in ls]; lvls = []
    for lvl, k in c:
        m = False
        for it in lvls:
            if abs(it["level"] - lvl) <= tol: it["level"] = (it["level"]*it["touches"] + lvl)/(it["touches"]+1); it["touches"] += 1; m = True; break
        if not m: lvls.append({"level": lvl, "touches": 1, "kind": k})
    sups = [x for x in lvls if x["level"] < p]; ress = [x for x in lvls if x["level"] > p]
    s = max(sups, key=lambda x: x["level"]) if sups else {"level": p - 2*a, "touches": 0}
    r = min(ress, key=lambda x: x["level"]) if ress else {"level": p + 2*a, "touches": 0}
    return s, r
def detect_fvg(df: pd.DataFrame, lb: int = 60) -> Optional[dict]:
    d = df.tail(lb)
    for i in range(len(d)-1, 1, -1):
        if d["low"].iloc[i] > d["high"].iloc[i-2]: return {"type": "bullish", "bottom": float(d["high"].iloc[i-2]), "top": float(d["low"].iloc[i])}
        if d["high"].iloc[i] < d["low"].iloc[i-2]: return {"type": "bearish", "bottom": float(d["high"].iloc[i]), "top": float(d["low"].iloc[i-2])}
    return None
def detect_order_block(df: pd.DataFrame, lb: int = 60) -> Optional[dict]:
    d = df.tail(lb)
    for i in range(len(d)-2, 0, -1):
        c, p = d.iloc[i], d.iloc[i-1]
        if c["close"] > p["high"] and p["close"] < p["open"]: return {"type": "bullish", "low": float(p["low"]), "high": float(p["high"])}
        if c["close"] < p["low"] and p["close"] > p["open"]: return {"type": "bearish", "low": float(p["low"]), "high": float(p["high"])}
    return None
def candle_patterns(df: pd.DataFrame) -> list[str]:
    if len(df) < 3: return []
    l, p = df.iloc[-1], df.iloc[-2]; b = abs(l["close"] - l["open"]); uw = l["high"] - max(l["close"], l["open"]); lw = min(l["close"], l["open"]) - l["low"]; pt = []
    if l["close"] > l["open"] and p["close"] < p["open"] and l["close"] >= p["open"] and l["open"] <= p["close"]: pt.append("bullish_engulfing")
    if l["close"] < l["open"] and p["close"] > p["open"] and l["close"] <= p["open"] and l["open"] >= p["close"]: pt.append("bearish_engulfing")
    if b > 0:
        if lw > 2*b and uw < b: pt.append("bullish_pin")
        if uw > 2*b and lw < b: pt.append("bearish_pin")
    return pt
def analyze_timeframe(df: pd.DataFrame, tf: str) -> Optional[dict]:
    if df is None or len(df) < 60: return None
    c = df["close"]; e20, e50, e200 = ema(c, 20), ema(c, 50), ema(c, 200)
    r = rsi(c, 14); ml, ms, mh = macd(c); a = atr(df, 14); bu, bm, bl = bollinger(c, 20, 2.0)
    lc, le20, le50, le200 = _last(c), _last(e20), _last(e50), _last(e200)
    bias = "Neutral"
    if pd.notna(le20) and pd.notna(le50) and pd.notna(le200):
        if lc > le50 and le20 > le50: bias = "Bullish"
        elif lc < le50 and le20 < le50: bias = "Bearish"
    sh, sl = last_swings(df, 4); st = "Ranging"
    if len(sh) >= 2 and len(sl) >= 2:
        if sh[-1] > sh[-2] and sl[-1] > sl[-2]: st = "HH/HL"
        elif sh[-1] < sh[-2] and sl[-1] < sl[-2]: st = "LH/LL"
    s, res = sr_levels(df)
    cds = [{"time": i.isoformat(), "open": float(rw["open"]), "high": float(rw["high"]), "low": float(rw["low"]), "close": float(rw["close"])} for i, rw in df.tail(3).iterrows()]
    return {"tf": tf, "close": lc, "open": float(df["open"].iloc[-1]), "high": float(df["high"].iloc[-1]), "low": float(df["low"].iloc[-1]), "ema20": le20, "ema50": le50, "ema200": le200, "rsi": _last(r), "macd": _last(ml), "macd_signal": _last(ms), "macd_hist": _last(mh), "atr": _last(a), "bb_upper": _last(bu), "bb_mid": _last(bm), "bb_lower": _last(bl), "bias": bias, "structure": st, "swing_highs": [float(x) for x in sh], "swing_lows": [float(x) for x in sl], "support": float(s["level"]), "support_touches": int(s["touches"]), "resistance": float(res["level"]), "resistance_touches": int(res["touches"]), "fvg": detect_fvg(df), "order_block": detect_order_block(df), "patterns": candle_patterns(df), "last_candles": cds}
def trigger_m5(df: pd.DataFrame, d: str) -> bool:
    if df is None or len(df) < 30: return False
    l, p = df.iloc[-1], df.iloc[-2]
    if d == "BUY": return bool((l["close"] > df["high"].iloc[-21:-1].max()) or (l["close"] > l["open"] and p["close"] < p["open"] and l["close"] >= p["open"]))
    return bool((l["close"] < df["low"].iloc[-21:-1].min()) or (l["close"] < l["open"] and p["close"] > p["open"] and l["close"] <= p["open"]))
def build_snapshot(bundle: dict[str, pd.DataFrame]) -> dict:
    sn = {}; k = ("close", "ema20", "ema50", "ema200", "rsi", "macd_hist", "atr", "bb_upper", "bb_lower", "bias", "structure", "support", "support_touches", "resistance", "resistance_touches", "fvg", "order_block", "patterns", "last_candles")
    for tf, df in bundle.items():
        a = analyze_timeframe(df, tf)
        if a: sn[tf] = {x: a[x] for x in k if x in a}
    return sn
def build_candidate(pair: str, bundle: dict[str, pd.DataFrame], nf=None) -> Optional[dict]:
    req = ["D1", "H4", "H1", "M30", "M15", "M5"]; an = {}
    for tf in req:
        a = analyze_timeframe(bundle.get(tf), tf) if bundle.get(tf) is not None else None
        if a is None: return None
        an[tf] = a
    d1, h4, h1, m30, m15, m5 = an["D1"], an["H4"], an["H1"], an["M30"], an["M15"], an["M5"]
    if d1["bias"] == "Neutral" or h4["bias"] == "Neutral": return None
    d = h4["bias"] if h4["bias"] != "Neutral" else d1["bias"]
    c, rs = 0, []
    if h1["bias"] == d: c += 1; rs.append(f"H1 {d}")
    if d == "BUY" and m30["rsi"] < 65: c += 1; rs.append("RSI M30 OK")
    elif d == "SELL" and m30["rsi"] > 35: c += 1; rs.append("RSI M30 OK")
    if d == "BUY" and m30["macd_hist"] > 0: c += 1; rs.append("MACD M30 +")
    elif d == "SELL" and m30["macd_hist"] < 0: c += 1; rs.append("MACD M30 -")
    if d == "BUY" and m15["close"] > m15["open"]: c += 1; rs.append("M15 Bull")
    elif d == "SELL" and m15["close"] < m15["open"]: c += 1; rs.append("M15 Bear")
    if not trigger_m5(bundle["M5"], d): return None
    c += 2; rs.append("M5 Trigger")
    if c < 3: return None
    e = float(m5["close"]); a5 = float(m5["atr"]) if m5["atr"] > 0 else e * 0.0005; m5d = bundle["M5"]
    if d == "BUY":
        s = min(float(m5d["low"].tail(10).min()), e - a5*1.5) - a5*0.2; rk = e - s
        if rk <= 0: return None
        t1 = max(e + rk*1.5, float(m15["resistance"])); t2 = max(e + rk*3.0, float(h1["resistance"]))
    else:
        s = max(float(m5d["high"].tail(10).max()), e + a5*1.5) + a5*0.2; rk = s - e
        if rk <= 0: return None
        t1 = min(e - rk*1.5, float(m15["support"])); t2 = min(e - rk*3.0, float(h1["support"]))
    r1, r2 = rr(e, s, t1), rr(e, s, t2)
    if r1 < 1.2 or r2 < 2.5: return None
    cf = min(95, 65 + c*5)
    nm = {}
    if nf is not None:
        al, rsn, nm = nf.gate(pair, d)
        if not al: return None
    return {"pair": pair, "direction": d, "confidence": cf, "entry": e, "sl": s, "tp1": t1, "tp2": t2, "risk_reward_tp1": r1, "risk_reward_tp2": r2, "tf_alignment": {tf: an[tf]["bias"] for tf in req}, "key_levels": {"support": float(h1["support"]), "resistance": float(h1["resistance"])}, "reasoning": f"Bias {d} dari H4. " + "; ".join(rs) + f". Entry {e:.5f}.", "news_meta": nm}
