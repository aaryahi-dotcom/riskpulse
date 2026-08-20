from __future__ import annotations

import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(TESTS_DIR)
sys.path.insert(0, BACKEND_DIR)

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    return tmp_path_factory.mktemp("db") / "test_riskpulse.db"


@pytest.fixture(scope="session", autouse=True)
def _set_test_env(test_db_path):
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
    os.environ["REDIS_URL"] = ""
    os.environ["JWT_SECRET"] = "test-secret"
    yield


@pytest.fixture(scope="session")
def app():
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    resp = client.post(
        "/api/v1/auth/token",
        data={"username": "demo_admin", "password": "riskpulse-demo"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_score_payload(**overrides):
    payload = {
        "amount": 5000.0,
        "sender_id": "sender_test_1",
        "receiver_id": "receiver_test_1@ybl",
        "timestamp": "2026-08-17T10:30:00Z",
        "channel": "UPI",
        "vpa": "receiver_test_1@ybl",
    }
    payload.update(overrides)
    return payload


def _build_tiny_ieee_cis_csvs(out_dir: str, n: int = 400, seed: int = 42) -> str:
    """A tiny, synthetic stand-in for the real 590K-row IEEE-CIS CSVs,
    with every column ml/data_loader.py expects. Used only by checklist
    2.6's retrain tests (test_retrain.py) so they run in seconds instead
    of minutes and never touch the real data/raw/ dataset. Fraud rows get
    a systematically larger amount so the tiny classifier has *something*
    learnable (F1 > 0 is not guaranteed to matter for those tests, which
    engineer the promotion comparison deterministically instead of
    relying on the exact score achieved here — see test_retrain.py)."""
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(seed)
    n_fraud = max(30, int(n * 0.15))
    is_fraud = np.zeros(n, dtype=int)
    fraud_idx = rng.choice(n, size=n_fraud, replace=False)
    is_fraud[fraud_idx] = 1

    amt = rng.uniform(50, 2000, size=n)
    amt[is_fraud == 1] *= rng.uniform(4, 10, size=n_fraud)

    txn_dt = np.sort(rng.integers(1_546_300_800, 1_546_300_800 + 20 * 86400, size=n))

    txn = pd.DataFrame({
        "TransactionID": np.arange(1, n + 1),
        "isFraud": is_fraud,
        "TransactionDT": txn_dt,
        "TransactionAmt": amt,
        "ProductCD": rng.choice(["W", "C", "H", "R", "S"], size=n),
        "card1": rng.integers(1000, 1050, size=n),
        "card2": rng.uniform(100, 600, size=n),
        "card3": rng.choice([150.0, 185.0], size=n),
        "card4": rng.choice(["visa", "mastercard"], size=n),
        "card5": rng.uniform(100, 240, size=n),
        "card6": rng.choice(["debit", "credit"], size=n),
        "addr1": rng.integers(100, 110, size=n),
        "addr2": rng.choice([87.0, 60.0], size=n),
        "dist1": rng.uniform(0, 100, size=n),
        "P_emaildomain": rng.choice(["gmail.com", "yahoo.com", "outlook.com", np.nan], size=n),
        "R_emaildomain": rng.choice(["gmail.com", "ybl", "paytm", np.nan], size=n),
        "C1": rng.uniform(0, 10, size=n),
        "C13": rng.uniform(0, 20, size=n),
        "D1": rng.uniform(0, 400, size=n),
        "D4": rng.uniform(0, 400, size=n),
        "D10": rng.uniform(0, 400, size=n),
        "D15": rng.uniform(0, 400, size=n),
        "M1": rng.choice(["T", "F", np.nan], size=n),
        "M2": rng.choice(["T", "F", np.nan], size=n),
        "M3": rng.choice(["T", "F", np.nan], size=n),
        "M4": rng.choice(["M0", "M1", "M2", np.nan], size=n),
    })
    ident = pd.DataFrame({
        "TransactionID": np.arange(1, n + 1),
        "DeviceType": rng.choice(["mobile", "desktop", np.nan], size=n),
        "DeviceInfo": rng.choice(["iPhone", "SM-G960", "Windows", np.nan], size=n),
        "id_31": rng.choice(["chrome", "safari", "samsung browser", np.nan], size=n),
        "id_30": rng.choice(["Android", "iOS", "Windows", np.nan], size=n),
        "id_38": rng.choice(["T", "F", np.nan], size=n),
    })

    os.makedirs(out_dir, exist_ok=True)
    txn.to_csv(os.path.join(out_dir, "train_transaction.csv"), index=False)
    ident.to_csv(os.path.join(out_dir, "train_identity.csv"), index=False)
    return out_dir


@pytest.fixture(scope="session")
def tiny_dataset_dir(tmp_path_factory) -> str:
    out_dir = tmp_path_factory.mktemp("tiny_ieee_cis")
    return _build_tiny_ieee_cis_csvs(str(out_dir))
