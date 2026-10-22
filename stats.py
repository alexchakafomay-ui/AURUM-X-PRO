from __future__ import annotations
import math
def _pf(v: float) -> str: return "∞" if math.isinf(v) else f"{v:.2f}"
def format_stats(s: dict, t: str = "STATISTIK AURUM-X PRO") -> str:
    return f"📊 <b>{t}</b>\n\nTotal sinyal : <b>{s['total']}</b>\nClosed       : <b>{s['closed']}</b>\nTP1 / TP2    : <b>{s['tp1']} / {s['tp2']}</b>\nSL           : <b>{s['sl']}</b>\nExpired      : <b>{s['expired']}</b>\nCancelled    : <b>{s['cancelled']}</b>\nPending      : <b>{s['pending']}</b>\n\nWinrate      : <b>{s['winrate']:.1f}%</b>\nTotal pips   : <b>{s['total_pips']:+.1f}</b>\nProfit factor: <b>{_pf(s['profit_factor'])}</b>\nAvg R        : <b>{s['avg_r']:+.2f}R</b>\n\n⚠️ Winrate valid setelah 100 trade."
def format_weekly(s: dict) -> str: return format_stats(s, "STATISTIK 7 HARI")
