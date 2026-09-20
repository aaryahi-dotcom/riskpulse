#!/usr/bin/env python3
"""
Inject targeted demo scenarios specifically designed to trigger agent verdicts.
Creates transactions that will score in different ranges to show the full agent pipeline.
"""
import requests
import time
from datetime import datetime

API_BASE = "http://localhost:8000"

def get_token():
    resp = requests.post(
        f"{API_BASE}/api/v1/auth/token",
        data={"username": "demo_admin", "password": "riskpulse-demo"},
    )
    return resp.json()["access_token"]

# Scenarios designed to trigger different verdicts
SCENARIOS = [
    {
        "name": "🟢 SAFE - Low Risk",
        "amount": 1000,
        "sender": "safe_user_123@bank",
        "receiver": "trusted_merchant@paypal",
        "device": "mobile",
    },
    {
        "name": "🟡 SUSPICIOUS - Medium Risk (Should trigger COOL_OFF)",
        "amount": 250000,
        "sender": "new_user_456@bank",
        "receiver": "unknown_new_merchant@merchant",
        "device": "desktop",
    },
    {
        "name": "🔴 FRAUD PATTERN - High Risk (Should trigger BLOCK)",
        "amount": 500000,
        "sender": "compromised_789@bank",
        "receiver": "offshore_account@unknown",
        "device": "unknown",
    },
    {
        "name": "🟡 UNUSUAL - Medium-High Risk",
        "amount": 300000,
        "sender": "first_time_user@bank",
        "receiver": "new_beneficiary@merchant",
        "device": "tablet",
    },
    {
        "name": "🔴 MULTIPLE RED FLAGS",
        "amount": 750000,
        "sender": "rapid_txn_user@bank",
        "receiver": "high_risk_receiver@offshore",
        "device": "unknown",
    },
    {
        "name": "🟢 LEGITIMATE",
        "amount": 50000,
        "sender": "regular_customer@bank",
        "receiver": "known_vendor@merchant",
        "device": "mobile",
    },
]

def inject_scenarios():
    """Inject scenarios one at a time."""
    token = get_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    print("\n" + "="*70)
    print("INJECTING DEMO SCENARIOS - Watch Brain Panel Activate!")
    print("="*70 + "\n")

    for i, scenario in enumerate(SCENARIOS, 1):
        payload = {
            "amount": scenario["amount"],
            "sender_id": scenario["sender"],
            "receiver_id": scenario["receiver"],
            "timestamp": datetime.now().isoformat(),
            "channel": "card",
            "device_type": scenario["device"],
        }

        try:
            print(f"{i}. {scenario['name']}")
            print(f"   Amount: ₹{scenario['amount']:,}")

            resp = requests.post(
                f"{API_BASE}/api/v1/score",
                headers=headers,
                json=payload,
                timeout=5,
            )

            if resp.status_code == 200:
                result = resp.json()

                # Show results
                print(f"   Score: {result['risk_score']:.3f}")
                print(f"   Decision: {result['decision'].upper()}")

                # Show agent trace if present
                if result.get("agent_trace"):
                    trace = result["agent_trace"]
                    if trace.get("agents_run"):
                        for agent in trace["agents_run"]:
                            print(f"   Agent: {agent['agent']} → {agent['status'].upper()}")
                    if trace.get("final_verdict"):
                        verdict = trace["final_verdict"]["verdict"]
                        print(f"   ✓ Agent Verdict: {verdict}")
                        print(f"   ✓ Confidence: {trace['final_verdict']['confidence']:.0%}")
                else:
                    print(f"   (No agents - outside grey zone)")

                print(f"   TXN ID: {result['txn_id']}")
                print()

            else:
                print(f"   ERROR: {resp.status_code}\n")

        except Exception as e:
            print(f"   FAILED: {e}\n")

        # Wait before next
        time.sleep(1.5)

    print("="*70)
    print("✓ All scenarios injected!")
    print("✓ Check frontend at http://localhost:5173")
    print("✓ Click transactions to see full agent reasoning in Brain Panel")
    print("="*70 + "\n")

if __name__ == "__main__":
    inject_scenarios()
