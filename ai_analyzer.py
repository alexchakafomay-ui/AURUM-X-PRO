import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

def analyze_market_with_ai(ticker, price_data, indicator_results):
    """
    Mengirimkan metrik pasar tingkat institusi ke Gemini via OpenRouter untuk analisis multi-dimensi.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    model_name = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

    if not api_key:
        return {
            "decision": "WAIT",
            "entry": "-",
            "stop_loss": "-",
            "take_profit": "-",
            "reasoning": ["API Key OpenRouter tidak ditemukan di sistem."]
        }

    prompt = f"""[SISTEM ANALISIS TRADING INSTITUSIONAL - CODENAME AURUM]
Anda adalah AI Quant Strategist Senior di Wall Street. Tugas Anda adalah memberikan keputusan trading dengan tingkat akurasi di atas 92% untuk {ticker}.

METRIK INTEGRASI PASAR:
- Harga Terakhir: {indicator_results.get('current_price')}
- Tren Dominan (Double EMA): {indicator_results.get('trend_ema')}
- RSI (14) & Status: {indicator_results.get('rsi')} ({indicator_results.get('rsi_status')})
- Volatilitas Pasar (ATR): {indicator_results.get('atr')}
- Bollinger Bands Upper: {indicator_results.get('bollinger_upper')}
- Bollinger Bands Lower: {indicator_results.get('bollinger_lower')}
- Pivot Support 1 / Resistance 1: {indicator_results.get('support')} / {indicator_results.get('resistance')}
- Pivot Support 2 / Resistance 2: {indicator_results.get('support_2')} / {indicator_results.get('resistance_2')}
- Level Golden Ratio Fibo (61.8%): {indicator_results.get('fibo', {}).get('fibo_618')}
- Sinyal Transaksi Bandar (VSA): {indicator_results.get('vsa_signal')}

ATURAN KETAT AKURASI:
1. BUY hanya jika harga mendekati Support/Fibo 61.8%/Lower Band DAN Tren bersifat BULLISH atau terjadi jenuh jual (Oversold).
2. SELL hanya jika harga mendekati Resistance/Upper Band DAN Tren bersifat BEARISH atau terjadi jenuh beli (Overbought).
3. Jika tidak ada konfluensi indikator yang jelas, pilih WAIT.

Keluarkan output dalam format JSON murni TANPA markdown wrapper (jangan gunakan ```json):
{{
  "decision": "BUY/SELL/WAIT",
  "entry": "angka_harga",
  "stop_loss": "angka_harga",
  "take_profit": "angka_harga",
  "reasoning": ["alasan strategis 1", "alasan strategis 2", "alasan strategis 3"]
}}
"""

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        if response.status_code == 200:
            content = response.json()['choices'][0]['message']['content'].strip()
            # Membersihkan jika AI tetap mengembalikan markdown
            if content.startswith("```"):
                content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        else:
            return {"decision": "WAIT", "entry": "-", "stop_loss": "-", "take_profit": "-", "reasoning": [f"Error API: {response.text}"]}
    except Exception as e:
        return {"decision": "WAIT", "entry": "-", "stop_loss": "-", "take_profit": "-", "reasoning": [f"Koneksi terganggu: {str(e)}"]}
