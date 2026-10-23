from __future__ import annotations
import asyncio, logging
from datetime import time, timezone
from telegram.ext import Application, ContextTypes
from ai_analyzer import AIAnalyzer
from config import Settings
from data_fetcher import DataFetcher
from indicators import build_candidate, build_snapshot
from logger import Database
from news_filter import NewsFilter
from telegram_sender import TelegramSender
from tracker import SignalTracker
from utils import market_is_open, utcnow

logger = logging.getLogger(__name__)

class AurumScheduler:
    def __init__(self, s: Settings, db: Database, f: DataFetcher, n: NewsFilter, a: AIAnalyzer, snd: TelegramSender, t: SignalTracker):
        self.s, self.db, self.f, self.n, self.a, self.snd, self.t = s, db, f, n, a, snd, t
        self._lock = asyncio.Lock()

    def schedule(self, app: Application) -> None:
        jq, tz, days = app.job_queue, timezone.utc, tuple(range(5))
        
        # Kembali ke Jadwal Tetap (Sesuai Jam)
        for h in self.s.session_hours_utc:
            # Sapaan Pagi (Hanya di sesi pertama jam 07:00 UTC)
            if h == self.s.session_hours_utc[0]:
                jq.run_daily(self.greeting_job, time=time(hour=h-1, minute=55, tzinfo=tz), days=days)
            
            # Pre-alert (2 menit sebelum analisa)
            jq.run_daily(self.pre_alert_job, time=time(hour=h-1, minute=58, tzinfo=tz), days=days)
            
            # Analisa Utama
            jq.run_daily(self.analysis_job, time=time(hour=h, minute=0, tzinfo=tz), days=days)
        
        # Tracker (Cek harga TP/SL tiap 5 menit)
        jq.run_repeating(self.tracker_job, interval=300, first=30)
        
        # Weekend Detector
        jq.run_repeating(self.weekend_job, interval=21600, first=60)

    async def greeting_job(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not market_is_open(): return
        td = utcnow().strftime("%Y-%m-%d")
        if self.db.get_state("greeted_date") == td: return
        await asyncio.to_thread(self.n.refresh)
        await self.snd.send_greeting(self.n.sentiment(), [e for e in self.n.upcoming(24) if e["impact"]=="High" and e["datetime_utc"].date()==utcnow().date()])
        self.db.set_state("greeted_date", td)

    async def pre_alert_job(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if market_is_open() and not self.db.is_paused():
            await self.snd.send_prealert(self.db.get_state("last_bias", "Mixed"))

    async def analysis_job(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not market_is_open(): return
        async with self._lock:
            try: 
                await self.run_analysis()
            except Exception: 
                logger.exception("Err Analysis")

    async def weekend_job(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not market_is_open(): await self.snd.send_weekend()

    async def tracker_job(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if market_is_open(): await self.t.run()

    async def run_analysis(self) -> None:
        ok, rsn = self.db.can_trade(self.s)
        if not ok:
            if self.s.send_no_signal: await self.snd.send_no_signal(rsn)
            return
            
        await asyncio.to_thread(self.n.refresh)
        bdl = await asyncio.to_thread(self.f.fetch_watchlist)
        cds = []
        for p, b in bdl.items():
            if b is not None:
                try:
                    c = build_candidate(p, b, self.n)
                    if c: cds.append((c, build_snapshot(b), b))
                except Exception: logger.exception("Cand %s", p)
                
        if not cds: 
            if self.s.send_no_signal: await self.snd.send_no_signal("Tidak ada konfluensi yang memenuhi standar.")
            return
            
        cds.sort(key=lambda x: x[0]["confidence"], reverse=True)
        slots = min(self.s.max_open_trades - self.db.open_trades_count(), self.s.max_signals_per_day - self.db.count_signals_today())
        
        if slots <= 0: 
            if self.s.send_no_signal: await self.snd.send_no_signal("Slot trade penuh.")
            return
        
        sent = 0
        for c, sn, _ in cds[:slots]:
            if self.db.recent_pair_signal(c["pair"], 2): continue
            
            f = await asyncio.to_thread(self.a.analyze, c, sn, c.get("news_meta", {}))
            if f.get("direction") == "NO_SIGNAL": continue
            
            ok, _ = self.db.can_trade(self.s)
            if not ok: break
            
            self.db.log_signal(f); 
            await self.snd.send_signal(f); 
            sent += 1; 
            self.db.set_state("last_bias", c["direction"])
            
        if sent == 0 and self.s.send_no_signal:
            await self.snd.send_no_signal("Semua kandidat ditolak oleh filter AI / Risk Manager.")
