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
        
        # 1. Sapaan Pagi (Jam 06:55 UTC / 13:55 WIB)
        jq.run_daily(self.greeting_job, time=time(hour=6, minute=55, tzinfo=tz), days=days)
        
        # 2. Analisa Kontinu: Setiap 30 Menit (1800 detik)
        jq.run_repeating(self.analysis_job, interval=1800, first=60)
        
        # 3. Tracker Pantau Harga: Setiap 5 Menit
        jq.run_repeating(self.tracker_job, interval=300, first=30)
        
        # 4. Weekend Detector: Setiap 6 Jam
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
            self.db.set_state("is_analyzing", "1")
            try: 
                await self.run_analysis()
            except Exception: 
                logger.exception("Err Analysis")
            finally:
                self.db.set_state("is_analyzing", "0")

    async def weekend_job(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if not market_is_open(): await self.snd.send_weekend()

    async def tracker_job(self, ctx: ContextTypes.DEFAULT_TYPE) -> None:
        if market_is_open(): await self.t.run()

    async def run_analysis(self) -> None:
        # Kuota maksimal 6 sinyal sehari tetap berlaku
        ok, rsn = self.db.can_trade(self.s)
        if not ok:
            return # Diam saja kalau kuota penuh atau bot dijeda
            
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
            return # Diam saja kalau pasar sepi
            
        cds.sort(key=lambda x: x[0]["confidence"], reverse=True)
        slots = min(self.s.max_open_trades - self.db.open_trades_count(), self.s.max_signals_per_day - self.db.count_signals_today())
        
        if slots <= 0: return
        
        sent = 0
        for c, sn, _ in cds[:slots]:
            # Beri jarak minimal 2 jam untuk pair yang sama agar tidak spam
            if self.db.recent_pair_signal(c["pair"], 2): continue
            
            f = await asyncio.to_thread(self.a.analyze, c, sn, c.get("news_meta", {}))
            if f.get("direction") == "NO_SIGNAL": continue
            
            ok, _ = self.db.can_trade(self.s)
            if not ok: break
            
            self.db.log_signal(f); 
            await self.snd.send_signal(f); 
            sent += 1; 
            self.db.set_state("last_bias", c["direction"])

    async def manual_analysis(self, pair: str) -> str:
        ok, rsn = self.db.can_trade(self.s)
        if not ok: return rsn
            
        await asyncio.to_thread(self.n.refresh)
        b = await asyncio.to_thread(self.f.fetch_pair_bundle, pair)
        if b is None: return "Data harga tidak lengkap untuk pair ini."
        
        try:
            c = build_candidate(pair, b, self.n)
            if not c: return "Tidak ada setup valid saat ini. Sabar ya Bos."
            
            sn = build_snapshot(b)
            f = await asyncio.to_thread(self.a.analyze, c, sn, c.get("news_meta", {}))
            
            if f.get("direction") == "NO_SIGNAL":
                await self.snd.send_no_signal(f.get("reasoning", "AI menolak setup karena risiko."))
                return "NO_SIGNAL"
                
            self.db.log_signal(f)
            await self.snd.send_signal(f)
            return "SIGNAL_SENT"
        except Exception as e:
            logger.exception("Manual signal error")
            return f"Error: {e}"
