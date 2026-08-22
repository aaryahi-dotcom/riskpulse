"""Regression test for the WS broadcast payload's shap_reasons field.

checklist 4.4 ("Plain-English driver summary"): the frontend's live feed
renders human-readable SHAP reason sentences straight from the
/ws/transactions broadcast, not just from the direct HTTP score response.
That broadcast happens inside a try/except that silently swallows failures
(routers/score.py), so a bug in serializing shap_reasons onto the socket
would never fail a plain HTTP-only test — it would just degrade the live
feed silently. This test opens a real WS connection first, so the broadcast
actually has a subscriber, then asserts the frame it receives carries
shap_reasons in the same shape the HTTP response does.
"""
from __future__ import annotations

from .conftest import make_score_payload


def test_ws_broadcast_carries_shap_reasons(client, auth_headers):
    with client.websocket_connect("/ws/transactions") as ws:
        resp = client.post(
            "/api/v1/score",
            json=make_score_payload(sender_id="ws_shap_reasons_sender", receiver_id="ws_shap_reasons_receiver@ybl"),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        frame = ws.receive_json()

    assert frame["type"] == "score"
    assert frame["txn_id"] == body["txn_id"]
    assert "shap_reasons" in frame
    assert frame["shap_reasons"] == body["shap_reasons"]
    if frame["shap_reasons"]:
        first = frame["shap_reasons"][0]
        assert set(first.keys()) == {"feature", "contribution", "reason"}
        assert isinstance(first["reason"], str) and first["reason"]
