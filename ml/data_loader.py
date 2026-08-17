"""
Loads and merges the IEEE-CIS Fraud Detection CSVs with memory-conscious
dtypes. The full train_transaction.csv is 683MB / 394 columns; this box has
8GB RAM, so we:

  1. Only read the columns we actually use for feature engineering
     (~35 of 394) via `usecols` — this alone avoids loading the 339
     anonymized V-columns we don't use, which is most of the file's bytes.
  2. Specify dtypes up front (float32 / int32 / category) instead of
     letting pandas infer float64/object, roughly halving memory again.

Adapting a card-not-present e-commerce dataset to UPI-flavored language:
IEEE-CIS has no explicit sender_id/receiver_id the way a UPI ledger would.
We approximate:
  - sender identity  -> card1 + addr1 (the most stable pair of columns
    tied to a single paying instrument/region in this dataset)
  - beneficiary identity -> R_emaildomain when present, else
    P_emaildomain (recipient email domain is the closest proxy IEEE-CIS
    offers to a payee/VPA handle)
This is documented again inline at the point each proxy is constructed.
"""
from __future__ import annotations

import logging
import os

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TRANSACTION_COLS = [
    "TransactionID", "isFraud", "TransactionDT", "TransactionAmt", "ProductCD",
    "card1", "card2", "card3", "card4", "card5", "card6",
    "addr1", "addr2", "dist1",
    "P_emaildomain", "R_emaildomain",
    "C1", "C13",
    "D1", "D4", "D10", "D15",
    "M1", "M2", "M3", "M4",
]

TRANSACTION_DTYPES = {
    "TransactionID": "int32",
    "isFraud": "int8",
    "TransactionDT": "int32",
    "TransactionAmt": "float32",
    "ProductCD": "category",
    "card1": "float32", "card2": "float32", "card3": "float32",
    "card4": "category", "card5": "float32", "card6": "category",
    "addr1": "float32", "addr2": "float32", "dist1": "float32",
    "P_emaildomain": "category", "R_emaildomain": "category",
    "C1": "float32", "C13": "float32",
    "D1": "float32", "D4": "float32", "D10": "float32", "D15": "float32",
    "M1": "category", "M2": "category", "M3": "category", "M4": "category",
}

IDENTITY_COLS = [
    "TransactionID", "DeviceType", "DeviceInfo",
    "id_31", "id_30", "id_38",
]

IDENTITY_DTYPES = {
    "TransactionID": "int32",
    "DeviceType": "category",
    "DeviceInfo": "category",
    "id_31": "category",
    "id_30": "category",
    "id_38": "category",
}


def load_raw(data_dir: str) -> pd.DataFrame:
    """Load train_transaction.csv + train_identity.csv, left-join on
    TransactionID (most transactions have no identity row — expected,
    ~76% of rows in IEEE-CIS), return the merged, dtype-optimized frame
    sorted by TransactionDT (the CSV is already chronological, but we
    sort defensively so downstream expanding/rolling features are valid).
    """
    txn_path = os.path.join(data_dir, "train_transaction.csv")
    id_path = os.path.join(data_dir, "train_identity.csv")
    if not os.path.exists(txn_path):
        raise FileNotFoundError(
            f"{txn_path} not found. Expected the IEEE-CIS train_transaction.csv "
            f"at data/raw/train_transaction.csv (see test_data/README.md)."
        )

    logger.info("Reading %s (columns limited to %d of 394 for memory)", txn_path, len(TRANSACTION_COLS))
    txn = pd.read_csv(
        txn_path,
        usecols=TRANSACTION_COLS,
        dtype=TRANSACTION_DTYPES,
        engine="c",
    )
    logger.info("train_transaction.csv loaded: %d rows, %.1f MB", len(txn), txn.memory_usage(deep=True).sum() / 1e6)

    if os.path.exists(id_path):
        logger.info("Reading %s", id_path)
        ident = pd.read_csv(
            id_path,
            usecols=IDENTITY_COLS,
            dtype=IDENTITY_DTYPES,
            engine="c",
        )
        logger.info("train_identity.csv loaded: %d rows, %.1f MB", len(ident), ident.memory_usage(deep=True).sum() / 1e6)
        merged = txn.merge(ident, how="left", on="TransactionID")
        del ident
    else:
        logger.warning("%s not found — proceeding with transaction table only, device signals will be cold-start.", id_path)
        merged = txn
        for c in ["DeviceType", "DeviceInfo", "id_31", "id_30", "id_38"]:
            merged[c] = np.nan

    del txn
    merged = merged.sort_values("TransactionDT", kind="mergesort").reset_index(drop=True)
    logger.info("Merged frame: %d rows, %.1f MB", len(merged), merged.memory_usage(deep=True).sum() / 1e6)
    return merged
