#!/usr/bin/env python3
"""
Stream real transactions through the backend continuously so they appear in frontend live feed.
"""
import requests
import pandas as pd
import time
from datetime import datetime

API_BASE = "http://localhost:8000"
DEMO_USERNAME = "demo_admin"
DEMO_PASSWORD = "riskpulse-demo"

def get_token():
    resp = requests.post(
        f"{API_BASE}/api/v1/auth/token",
        data={"username": DEMO_USERNAME, "password": DEMO_PASSWORD},
    )
    return resp.json()["access_token"]

def stream_transactions(interval_seconds=2):
    """Continuously score transactions so they appear in live feed."""
    try:
        df = pd.read_csv("data/raw/train_transaction.csv")
        print(f"✓ Loaded {len(df)} transactions")
    except FileNotFoundError:
        print("❌ train_transaction.csv not found")
        return

    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print(f"\n🔄 Streaming transactions every {interval_seconds}s...")
    print("(Frontend live feed will update in real-time)\n")

    idx = 0
    try:
        while True:
            row = df.iloc[idx % len(df)]

            payload = {
                "amount": float(row.get("TransactionAmt", 100)),
                "sender_id": f"user_{int(row.get('card1', 0))}@bank",
                "receiver_id": f"merchant_{row.get('ProductCD', 'X')}@merchant",
                "timestamp": datetime.now().isoformat(),
                "channel": "card",
                "device_type": str(row.get("DeviceType", "desktop")),
            }

            try:
                resp = requests.post(
                    f"{API_BASE}/api/v1/score",
                    headers=headers,
                    json=payload,
                    timeout=5,
                )
                if resp.status_code == 200:
                    result = resp.json()
                    is_fraud = int(row.get("isFraud", 0))
                    fraud_flag = "🔴 FRAUD" if is_fraud == 1 else "🟢 LEGIT"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {fraud_flag} | Score: {result['risk_score']:.3f} | {result['decision'].upper()}")
                    idx += 1
                else:
                    print(f"Error: {resp.status_code}")
            except Exception as e:
                print(f"Failed: {e}")

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        print("\n\n✓ Stopped streaming")

if __name__ == "__main__":
    stream_transactions(interval_seconds=2)
