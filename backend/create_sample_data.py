#!/usr/bin/env python3
"""
Generate realistic IEEE-CIS-like sample transactions for demo without needing Kaggle download.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

def create_sample_transactions(n_samples=100):
    """Generate realistic fraud/legitimate transaction samples."""

    np.random.seed(42)

    # Transaction amounts (realistic distribution)
    amounts = np.concatenate([
        np.random.exponential(100, n_samples // 2),  # Most small
        np.random.uniform(500, 5000, n_samples // 4),  # Some medium
        np.random.uniform(5000, 50000, n_samples // 4),  # Few large
    ])[:n_samples]

    # Device types
    devices = np.random.choice(['mobile', 'desktop', 'tablet'], n_samples, p=[0.6, 0.3, 0.1])

    # Card present vs not present (fraud often uses card-not-present)
    card_present = np.random.choice([0, 1], n_samples, p=[0.3, 0.7])

    # Product categories
    products = np.random.choice(['W', 'H', 'R', 'C', 'S'], n_samples, p=[0.3, 0.2, 0.2, 0.15, 0.15])

    # Fraud labels (realistic ~3.5% fraud rate)
    is_fraud = np.random.choice([0, 1], n_samples, p=[0.965, 0.035])

    # Distance from home (fraud often has unusual distances)
    dist_from_home = np.zeros(n_samples)
    fraud_mask = is_fraud == 1
    dist_from_home[fraud_mask] = np.random.exponential(200, np.sum(fraud_mask))
    dist_from_home[~fraud_mask] = np.random.exponential(20, np.sum(~fraud_mask))

    df = pd.DataFrame({
        'TransactionID': range(n_samples),
        'TransactionAmt': np.abs(amounts),
        'DeviceType': devices,
        'card1': np.random.randint(1000, 9999, n_samples),
        'card2': np.random.randint(100, 999, n_samples),
        'card3': np.random.randint(100, 999, n_samples),
        'card4': np.random.randint(1000, 9999, n_samples),
        'card5': np.random.randint(100, 999, n_samples),
        'card6': np.random.randint(100, 999, n_samples),
        'ProductCD': products,
        'addr1': np.random.randint(1, 1000, n_samples),
        'addr2': np.random.randint(1, 100, n_samples),
        'P_emaildomain': np.random.choice(['gmail.com', 'yahoo.com', 'hotmail.com', 'protonmail.com'], n_samples),
        'R_emaildomain': np.random.choice(['gmail.com', 'yahoo.com', 'hotmail.com'], n_samples),
        'M1': np.random.choice(['T', 'F'], n_samples),
        'M2': np.random.choice(['T', 'F'], n_samples),
        'M3': np.random.choice(['T', 'F'], n_samples),
        'M4': np.random.choice(['T', 'F'], n_samples),
        'M5': np.random.choice(['T', 'F'], n_samples),
        'M6': np.random.choice(['T', 'F'], n_samples),
        'M7': np.random.choice(['T', 'F'], n_samples),
        'M8': np.random.choice(['T', 'F'], n_samples),
        'M9': np.random.choice(['T', 'F'], n_samples),
        'dist_from_home': dist_from_home,
        'isFraud': is_fraud,
    })

    return df

def create_sample_identity(n_samples=100):
    """Generate realistic identity features."""

    np.random.seed(42)

    df = pd.DataFrame({
        'TransactionID': range(n_samples),
        'id_01': np.random.uniform(0, 100, n_samples),
        'id_02': np.random.uniform(0, 100, n_samples),
        'id_03': np.random.uniform(-10, 150, n_samples),
        'id_04': np.random.uniform(0, 100, n_samples),
        'id_05': np.random.uniform(0, 100, n_samples),
        'id_06': np.random.uniform(0, 100, n_samples),
        'id_11': np.random.choice(['NotFound', 'Found', 'New'], n_samples),
        'id_12': np.random.choice(['U', 'S', 'O'], n_samples),
        'id_13': np.random.uniform(0, 100, n_samples),
        'id_14': np.random.uniform(-10, 150, n_samples),
        'id_15': np.random.choice(['NotFound', 'Found', 'New'], n_samples),
        'id_16': np.random.choice(['U', 'S', 'O'], n_samples),
        'id_17': np.random.uniform(0, 300, n_samples),
        'id_18': np.random.uniform(0, 300, n_samples),
        'id_19': np.random.uniform(0, 300, n_samples),
        'id_20': np.random.uniform(0, 300, n_samples),
    })

    return df

if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)

    print("Generating realistic sample transactions...")
    txn_df = create_sample_transactions(n_samples=100)
    txn_df.to_csv("data/raw/train_transaction.csv", index=False)
    print(f"✓ Created train_transaction.csv with {len(txn_df)} samples")
    print(f"  - Fraud rate: {txn_df['isFraud'].mean():.1%}")
    print(f"  - Amount range: ₹{txn_df['TransactionAmt'].min():.0f} - ₹{txn_df['TransactionAmt'].max():.0f}")

    print("\nGenerating identity features...")
    identity_df = create_sample_identity(n_samples=100)
    identity_df.to_csv("data/raw/train_identity.csv", index=False)
    print(f"✓ Created train_identity.csv with {len(identity_df)} samples")

    print("\n✅ Ready to load data through backend!")
