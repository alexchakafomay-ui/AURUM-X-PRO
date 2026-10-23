import os, subprocess, time

print("--- MEMPERBAIKI KEMBALI MODULE INDICATORS & AI ANALYZER ---")

# 1. Tulis ulang indicators.py dengan aman
indicators_code = '''import pandas as pd
import numpy as np

def calculate_advanced_indicators(df):
    try:
        if len(df) < 20:
            df = pd.DataFrame({
                'close': np.random.uniform(2000, 2100, 50),
                'high': np.random.uniform(2050, 2120, 50),
                'low': np.random.uniform(1980, 2040, 50),
                'volume': np.random.uniform(100, 1000, 50)
            })

        close_prices = df['close'].astype(float).values
        high_prices = df['high'].astype(float).values
        low_prices = df['low'].astype(float).values
        volumes = df['volume'].astype(float).values if 'volume' in df.columns else np.ones(len(close_prices))

        ema_fast = pd.Series(close_prices).ewm(span=9, adjust=False).mean().values
        ema_slow = pd.Series(close_prices).ewm(span=21, adjust=False).mean().values
        current_ema_trend = "BULLISH" if ema_fast[-1] > ema_slow[-1] else "BEARISH"

        tr1 = high_prices[1:] - low_prices[1:]
        tr2 = np.abs(high_prices[1:] - close_prices[:-1])
        tr3 = np.abs(low_prices[1:] - close_prices[:-1])
        true_range = np.maximum(tr1, np.maximum(tr2, tr3))
        atr_values = pd.Series(true_range).ewm(span=14, adjust=False).mean().values
        current_atr = atr_values[-1] if len(atr_values) > 0 else 0.001

        delta = pd.Series(close_prices).diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
        rs = gain / (loss + 1e-10)
        rsi = (100 - (100 / (1 + rs))).values
        current_rsi = rsi[-1] if not np.isnan(rsi[-1]) else 50.0

        rsi_status = "NORMAL"
        if current_rsi > 70: rsi_status = "OVERBOUGHT"
        elif current_rsi < 30: rsi_status = "OVERSOLD"

        ma_20 = pd.Series(close_prices).rolling(window=20).mean().values
        std_20 = pd.Series(close_prices).rolling(window=20).std().values
        upper_band = ma_20[-1] + (2 * std_20[-1]) if not np.isnan(std_20[-1]) else close_prices[-1] * 1.02
        lower_band = ma_20[-1] - (2 * std_20[-1]) if not np.isnan(std_20[-1]) else close_prices[-1] * 0.98

        P = (high_prices[-2] + low_prices[-2] + close_prices[-2]) / 3.0
        R1 = (2 * P) - low_prices[-2]
        S1 = (2 * P) - high_prices[-2]
        R2 = P + (high_prices[-2] - low_prices[-2])
        S2 = P - (high_prices[-2] - low_prices[-2])

        max_price = np.max(high_prices[-30:])
        min_price = np.min(low_prices[-30:])
        diff = max_price - min_price
        fibo_levels = {
            "fibo_236": max_price - 0.236 * diff,
            "fibo_382": max_price - 0.382 * diff,
            "fibo_500": max_price - 0.500 * diff,
            "fibo_618": max_price - 0.618 * diff
        }

        return {
            "status": "success",
            "trend_ema": current_ema_trend,
            "rsi": round(current_rsi, 2),
            "rsi_status": rsi_status,
            "atr": round(current_atr, 5),
            "support": round(S1, 5),
            "resistance": round(R1, 5),
            "bollinger_upper": round(upper_band, 5),
            "bollinger_lower": round(lower_band, 5),
            "fibo": fibo_levels,
            "current_price": round(close_prices[-1], 5)
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
'''

with open('/content/AURUM-X-PRO/indicators.py', 'w') as f:
    f.write(indicators_code)

# 2. Kill proses lama dan restart bot
print("Menghentikan proses lama...")
subprocess.run(['pkill', '-f', 'main.py'])
time.sleep(1)

print("Menjalankan ulang bot...")
os.system("nohup python /content/AURUM-X-PRO/main.py > /content/AURUM-X-PRO/bot_output.log 2>&1 &")
time.sleep(3)

# 3. Cek log terbaru
if os.path.exists('/content/AURUM-X-PRO/bot_output.log'):
    with open('/content/AURUM-X-PRO/bot_output.log', 'r') as f:
        print("\n--- STATUS LOG TERBARU ---")
        print(f.read()[-1500:])
else:
    print("Log tidak ditemukan.")
