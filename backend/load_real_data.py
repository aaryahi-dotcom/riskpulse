#!/usr/bin/env python3
"""
Load real IEEE-CIS fraud transactions and score them through the backend.
Designed to populate the frontend live feed with real data patterns.
"""
import json
import pandas as pd
import requests
from datetime import datetime, timedelta

# Backend config
API_BASE = "http://localhost:8000"
DEMO_USERNAME = "demo_admin"
DEMO_PASSWORD = "riskpulse-demo"

# Get auth token
def get_token():
    resp = requests.post(
        f"{API_BASE}/api/v1/auth/token",
        data={"username": DEMO_USERNAME, "password": DEMO_PASSWORD},
    )
    return resp.json()["access_token"]

# Load real transaction data
def load_transactions(limit=50):
    """Load real IEEE-CIS transactions from CSV."""
    try:
        df = pd.read_csv("data/raw/train_transaction.csv", nrows=limit)
        print(f"✓ Loaded {len(df)} transactions from IEEE-CIS dataset")
        return df
    except FileNotFoundError:
        print("❌ train_transaction.csv not found in data/raw/")
        print("   Download from: https://www.kaggle.com/datasets/vcskaushik/ieee-cis-fraud-detection")
        return None

# Score transactions through backend
def score_batch(df, token):
    """Send real transactions to backend for scoring."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    scored = []
    for idx, row in df.iterrows():
        # Map IEEE-CIS columns to RiskPulse schema
        payload = {
            "amount": float(row.get("TransactionAmt", 0)),
            "sender_id": f"user_{row.get('TransactionID', idx)}@bank",
            "receiver_id": f"merchant_{row.get('ProductCD', 'unknown')}@merchant",
            "timestamp": datetime.now().isoformat(),
            "channel": "card",  # IEEE-CIS is card fraud, not UPI
            "device_type": str(row.get("DeviceType", "unknown")),
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
                scored.append({
                    "txn_id": result["txn_id"],
                    "amount": payload["amount"],
                    "risk_score": result["risk_score"],
                    "decision": result["decision"],
                    "is_fraud": int(row.get("isFraud", 0)),
                })
                print(f"  {idx+1}. Score: {result['risk_score']:.3f} | Decision: {result['decision'].upper()}")
            else:
                print(f"  {idx+1}. Error: {resp.status_code}")
        except Exception as e:
            print(f"  {idx+1}. Failed: {e}")

    return scored

# Main
if __name__ == "__main__":
    print("\n=== RiskPulse Real Data Loader ===\n")

    # Load data
    df = load_transactions(limit=50)
    if df is None:
        exit(1)

    # Authenticate
    print("Authenticating...")
    try:
        token = get_token()
        print(f"✓ Token obtained\n")
    except Exception as e:
        print(f"❌ Auth failed: {e}")
        exit(1)

    # Score batch
    print("Scoring transactions through backend...\n")
    results = score_batch(df, token)

    # Summary
    print(f"\n=== Results ===")
    print(f"Total scored: {len(results)}")
    if results:
        approved = sum(1 for r in results if r["decision"] == "approve")
        blocked = sum(1 for r in results if r["decision"] == "block")
        stepped = sum(1 for r in results if r["decision"] == "step_up")

        print(f"Approve: {approved} | Step-up: {stepped} | Block: {blocked}")
        print(f"\nCheck frontend live feed at http://localhost:5175")
