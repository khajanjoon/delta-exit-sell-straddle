import hashlib
import hmac
import requests
import time
import os
from collections import defaultdict

# ================= CONFIG =================
BASE_URL = "https://api.india.delta.exchange"
API_KEY = "TcwdPNNYGjjgkRW4BRIAnjL7z5TLyJ"
API_SECRET = "B5ALo5Mh8mgUREB6oGD4oyX3y185oElaz1LoU6Y3X5ZX0s8TvFZcX4YTVToJ"

REFRESH_INTERVAL = 5
STRADDLE_TARGET = 1000.0      # 🔥 EXIT target per straddle
# ========================================


def sign(secret, message):
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def auth_headers(method, path, payload=""):
    ts = str(int(time.time()))
    sig = sign(API_SECRET, method + ts + path + payload)
    return {
        "api-key": API_KEY,
        "timestamp": ts,
        "signature": sig,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }


def fetch_positions():
    path = "/v2/positions/margined"
    return requests.get(
        BASE_URL + path,
        headers=auth_headers("GET", path),
        timeout=(3, 27)
    ).json()


def close_position(product_id, qty):
    path = "/v2/orders"
    payload = {
        "product_id": product_id,
        "size": qty,
        "side": "buy",                 # BUY to close SELL
        "order_type": "market_order"
    }

    body = str(payload).replace("'", '"')
    return requests.post(
        BASE_URL + path,
        headers=auth_headers("POST", path, body),
        data=body,
        timeout=(3, 27)
    ).json()


def clear():
    os.system("clear" if os.name != "nt" else "cls")


# ---------- STATE ----------
exited_straddles = set()

# ---------- MAIN LOOP ----------
while True:
    try:
        data = fetch_positions()
        clear()

        print("📊 LIVE STRADDLE PnL + AUTO-EXIT")
        print("=" * 100)

        if not data.get("success"):
            print("❌ API error")
            time.sleep(REFRESH_INTERVAL)
            continue

        straddles = defaultdict(lambda: {
            "CALL": 0.0,
            "PUT": 0.0,
            "TOTAL": 0.0,
            "LEGS": []
        })

        for pos in data["result"]:
            size = float(pos.get("size", 0))
            if size >= 0:
                continue

            symbol = pos["product_symbol"]
            if not (symbol.startswith("C-") or symbol.startswith("P-")):
                continue

            entry = float(pos["entry_price"])
            mark = float(pos["mark_price"])
            qty = abs(size)
            pnl = (entry - mark) * qty

            parts = symbol.split("-")
            opt_type, asset, strike, expiry = parts
            key = f"{asset}-{strike}-{expiry}"

            straddles[key][opt_type == "C" and "CALL" or "PUT"] += pnl
            straddles[key]["TOTAL"] += pnl
            straddles[key]["LEGS"].append({
                "product_id": pos["product_id"],
                "qty": qty
            })

        for key, s in sorted(straddles.items()):
            sign_icon = "🟢" if s["TOTAL"] >= 0 else "🔴"
            exited = key in exited_straddles

            print(
                f"{sign_icon} {key:<20} | "
                f"CALL: {s['CALL']:>7.2f} | "
                f"PUT: {s['PUT']:>7.2f} | "
                f"TOTAL: {s['TOTAL']:>7.2f}"
                f"{' ✅ EXITED' if exited else ''}"
            )

            # ---------- AUTO EXIT ----------
            if s["TOTAL"] >= STRADDLE_TARGET and not exited:
                print(f"🚀 TARGET HIT → EXITING {key}")
                for leg in s["LEGS"]:
                    close_position(leg["product_id"], leg["qty"])
                exited_straddles.add(key)

        print("=" * 100)
        print(f"🎯 Target per straddle: {STRADDLE_TARGET}")
        print(f"⏱️  {time.strftime('%H:%M:%S')}")

    except KeyboardInterrupt:
        print("\n👋 Auto-exit monitor stopped safely")
        break
    except Exception as e:
        print("❌ Error:", e)

    time.sleep(REFRESH_INTERVAL)
