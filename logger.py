from __future__ import annotations
import json, logging, sqlite3, threading
from typing import Optional
from utils import to_db_ts, utcnow
logger = logging.getLogger(__name__)
SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (id INTEGER PRIMARY KEY AUTOINCREMENT, ts_utc TEXT, pair TEXT, direction TEXT, confidence INTEGER, entry REAL, sl REAL, tp1 REAL, tp2 REAL, rr_tp1 REAL, rr_tp2 REAL, status TEXT DEFAULT 'PENDING', result_pips REAL DEFAULT 0, result_r REAL DEFAULT 0, news_bias TEXT, reasoning TEXT, valid_until TEXT, raw_json TEXT);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts_utc);
CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT);
"""
class Database:
    def __init__(self, path: str):
        self._lock = threading.Lock(); self.conn = sqlite3.connect(path, check_same_thread=False); self.conn.row_factory = sqlite3.Row
        with self._lock: self.conn.executescript(SCHEMA); self.conn.commit()
    def log_signal(self, sig: dict) -> int:
        with self._lock:
            c = self.conn.execute("INSERT INTO signals (ts_utc, pair, direction, confidence, entry, sl, tp1, tp2, rr_tp1, rr_tp2, status, news_bias, reasoning, valid_until, raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,'PENDING',?,?,?,?)", (to_db_ts(sig.get("timestamp_utc")), sig["pair"], sig["direction"], int(sig["confidence"]), sig.get("entry"), sig.get("sl"), sig.get("tp1"), sig.get("tp2"), sig.get("risk_reward_tp1"), sig.get("risk_reward_tp2"), sig.get("news_bias", "Neutral"), sig.get("reasoning", ""), to_db_ts(sig.get("valid_until")), json.dumps(sig)))
            self.conn.commit(); return int(c.lastrowid)
    def update_status(self, sid: int, st: str, pips: Optional[float] = None, r: Optional[float] = None) -> None:
        with self._lock: self.conn.execute("UPDATE signals SET status=?, result_pips=COALESCE(?, result_pips), result_r=COALESCE(?, result_r) WHERE id=?", (st, pips, r, sid)); self.conn.commit()
    def get_open_signals(self) -> list[dict]:
        with self._lock: return [dict(x) for x in self.conn.execute("SELECT * FROM signals WHERE status IN ('PENDING', 'ACTIVE') AND julianday(valid_until) > julianday('now', '-2 hours') ORDER BY id ASC").fetchall()]
    def count_signals_today(self) -> int:
        with self._lock: return int(self.conn.execute("SELECT COUNT(*) AS n FROM signals WHERE date(ts_utc) = date('now')").fetchone()["n"])
    def open_trades_count(self) -> int:
        with self._lock: return int(self.conn.execute("SELECT COUNT(*) AS n FROM signals WHERE status IN ('PENDING', 'ACTIVE')").fetchone()["n"])
    def daily_realized_r(self) -> float:
        with self._lock: return float(self.conn.execute("SELECT COALESCE(SUM(result_r), 0) AS r FROM signals WHERE date(ts_utc) = date('now') AND status IN ('TP1', 'TP2', 'SL')").fetchone()["r"])
    def recent_pair_signal(self, pair: str, h: int = 2) -> Optional[dict]:
        with self._lock:
            r = self.conn.execute("SELECT * FROM signals WHERE pair = ? AND julianday(ts_utc) >= julianday('now', ?) ORDER BY id DESC LIMIT 1", (pair, f"-{h} hours")).fetchone()
            return dict(r) if r else None
    def get_stats(self, d: Optional[int] = None) -> dict:
        with self._lock:
            if d: rs = self.conn.execute("SELECT * FROM signals WHERE julianday(ts_utc) >= julianday('now', ?)", (f"-{d} days",)).fetchall()
            else: rs = self.conn.execute("SELECT * FROM signals").fetchall()
        rec = [dict(x) for x in rs]; c = {k: 0 for k in ("TP1", "TP2", "SL", "EXPIRED", "CANCELLED", "PENDING", "ACTIVE")}
        for r in rec: c[r["status"]] = c.get(r["status"], 0) + 1
        w, l = c["TP1"] + c["TP2"], c["SL"]; cl = w + l
        p = [float(r.get("result_pips") or 0) for r in rec if r.get("result_pips")]; rv = [float(r.get("result_r") or 0) for r in rec if r.get("result_r")]
        gw, gl = sum(x for x in p if x > 0), abs(sum(x for x in p if x < 0))
        return {"total": len(rec), "closed": cl, "wins": w, "losses": l, "tp1": c["TP1"], "tp2": c["TP2"], "sl": c["SL"], "expired": c["EXPIRED"], "cancelled": c["CANCELLED"], "pending": c["PENDING"]+c["ACTIVE"], "winrate": (w/cl*100) if cl else 0.0, "total_pips": sum(p), "profit_factor": (gw/gl) if gl > 0 else 0.0, "avg_r": sum(rv)/len(rv) if rv else 0.0}
    def can_trade(self, s) -> tuple[bool, str]:
        if self.is_paused(): return False, "Jeda."
        if self.count_signals_today() >= s.max_signals_per_day: return False, "Limit harian."
        if self.open_trades_count() >= s.max_open_trades: return False, "Limit open."
        if self.daily_realized_r() <= -(s.max_daily_loss_pct / max(s.risk_percent, 0.1)): return False, "Max loss."
        return True, "OK"
    def set_state(self, k: str, v: str) -> None:
        with self._lock: self.conn.execute("INSERT INTO state(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v)); self.conn.commit()
    def get_state(self, k: str, d: str = "") -> str:
        with self._lock:
            r = self.conn.execute("SELECT value FROM state WHERE key = ?", (k,)).fetchone(); return r["value"] if r else d
    def set_paused(self, p: bool) -> None: self.set_state("paused", "1" if p else "0")
    def is_paused(self) -> bool: return self.get_state("paused", "0") == "1"
