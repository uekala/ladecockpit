"""Charging networks in Europe by the name people know them.

Registers and maps name the company that runs a station ("Enel X Way Italia S.r.l.", "The New
Motion B.V."). People know the network by its brand. This table maps a company name, written in
lower case and without its legal form, to the brand. Names that already start with a brand from
`networks._OPERATOR_NAMES` ("Fastned Deutschland", "Allego GmbH") need no entry.

To add a network: one line, company name in lower case without legal form → brand.
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
    """The brand for a company name without its legal form, if the table has it."""
    return ALIASES.get(" ".join((name or "").casefold().split()))
