"""Подбор схем по ответам опросного листа.

Правила привязаны к slug схем в coating_schemes.json.
Новая схема без правила попадает в разбор, а не в тихий пропуск.
"""
import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "coating_schemes.json"

# years — нижняя граница срока схемы. 0 значит межоперационный грунт, не срок службы.
# blast — для заявленного срока нужна струя Sa 2½.
RULES = {
    "shop-alkyd-306": {"places": ["shop"], "years": 0, "blast": False, "substrates": ["steel", "hand"]},
    "shop-zinc-5927": {"places": ["shop"], "years": 0, "blast": True, "substrates": ["steel", "hand"]},
    "shop-epoxy-2509": {"places": ["shop"], "years": 0, "blast": False, "substrates": ["steel", "hand"]},
    "shop-epoxy-1052": {"places": ["shop"], "years": 0, "blast": False, "substrates": ["steel", "hand"]},
    "direct-345": {"places": ["indoor", "city"], "years": 5, "blast": False, "substrates": ["steel", "hand"]},
    "exterior-epoxy-740": {"places": ["indoor"], "years": 7, "blast": False, "substrates": ["steel", "hand"]},
    "exterior-alkyd-gf-pf": {"places": ["city", "site"], "years": 5, "blast": False, "substrates": ["steel", "hand"]},
    "exterior-c3-c4-115": {"places": ["city", "site"], "years": 5, "blast": True, "substrates": ["steel", "hand"]},
    "exterior-c3-c4-160": {"places": ["city", "site"], "years": 10, "blast": True, "substrates": ["steel", "hand"]},
    "exterior-c3-c4-200": {"places": ["city", "site"], "years": 15, "blast": True, "substrates": ["steel", "hand"]},
    "exterior-c4-c5-250": {"places": ["site", "harsh"], "years": 15, "blast": True, "substrates": ["steel", "hand"]},
    "exterior-c4-c5-240": {"places": ["site", "harsh"], "years": 15, "blast": True, "substrates": ["steel", "hand"]},
    "exterior-c5-4000": {"places": ["harsh"], "years": 25, "blast": True, "substrates": ["steel", "hand"]},
    "exterior-c5-zinc-epoxy": {"places": ["harsh"], "years": 25, "blast": True, "substrates": ["steel", "hand"]},
    "exterior-bridge": {"places": ["site", "harsh"], "years": 25, "blast": True, "substrates": ["steel", "hand"]},
    "exterior-galvanized": {"places": ["city", "site"], "years": 7, "blast": False, "substrates": ["zinc"]},
    "cui-670hs": {"places": ["insulation"], "years": 15, "blast": True, "substrates": ["steel", "hand"]},
    "heat-228hs": {"places": ["heat"], "years": 15, "blast": True, "substrates": ["steel", "hand"]},
    "heat-2340upc": {"places": ["heat", "insulation"], "years": 15, "blast": True, "substrates": ["steel", "hand"]},
    "immersion-954": {"places": ["water"], "years": 15, "blast": True, "substrates": ["steel", "hand"]},
    "tanks-850": {"places": ["tank"], "years": 15, "blast": True, "substrates": ["steel", "hand"]},
}

# min/max лет схемы, которая остаётся в списке. None — срок не фильтруем.
LIFE_BANDS = {
    "": None,
    "to7": (0, 10),
    "m15": (7, 15),
    "h25": (15, 24),
    "vh": (25, 99),
}

PLACES = ("shop", "indoor", "city", "site", "harsh", "insulation", "heat", "water", "tank")
SUBSTRATES = ("steel", "hand", "zinc")

REVIEW_NOTES = {
    "insulation": "Под изоляцией схему подтверждаем по температуре и по тому, будет ли изоляция мокрой. Ниже ориентир из каталога.",
    "heat": "Для горячей поверхности сверяем рабочую и пиковую температуру. Ниже ориентир из каталога.",
    "water": "Погружение и зону смачивания подбираем по среде и нагрузке. Ниже ориентир, не спецификация.",
    "tank": "Внутренность ёмкости зависит от продукта. Ниже ориентир. Финальную схему собирает инженер.",
}


def _load_raw() -> list[dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _card(raw: dict) -> dict:
    rem = raw.get("rem") or {}
    layers = []
    for layer in rem.get("layers") or []:
        coats = int(layer.get("coats") or 1)
        dft = int(layer.get("dft") or 0)
        thickness = f"{coats}×{dft}" if coats > 1 else str(dft)
        layers.append(f"{layer.get('name')} {thickness} мкм")
    return {
        "slug": raw.get("slug") or "",
        "title": raw.get("title") or "",
        "purpose": raw.get("purpose") or "",
        "corrosivity": raw.get("corrosivity") or "",
        "durability": raw.get("durability") or "",
        "total_dft": raw.get("total_dft") or 0,
        "rem_code": rem.get("code") or "",
        "layers": layers,
        "href": f"/schemes/{raw.get('slug')}",
    }


def catalog() -> list[dict]:
    items = []
    for raw in _load_raw():
        slug = raw.get("slug") or ""
        rule = RULES.get(slug)
        card = _card(raw)
        card["rule"] = rule
        items.append(card)
    return items


def match(place: str = "", substrate: str = "", life: str = "") -> dict:
    place = place if place in PLACES else ""
    substrate = substrate if substrate in SUBSTRATES else ""
    band = LIFE_BANDS.get(life if life in LIFE_BANDS else "")
    if not place:
        return {
            "ready": False,
            "note": "",
            "fit": [],
            "blast": [],
            "unknown": [],
        }

    fit = []
    blast = []
    unknown = []
    for item in catalog():
        rule = item["rule"]
        if not rule:
            unknown.append(item)
            continue
        if place not in rule["places"]:
            continue
        if not substrate and "steel" not in rule["substrates"] and "hand" not in rule["substrates"]:
            continue
        if substrate and substrate not in rule["substrates"]:
            continue
        if band is not None:
            low, high = band
            if not (low <= rule["years"] <= high):
                continue
        public = {k: v for k, v in item.items() if k != "rule"}
        if substrate == "hand" and rule["blast"]:
            blast.append(public)
        else:
            fit.append(public)

    note = REVIEW_NOTES.get(place, "")
    if substrate == "zinc" and not fit and not blast:
        note = "Готовой схемы по оцинковке для этой среды в каталоге нет. Подбор подтверждаем отдельно."
    elif not fit and not blast and not note:
        note = "По этим ответам готовой схемы в каталоге нет. Нужен разбор объекта."
    return {
        "ready": True,
        "note": note,
        "fit": fit,
        "blast": blast,
        "unknown": [{k: v for k, v in item.items() if k != "rule"} for item in unknown if place],
    }
