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
        
        # 1. Sapaan Pagi (jam 06:55 UTC / 13:55 WIB)
        jq.run_daily(self.greeting_job, time=time(hour=6, minute=55, tzinfo=tz), days=days)
        
        # 2. Analisa Setiap 1 Jam (3600 detik)
        jq.run_repeating(self.analysis_job, interval=3600, first=60)
        
        # 3. Tracker (Cek harga tiap 5 menit)
        jq.run_repeating(self.tracker_job, interval=300, first=30)
        
        # 4. Weekend Detector (Tiap 6 jam)
        jq.run_repeating(self.weekend_job, interval=21600, first=60)

    async def greeting_job(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not market_is_open(): return
        td = utcnow().strftime("%Y-%m-%d")
        if self.db.get_state("greeted_date") == td: return
        await asyncio.to_thread(self.n.refresh)
        await self.snd.send_greeting(self.n.sentiment(), [e for e in self.n.upcoming(24) if e["impact"]=="High" and e["datetime_utc"].date()==utcnow().date()])
        self.db.set_state("greeted_date", td)

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
        # Cek kuota (max 6 sinyal sehari)
        ok, rsn = self.db.can_trade(self.s)
        if not ok:
            logger.info(f"Analisa dilewati: {rsn}")
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
            logger.info("Tidak ada kandidat setup di jam ini.")
            return
            
        cds.sort(key=lambda x: x[0]["confidence"], reverse=True)
        slots = min(self.s.max_open_trades - self.db.open_trades_count(), self.s.max_signals_per_day - self.db.count_signals_today())
        
        if slots <= 0: return
        
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
            
        if sent > 0:
            logger.info(f"Berhasil mengirim {sent} sinyal baru.")
