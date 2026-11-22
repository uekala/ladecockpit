"""Ladenetze in Europa unter dem Namen, den man kennt.

Register und Karten nennen die Firma, die eine Station betreibt („Enel X Way Italia S.r.l.“, „The New
Motion B.V.“). Bekannt ist das Netz aber unter seiner Marke. Diese Tabelle bildet einen Firmennamen,
klein geschrieben und ohne Rechtsform, auf die Marke ab. Namen, die schon mit einer Marke aus
`networks._OPERATOR_NAMES` beginnen („Fastned Deutschland“, „Allego GmbH“), brauchen keinen Eintrag.

Ein Netz ergänzen: eine Zeile, Firmenname klein geschrieben ohne Rechtsform → Marke.
"""
from __future__ import annotations

ALIASES = {
    # Shell
    "newmotion": "Shell Recharge", "the new motion": "Shell Recharge", "new motion": "Shell Recharge",
    # bp
    "aral": "Aral pulse", "bp chargemaster": "bp pulse", "chargemaster": "bp pulse",
    # TotalEnergies
    "total": "TotalEnergies", "total energies": "TotalEnergies",
    # Italy
    "enel x": "Enel X Way", "enel x way": "Enel X Way", "enel x way italia": "Enel X Way",
    "enel x mobility": "Enel X Way", "plenitude": "Plenitude", "eni plenitude": "Plenitude",
    "plenitude on the road": "Plenitude", "free2move esolutions": "Free2Move eSolutions",
    "f2m esolutions": "Free2Move eSolutions", "ewiva": "Ewiva",
    # Spain and Portugal
    "endesa x way": "Endesa X Way", "wenea": "Wenea", "repsol": "Repsol", "powerdot": "Powerdot",
    # France and Benelux
    "sodetrel": "Izivia", "izivia": "Izivia", "vianeo": "Engie Vianeo", "engie vianeo": "Engie Vianeo",
    "eneco": "Eneco eMobility", "eneco emobility": "Eneco eMobility",
    "vattenfall incharge": "Vattenfall InCharge",
    # Austria and Switzerland
    "smatrics": "SMATRICS", "smatrics enbw": "SMATRICS EnBW", "moon": "MOON POWER", "moon power": "MOON POWER",
    "gofast": "GOFAST", "gotthard fastcharge": "GOFAST", "move mobility": "MOVE",
    # Nordics
    "recharge": "Recharge", "recharge infra": "Recharge", "mer": "Mer", "mer norway": "Mer", "mer sweden": "Mer",
    "mer germany": "Mer", "eviny": "Eviny", "circle k": "Circle K", "clever": "Clever",
    # Central and Eastern Europe
    "orlen": "ORLEN Charge", "orlen charge": "ORLEN Charge", "mol": "MOL Plugee", "mol plugee": "MOL Plugee",
}


def brand(name: str | None) -> str | None:
    """Die Marke zu einem Firmennamen ohne Rechtsform, wenn die Tabelle sie kennt."""
    return ALIASES.get(" ".join((name or "").casefold().split()))
