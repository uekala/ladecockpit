"""Amounts of a session from the raw Tesla record: paid, list price, credits, net."""
from __future__ import annotations


def _num(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


_TIERS = ("Base", "Tier1", "Tier2", "Tier3", "Tier4")


def fee_total(fee: dict) -> float:
    total = _num(fee.get("totalDue"))
    if total is None:
        total = _num(fee.get("netDue"))
    if total is None:
        total = sum(_num(fee.get("total" + t)) or 0.0 for t in _TIERS)
    return total


def price_details(raw: dict | None) -> dict:
    """List price, credits and net amount of one session.

    totalDue is what was paid. When Tesla credits (e.g. free Supercharging that came with
    the car) covered part of a session, the paid price per kWh says nothing about the
    Supercharger, so price comparisons use the list rate (usage × rate per tier) instead.
    netDue is the amount without VAT.
    """
    out = {"list_cost": None, "credit": 0.0, "credit_kwh": None, "net_total": None}
    if not raw:
        return out
    # Tesla also names the free energy: "credit": {"energyApplied": 30, "distance": 150, ...}
    credit_info = raw.get("credit") if isinstance(raw.get("credit"), dict) else {}
    credit_kwh = _num(credit_info.get("energyApplied"))
    if credit_kwh:
        out["credit_kwh"] = credit_kwh
    list_cost = paid = net = 0.0
    have_rate = have_net = credit_flag = False
    for fee in raw.get("fees") or []:
        n = _num(fee.get("netDue"))
        if n is not None:
            net += n
            have_net = True
        if str(fee.get("feeType") or "").upper() != "CHARGING":
            continue
        ptype = str(fee.get("pricingType") or "").upper()
        credit_flag = credit_flag or "CREDIT" in ptype or "FREE" in ptype
        if str(fee.get("uom") or "kwh").lower() != "kwh":
            continue
        for tier in _TIERS:
            usage, rate = _num(fee.get("usage" + tier)), _num(fee.get("rate" + tier))
            if usage and rate is not None:
                list_cost += usage * rate
                have_rate = True
        paid += fee_total(fee)
    if have_rate:
        out["list_cost"] = round(list_cost, 2)
        credit = list_cost - paid
        if credit > 0.05 and (credit_flag or credit_kwh or credit > 0.5):
            out["credit"] = round(credit, 2)
    if have_net:
        out["net_total"] = round(net, 2)
    return out
