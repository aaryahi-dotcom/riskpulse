#!/usr/bin/env python3
"""
Inject transactions specifically designed to fall in grey zone [0.20-0.70]
so agents activate and brain panel shows full reasoning.
"""
import requests
from datetime import datetime
import time

API_BASE = "http://localhost:8000"

def get_token():
    resp = requests.post(
        f"{API_BASE}/api/v1/auth/token",
        data={"username": "demo_admin", "password": "riskpulse-demo"},
    )
    return resp.json()["access_token"]

GREY_ZONE_SCENARIOS = [
    {
        "name": "🟢 Low-Mid Risk (Should show ALLOW)",
        "amount": 50000,
        "sender": "occasional_user@bank",
        "receiver": "new_payee_1@merchant",
    },
    {
        "name": "🟡 Medium Risk (Should show COOL_OFF)",
        "amount": 100000,
        "sender": "medium_risk_user@bank",
        "receiver": "unknown_payee@merchant",
    },
    {
        "name": "🟡 Medium-High Risk (Should show COOL_OFF or BLOCK)",
        "amount": 200000,
        "sender": "suspicious_user@bank",
        "receiver": "risky_payee@merchant",
    },
    {
        "name": "🟡 Borderline (Agent will decide)",
        "amount": 150000,
        "sender": "first_large_txn@bank",
        "receiver": "new_account@merchant",
    },
    {
        "name": "🟢 Moderate (Should show ALLOW)",
        "amount": 75000,
        "sender": "regular_user@bank",
        "receiver": "occasional_payee@merchant",
    },
    {
        "name": "🟡 Edge Case (Agent decides)",
        "amount": 180000,
        "sender": "borderline_user@bank",
        "receiver": "questionable_payee@merchant",
    },
]

def inject():
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print("\n" + "="*70)
    print("GREY ZONE TRANSACTIONS - Agents Will Activate!")
    print("="*70 + "\n")

    for i, scenario in enumerate(GREY_ZONE_SCENARIOS, 1):
        payload = {
            "amount": scenario["amount"],
            "sender_id": scenario["sender"],
            "receiver_id": scenario["receiver"],
            "timestamp": datetime.now().isoformat(),
            "channel": "card",
        }

        try:
            print(f"{i}. {scenario['name']}")
            resp = requests.post(
                f"{API_BASE}/api/v1/score",
                headers=headers,
                json=payload,
                timeout=5,
            )

            if resp.status_code == 200:
                result = resp.json()
                score = result['risk_score']

                # Check if in grey zone
                in_grey = 0.20 <= score < 0.70
                agent_status = "🤖 AGENT ACTIVE" if in_grey else "⚡ FAST PATH"

                print(f"   Score: {score:.3f} [{agent_status}]")
                print(f"   Decision: {result['decision'].upper()}")

                if result.get("agent_trace"):
                    trace = result["agent_trace"]
                    if trace.get("final_verdict"):
                        verdict = trace["final_verdict"]
                        print(f"   ✅ Agent Verdict: {verdict['verdict']}")
                        print(f"   ✅ Confidence: {verdict['confidence']:.0%}")

                print(f"   TXN: {result['txn_id']}\n")

            else:
                print(f"   ERROR: {resp.status_code}\n")

        except Exception as e:
            print(f"   FAILED: {e}\n")

        time.sleep(1)

    print("="*70)
    print("✓ Grey zone transactions injected!")
    print("✓ Frontend: http://localhost:5173")
    print("✓ Click yellow/orange transactions → Brain panel shows agent reasoning")
    print("="*70)

if __name__ == "__main__":
    inject()
