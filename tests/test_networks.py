import json

from app.db import DB
from app.networks import MULTIPASS, SUPERCHARGER, classify, unknown_keys
from app.sync import SyncService
from app.tesla import parse_session

# Shape of a real Supercharger record (values made up)
SUPERCHARGER_RAW = {
    "billingType": "IMMEDIATE",
    "chargeStartDateTime": "2026-10-22T22:07:13+02:00",
    "chargeStopDateTime": "2026-10-22T22:13:05+02:00",
    "countryCode": "DE",
    "fees": [
        {"currencyCode": "EUR", "feeType": "CHARGING", "isPaid": True, "netDue": 2.23,
         "pricingType": "PAYMENT", "rateBase": 0.37, "sessionFeeId": 1, "status": "PAID",
         "totalBase": 2.23, "totalDue": 2.23, "uom": "kwh", "usageBase": 6.05},
        {"currencyCode": "EUR", "feeType": "CONGESTION", "isPaid": True, "netDue": 0,
         "pricingType": "NO_CHARGE", "sessionFeeId": 2, "status": "PAID", "totalDue": 0, "uom": "min"},
    ],
    "invoices": [{"contentId": "abc", "fileName": "inv.pdf", "invoiceType": "IMMEDIATE"}],
    "sessionId": 42,
    "siteLocationName": "Partnerstadt, Germany",
    "unlatchDateTime": "2026-10-22T22:14:00+02:00",
    "vehicleMakeType": "TSLA",
    "vin": "TESTVIN0000000001",
}


def test_plain_supercharger():
    assert classify(SUPERCHARGER_RAW) == (SUPERCHARGER, None)   # "Partner" in the site name is ignored
    assert unknown_keys(SUPERCHARGER_RAW) == []
    assert classify(None) == (SUPERCHARGER, None)


def test_multipass_hints():
    cases = [
        {**SUPERCHARGER_RAW, "billingType": "MONTHLY"},
        {**SUPERCHARGER_RAW, "invoices": [{"contentId": "x", "invoiceType": "AGGREGATED"}]},
        {**SUPERCHARGER_RAW, "chargingNetwork": "Hyper Charge GmbH"},
        {**SUPERCHARGER_RAW, "fees": [{**SUPERCHARGER_RAW["fees"][0], "pricingType": "ROAMING"}]},
        {**SUPERCHARGER_RAW, "programType": "MULTIPASS"},
        {**SUPERCHARGER_RAW, "siteLocationName": "EnBW Schnellladepark Köln, Germany"},
        {**SUPERCHARGER_RAW, "siteLocationName": "IONITY Aachen-Land"},
    ]
    for raw in cases:
        network, reason = classify(raw)
        assert network == MULTIPASS and reason, raw


def test_network_flows_into_db_event_and_csv(settings, tmp_path):
    db = DB(tmp_path / "n.db")
    db.upsert_session(parse_session(SUPERCHARGER_RAW), "new")
    db.upsert_session(parse_session({**SUPERCHARGER_RAW, "sessionId": 43, "billingType": "MONTHLY",
                                     "siteLocationName": "Hyper Charge Musterstadt"}), "new")
    by_id = {s["session_id"]: s for s in db.sessions()}
    assert by_id["42"]["network"] == SUPERCHARGER
    assert by_id["43"]["network"] == MULTIPASS and "billingType" in by_id["43"]["network_reason"]
    assert "raw" not in by_id["43"]

    sync = SyncService(settings, db, tesla=None, ha=None)
    payload = sync.event_payload(by_id["43"])
    assert payload["network"] == MULTIPASS and payload["text"].startswith("MultiPass · ")
    assert sync.event_payload(by_id["42"])["network"] == SUPERCHARGER
    json.dumps(payload)

    from app.export import sessions_csv
    rows = sessions_csv(db.sessions(), settings).lstrip("﻿").splitlines()
    assert rows[0].endswith(",Network")
    assert {r.split(",")[-1] for r in rows[1:]} == {"Supercharger", "MultiPass"}
