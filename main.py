from flask import Flask
import requests
import os

app = Flask(__name__)

# === ENVIRONMENT VARIABLES ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# === CONFIG ===
CHAINS = ["ethereum", "solana", "bsc"]
MAX_MARKET_CAP = 12_000_000
MIN_LIQUIDITY = 20_000
MAX_LIQUIDITY = 300_000
MIN_VOLUME_15M = 1_500

sent_tokens = set()

# === ALERT FUNCTIONS ===
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}
    requests.post(url, data=payload)

def format_message(pair, note=""):
    return (
        f"🚨 <b>New Gem Alert!</b>\n"
        f"<b>Name:</b> {pair['baseToken']['name']} ({pair['baseToken']['symbol']})\n"
        f"<b>Chain:</b> {pair['chainId'].capitalize()}\n"
        f"<b>Market Cap:</b> ${int(pair.get('marketCapUsd', 0)):,}\n"
        f"<b>Liquidity:</b> ${int(pair['liquidity']['usd']):,}\n"
        f"<b>Volume (15m):</b> ${int(pair['volume']['m15']):,}\n"
        f"{note}"
        f"<b>DEX Link:</b> {pair['url']}"
    )

# === CORE FUNCTION ===
def check_dexscreener():
    matches = []
    fallback_candidates = []

    for chain in CHAINS:
        url = f"https://api.dexscreener.com/latest/dex/pairs/{chain}"
        try:
            response = requests.get(url)
            if response.status_code != 200:
                continue
            pairs = response.json().get("pairs", [])[:40]

            for pair in pairs:
                token_id = pair['pairAddress']
                market_cap = pair.get("marketCapUsd", 0)
                liquidity = pair["liquidity"]["usd"]
                volume_15m = pair["volume"]["m15"]

                if not all([market_cap, liquidity, volume_15m]):
                    continue

                if market_cap < MAX_MARKET_CAP:
                    fallback_candidates.append((volume_15m, pair))

                if (
                    token_id not in sent_tokens
                    and market_cap < MAX_MARKET_CAP
                    and MIN_LIQUIDITY <= liquidity <= MAX_LIQUIDITY
                    and volume_15m > MIN_VOLUME_15M
                ):
                    matches.append(pair)
                    sent_tokens.add(token_id)

        except Exception as e:
            print(f"Error fetching from {chain}: {e}")

    if matches:
        for match in matches:
            msg = format_message(match)
            send_telegram_alert(msg)
    else:
        fallback_candidates.sort(reverse=True)
        fallback_sent = 0
        for _, pair in fallback_candidates[:2]:
            if pair['pairAddress'] not in sent_tokens:
                msg = format_message(pair, note="🔍 <i>Fallback match based on volume.</i>\n")
                send_telegram_alert(msg)
                sent_tokens.add(pair['pairAddress'])
                fallback_sent += 1

        if fallback_sent == 0:
            send_telegram_alert("🧪 <b>Test Alert:</b> No tokens matched — bot is working!")

# === FLASK ROUTES ===
@app.route("/")
def home():
    return "Gem Hunter Bot is live! Ping /scan to run."

@app.route("/scan")
def scan():
    check_dexscreener()
    return "✅ Scan complete. Check Telegram for alerts."

# === ENTRY POINT ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
