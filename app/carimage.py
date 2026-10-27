"""A picture of the car, rendered by Tesla's own configurator image service.

The user picks model, trim, paint, wheels and view in the web app. The choice is stored
in the database; without one, the model and its generation are guessed from the VIN in
the charging history. Only image addresses are built here – the browser (or Home
Assistant's frontend) loads the pictures straight from Tesla, so nothing is downloaded
by Ladecockpit and no Tesla request counts against the API budget.

Tesla's image service only renders option sets that belong together and silently
returns an empty or half-drawn picture for anything else. Every combination in the
catalogue below was checked against it (see tests/test_carimage.py for the rules that
keep the catalogue consistent).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import quote

CONFIGURATOR = "https://static-assets.tesla.com/configurator/compositor"
LEGACY = "https://static-assets.tesla.com/v1/compositor/"

KV_KEY = "car_image"

VIEWS = {"front": "STUD_3QTR", "side": "STUD_SIDE", "rear": "STUD_REAR"}
SIZES = (720, 1440, 1920)

# Tesla's own paint names; the same in every language.
PAINTS = {
    "PPSW": "Pearl White Multi-Coat",
    "PBSB": "Solid Black",
    "PX02": "Diamond Black",
    "PMBL": "Obsidian Black Metallic",
    "PMNG": "Midnight Silver Metallic",
    "PMSS": "Silver Metallic",
    "PMTG": "Dolphin Grey Metallic",
    "PMAB": "Brown Metallic",
    "PN00": "Quicksilver",
    "PN01": "Stealth Grey",
    "PN02": "Lunar Silver",
    "PPSB": "Deep Blue Metallic",
    "PB00": "Frost Blue Metallic",
    "PB01": "Glacier Blue",
    "PB02": "Marine Blue",
    "PB03": "Coastal Blue",
    "PPMR": "Red Multi-Coat",
    "PR01": "Ultra Red",
    "PBCW": "Solid White",
    "PDD": "Stainless Steel",
}

TRIM_LABELS = {
    "standard": {"de": "Standard", "en": "Standard"},
    "rwd_lr": {"de": "Hinterradantrieb · Maximale Reichweite", "en": "Rear-Wheel Drive · Long Range"},
    "performance": {"de": "Performance", "en": "Performance"},
    "awd": {"de": "Allradantrieb", "en": "All-Wheel Drive"},
    "rwd": {"de": "Hinterradantrieb", "en": "Rear-Wheel Drive"},
    "plaid": {"de": "Plaid", "en": "Plaid"},
    "cyberbeast": {"de": "Cyberbeast", "en": "Cyberbeast"},
    "any": {"de": "Alle Varianten", "en": "All versions"},
}

VIEW_LABELS = {
    "front": {"de": "Schräg von vorne", "en": "Front three-quarter"},
    "side": {"de": "Seite", "en": "Side"},
    "rear": {"de": "Schräg von hinten", "en": "Rear three-quarter"},
}


@dataclass(frozen=True)
class Fit:
    """One set of wheels on one trim: the interior Tesla needs to render it, and the paints it has."""
    interior: str
    paints: tuple[str, ...]


@dataclass(frozen=True)
class Trim:
    key: str
    code: str
    wheels: dict[str, Fit]  # wheel code → Fit, in the order they are offered


@dataclass(frozen=True)
class Generation:
    key: str
    model: str            # Tesla's model code: m3, my, ms, mx, ct
    name: str             # "Model 3"
    since: int            # first model year
    until: int | None     # last model year, None = still built
    trims: tuple[Trim, ...]
    wheels: dict[str, dict[str, str]]       # code → {"de": …, "en": …}
    # The views Tesla renders, each with the box (x1, y1, x2, y2) the car takes up on the
    # 1920 × 1080 canvas – used to crop the empty margin. None: the image service cannot crop.
    boxes: dict[str, tuple[int, int, int, int] | None] = field(default_factory=dict)
    legacy: bool = False  # old image service (Model S/X before 2021)
    default_trim: str = ""  # shown before the user picks one; the first trim if empty

    @property
    def crop(self) -> dict[str, tuple[int, int, int, int] | None]:
        return {v: _crop(b) for v, b in self.boxes.items()}

    @property
    def views(self) -> tuple[str, ...]:
        return tuple(v for v in VIEWS if v in self.boxes)

    @property
    def paints(self) -> tuple[str, ...]:
        used = {p for t in self.trims for fit in t.wheels.values() for p in fit.paints}
        return tuple(p for p in PAINTS if p in used)

    def label(self, lang: str) -> str:
        if self.until is None:
            years = f"ab {self.since}" if lang == "de" else f"{self.since}+"
        else:
            years = f"{self.since}–{self.until}"
        return f"{self.name} ({years})"

    def trim(self, key: str | None) -> Trim:
        by_key = {t.key: t for t in self.trims}
        return by_key.get(key or "") or by_key.get(self.default_trim) or self.trims[0]


CANVAS = (1920, 1080)
MARGIN = 0.03  # of the car's width, kept around it when cropping


def _crop(box: tuple[int, int, int, int] | None) -> tuple[int, int, int, int] | None:
    """Box the car takes up → Tesla's crop parameter (width, height, x, y) with a small margin."""
    if box is None:
        return None
    x1, y1, x2, y2 = box
    pad = round((x2 - x1) * MARGIN)
    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
    x2, y2 = min(CANVAS[0], x2 + pad), min(CANVAS[1], y2 + pad)
    return (x2 - x1, y2 - y1, x1, y1)


def _fits(interior: str, paints: str, *wheels: str) -> dict[str, Fit]:
    return {w: Fit(interior, tuple(paints.split())) for w in wheels}


def _w(de: str, en: str | None = None) -> dict[str, str]:
    return {"de": de, "en": en or de}


# Paint sets that Tesla's image service has for a trim and its wheels.
_M3H = "PPSW PX02 PN01 PN00 PB02 PR01"
_M3H_PERF = "PPSW PX02 PN01 PN00 PB02 PB00 PR01"
_CLASSIC = "PPSW PBSB PMNG PPSB PPMR"
_MYJ = "PPSW PBSB PX02 PN01 PN00 PB02 PB01 PR01 PPSB"

CATALOG: tuple[Generation, ...] = (
    Generation(
        "m3-2024", "m3", "Model 3", 2024, None,
        trims=(
            Trim("standard", "MT367", {**_fits("IBB7", _M3H, "W38G"), **_fits("IBB7", "PPSW PX02 PN01 PB02 PR01", "W38A")}),
            Trim("rwd_lr", "MT385", {**_fits("IPB12", _M3H, "W38A"),
                                     **_fits("IPB2", "PPSW PBSB PX02 PN01 PN00 PPSB PB02 PR01", "W39S"),
                                     **_fits("IPB12", _M3H, "W39D")}),
            Trim("performance", "MT381", _fits("IPB14", _M3H_PERF, "W30A", "W30P")),
        ),
        wheels={"W38G": _w("18″ Prismata"), "W38A": _w("18″ Photon"), "W39S": _w("19″ Nova"),
                "W39D": _w("19″ Dark Nova"), "W30A": _w("20″ Warp"),
                "W30P": _w("20″ Warp, geschmiedet", "20″ Warp, forged")},
        boxes={"front": (459, 350, 1467, 752), "side": (415, 355, 1501, 697), "rear": (471, 351, 1443, 752)},
        default_trim="rwd_lr",
    ),
    Generation(
        "m3-2017", "m3", "Model 3", 2017, 2023,
        trims=(
            Trim("rwd_lr", "MT322", _fits("IBB1", _CLASSIC, "W40B", "W41B")),
            Trim("performance", "MT317", _fits("IPB1", _CLASSIC, "W33D")),
        ),
        wheels={"W40B": _w("18″ Aero"), "W41B": _w("19″ Sport"), "W33D": _w("20″ Überturbine", "20″ Überturbine")},
        boxes={"front": (470, 350, 1465, 751), "side": (422, 354, 1499, 696), "rear": (471, 350, 1441, 750)},
    ),
    Generation(
        "my-2025", "my", "Model Y", 2025, None,
        trims=(
            Trim("standard", "MTY85", _fits("IBB6", _MYJ + " PB03", "WY18P", "WY19P")),
            Trim("rwd_lr", "MTY90", _fits("IPB12", _MYJ, "WY19P", "WY20B")),
            Trim("performance", "MTY53", _fits("IPB12", _MYJ, "WY21A")),
        ),
        wheels={"WY18P": _w("18″ Aperture"), "WY19P": _w("19″ Crossflow"), "WY20B": _w("20″ Helix 2.0"),
                "WY21A": _w("21″ Arachnid 2.0")},
        boxes={"front": (432, 298, 1507, 753), "side": (400, 310, 1514, 704), "rear": (430, 318, 1472, 773)},
        default_trim="rwd_lr",
    ),
    Generation(
        "my-2020", "my", "Model Y", 2020, 2024,
        trims=(
            Trim("rwd_lr", "MTY07", _fits("INPB0", _CLASSIC + " PN00 PN01 PR01", "WY19B", "WY20P")),
            Trim("performance", "MTY12", _fits("INPB0", _CLASSIC + " PN00 PN01 PR01", "WY21P")),
        ),
        wheels={"WY19B": _w("19″ Gemini"), "WY20P": _w("20″ Induction"), "WY21P": _w("21″ Überturbine")},
        boxes={"front": (450, 304, 1477, 753), "side": (410, 310, 1507, 698), "rear": (455, 305, 1451, 754)},
    ),
    Generation(
        "ms-2021", "ms", "Model S", 2021, None,
        trims=(
            Trim("awd", "MTS20", _fits("IBE00", _CLASSIC + " PR01 PN01 PN02", "WS91", "WS11")),
            Trim("plaid", "MTS19", _fits("IBE00", _CLASSIC + " PR01 PN01", "WS91", "WS11")),
        ),
        wheels={"WS91": _w("19″ Tempest"), "WS11": _w("21″ Arachnid")},
        boxes={"front": (426, 356, 1492, 754), "side": (382, 355, 1539, 698), "rear": (446, 352, 1483, 757)},
    ),
    Generation(
        "ms-2012", "ms", "Model S", 2012, 2020,
        trims=(Trim("any", "", _fits("", _CLASSIC + " PBCW PMBL PMSS PMTG PMAB", "WT19", "WTAS", "WTSG")),),
        wheels={"WT19": _w("19″ Slipstream"), "WTAS": _w("19″ Aero Turbine"), "WTSG": _w("21″ Turbine")},
        boxes={"front": None, "side": None},
        legacy=True,
    ),
    Generation(
        "mx-2021", "mx", "Model X", 2021, None,
        trims=(
            Trim("awd", "MTX20", _fits("IBE00", "PPSW PBSB PMNG PPSB PR01 PN01 PN02", "WX00", "WX20")),
            Trim("plaid", "MTX19", _fits("IBE00", "PPSW PBSB PMNG PPSB PR01 PN01 PN02", "WX00", "WX20")),
        ),
        wheels={"WX00": _w("20″ Cyberstream"), "WX20": _w("22″ Turbine")},
        boxes={"front": (416, 297, 1502, 757), "side": (375, 301, 1541, 699), "rear": (441, 293, 1490, 758)},
    ),
    Generation(
        "mx-2015", "mx", "Model X", 2015, 2020,
        trims=(Trim("any", "", _fits("", _CLASSIC + " PBCW PMBL PMSS", "WT20", "WTSC", "WT22", "WTUT")),),
        wheels={"WT20": _w("20″ Aero Turbine"), "WTSC": _w("20″ Slipstream"), "WT22": _w("22″ Turbine"),
                "WTUT": _w("22″ Onyx")},
        boxes={"front": None, "side": None},
        legacy=True,
    ),
    Generation(
        "ct-2024", "ct", "Cybertruck", 2024, None,
        trims=(
            Trim("awd", "MTC08", _fits("IG01", "PDD", "WH0A", "WH0B", "WH8A")),
            Trim("cyberbeast", "MTC04", _fits("IG01", "PDD", "WH0A", "WH0B")),
            Trim("rwd", "MTC06", _fits("IG01", "PDD", "WH8A", "WH0A", "WH0B")),
        ),
        wheels={"WH0A": _w("20″ Core"), "WH0B": _w("20″ Mantle"), "WH8A": _w("18″ Molten")},
        boxes={"front": (358, 279, 1580, 819), "side": (278, 288, 1651, 733), "rear": (319, 284, 1597, 807)},
    ),
)


def generation(key: str | None) -> Generation | None:
    return next((g for g in CATALOG if g.key == key), None)


# --- VIN -------------------------------------------------------------------------------------
_VIN_MODELS = {"3": "m3", "Y": "my", "S": "ms", "X": "mx", "C": "ct"}
_VIN_YEARS = "ABCDEFGHJKLMNPRSTVWXY"  # 10th character, A = 2010 … Y = 2030


def from_vin(vin: str | None) -> Generation | None:
    """Model and generation from a VIN: 4th character is the model, 10th the model year."""
    if not vin or len(vin) < 10:
        return None
    model = _VIN_MODELS.get(vin[3].upper())
    if not model:
        return None
    code = vin[9].upper()
    year = 2010 + _VIN_YEARS.index(code) if code in _VIN_YEARS else None
    candidates = [g for g in CATALOG if g.model == model]
    if year is not None:
        fitting = [g for g in candidates if g.since <= year and (g.until is None or year <= g.until)]
        if fitting:
            # Overlapping years (e.g. Model Y 2025): prefer the newer generation.
            return max(fitting, key=lambda g: g.since)
    return max(candidates, key=lambda g: g.since) if candidates else None


# --- choice ---------------------------------------------------------------------------------
def normalize(choice: dict | None, vin: str | None = None) -> dict:
    """A complete, renderable choice. Unknown or unfitting parts fall back to sensible defaults."""
    choice = dict(choice or {})
    gen = generation(choice.get("generation")) or from_vin(vin) or CATALOG[0]
    trim = gen.trim(choice.get("trim"))
    paint = choice.get("paint")
    wheel = choice.get("wheel")
    if wheel not in trim.wheels:
        # Keep the paint if possible: take the first wheels that come in it.
        wheel = next((w for w, fit in trim.wheels.items() if paint in fit.paints), next(iter(trim.wheels)))
    fit = trim.wheels[wheel]
    if paint not in fit.paints:
        paint = fit.paints[0]
    view = choice.get("view") if choice.get("view") in gen.views else gen.views[0]
    return {"generation": gen.key, "trim": trim.key, "paint": paint, "wheel": wheel, "view": view}


def name(choice: dict, lang: str) -> str:
    """'Model 3 Performance', 'Model Y', 'Cybertruck Cyberbeast' …"""
    gen = generation(choice["generation"])
    if gen is None:
        return "Tesla"
    if choice["trim"] in ("performance", "plaid", "cyberbeast"):
        return f"{gen.name} {TRIM_LABELS[choice['trim']][lang]}"
    return gen.name


def url(choice: dict, size: int = 1440, view: str | None = None) -> str:
    gen = generation(choice["generation"])
    if gen is None:
        return ""
    view = view if view in gen.views else choice["view"]
    trim = gen.trim(choice["trim"])
    wheel = choice["wheel"]
    size = min(SIZES, key=lambda s: abs(s - size))
    params = {"model": gen.model, "view": VIEWS[view], "size": str(size), "bkba_opt": "1"}
    crop = gen.crop.get(view)
    if crop:
        params["crop"] = ",".join(str(v) for v in crop)
    if gen.legacy:
        options = [choice["paint"], wheel]
        base = LEGACY
    else:
        params["context"] = "design_studio_2"
        params["overlay"] = "0"
        options = ["$" + c for c in (trim.code, choice["paint"], wheel, trim.wheels[wheel].interior)]
        base = CONFIGURATOR
    query = "&".join(f"{k}={quote(v, safe=',')}" for k, v in params.items())
    return f"{base}?{query}&options={','.join(quote(o, safe='$') for o in options)}"


def describe(choice: dict, lang: str, *, auto: bool) -> dict:
    """What the web app and Home Assistant need: name, picture addresses and the choice."""
    gen = generation(choice["generation"])
    return {
        "name": name(choice, lang),
        "url": url(choice, 1440),
        "thumb": url(choice, 720),
        "views": {v: url(choice, 1440, v) for v in (gen.views if gen else ())},
        "choice": choice,
        "auto": auto,
        "labels": {
            "generation": gen.label(lang) if gen else "",
            "trim": TRIM_LABELS[choice["trim"]][lang],
            "paint": PAINTS.get(choice["paint"], choice["paint"]),
            "wheel": gen.wheels[choice["wheel"]][lang] if gen else choice["wheel"],
            "view": VIEW_LABELS[choice["view"]][lang],
        },
    }


def catalog(lang: str) -> list[dict]:
    """Everything the web app needs to offer the choices – only sets Tesla can render."""
    return [{
        "key": g.key,
        "label": g.label(lang),
        "views": [{"key": v, "label": VIEW_LABELS[v][lang]} for v in g.views],
        "trims": [{
            "key": t.key,
            "label": TRIM_LABELS[t.key][lang],
            "wheels": [{"code": w, "label": g.wheels[w][lang],
                        "paints": [{"code": p, "label": PAINTS[p]} for p in fit.paints]}
                       for w, fit in t.wheels.items()],
        } for t in g.trims],
    } for g in CATALOG]


# --- storage ----------------------------------------------------------------------------------
def load_choice(db) -> dict | None:
    raw = db.kv_get(KV_KEY)
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def save_choice(db, choice: dict) -> None:
    db.kv_set(KV_KEY, json.dumps(choice, sort_keys=True))


def reset_choice(db) -> None:
    db.kv_del(KV_KEY)


def current(db, vin: str | None, lang: str) -> dict:
    stored = load_choice(db)
    return describe(normalize(stored, vin), lang, auto=stored is None)
