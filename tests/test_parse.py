import json

from app.tesla import _unwrap, parse_session

RAW = {
    "sessionId": 123,
    "vin": "TESTVIN0000000001",
    "siteLocationName": "Test Site",
    "chargeStartDateTime": "2026-10-21T18:18:00+02:00",
    "chargeStopDateTime": "2026-10-21T18:32:00+02:00",
    "unlatchDateTime": "2026-10-21T18:35:00+02:00",
    "countryCode": "DE",
    "fees": [
        {"feeType": "CHARGING", "currencyCode": "EUR", "uom": "kwh",
         "usageBase": 18.0, "usageTier1": 0, "rateBase": 0.37, "totalDue": 6.66},
    ],
    "invoices": [{"fileName": "inv.pdf", "contentId": "abc", "invoiceType": "IMMEDIATE"}],
}


def test_complete_session():
    s = parse_session(RAW)
    assert s["session_id"] == "123"
    assert s["site"] == "Test Site"
    assert s["start_ts"] == "2026-10-21T16:18:00+00:00"
    assert s["kwh"] == 18.0
    assert s["charge_cost"] == 6.66
    assert s["total"] == 6.66
    assert s["price"] == 0.37
    assert s["currency"] == "EUR"
    assert json.loads(s["invoices"])[0]["id"] == "abc"


def test_pending_session_has_no_amounts():
    raw = {**RAW, "fees": []}
    s = parse_session(raw)
    assert s["kwh"] is None and s["total"] is None and s["price"] is None


def test_tiers_and_idle_fee():
    raw = {**RAW, "fees": [
        {"feeType": "CHARGING", "currencyCode": "USD", "uom": "kwh",
         "usageBase": 10, "usageTier1": 5, "totalBase": 4.0, "totalTier1": 2.5},
        {"feeType": "PARKING", "currencyCode": "USD", "uom": "min", "totalDue": 3.0},
    ]}
    s = parse_session(raw)
    assert s["kwh"] == 15
    assert s["charge_cost"] == 6.5
    assert s["idle_fee"] == 3.0
    assert s["total"] == 9.5
    assert s["currency"] == "USD"


def test_missing_id_is_ignored():
    assert parse_session({"fees": []}) is None


def test_unwrap_variants():
    items = [{"sessionId": 1}, {"sessionId": 2}]
    assert _unwrap({"response": {"data": items, "totalResults": 2}}) == (items, 2)
    assert _unwrap({"data": items}) == (items, None)
    assert _unwrap(items) == (items, None)
    assert _unwrap({"response": None}) == ([], None)
