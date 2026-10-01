"""Схемы покрытий: JSON → страницы /schemes и карточки товаров."""
import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "coating_schemes.json"

CATEGORY_META = [
    ("shop", "Домонтажная окраска", "Грунты цеха и межоперационная защита"),
    ("direct", "Грунт-эмали 3 в 1", "Однослойные системы по стали"),
    ("exterior", "Наружные покрытия", "Атмосфера C3–C5, ISO 12944"),
    ("cui", "Под теплоизоляцией", "CUI, до +120 °C"),
    ("heat", "Термостойкие", "Горячие трубы и оборудование"),
    ("immersion", "Погружение и износ", "Splash zone, гидротехника"),
    ("tanks", "Внутренние поверхности резервуаров", "Химстойкие лайнинги"),
]


def _enrich_side(side: dict | None, products: dict[str, dict]) -> dict:
    side = side or {}
    layers = []
    for layer in side.get("layers") or []:
        item = dict(layer)
        slug = (item.get("slug") or "").strip()
        product = products.get(slug) if slug else None
        item["exists"] = bool(product)
        if product:
            item["display_name"] = product["name"]
        else:
            item["display_name"] = item.get("name") or slug
        item["href"] = f"/product/{slug}" if slug else ""
        coats = int(item.get("coats") or 1)
        dft = int(item.get("dft") or 0)
        item["dft_label"] = f"{coats}×{dft}" if coats > 1 else str(dft)
        item["dft_total"] = coats * dft
        layers.append(item)
    return {
        "brand": side.get("brand") or "",
        "code": side.get("code") or "",
        "layers": layers,
        "total_dft": sum(layer["dft_total"] for layer in layers),
    }


def _prepare(raw: dict, products: dict[str, dict]) -> dict:
    competitor = _enrich_side(raw.get("competitor"), products)
    rem = _enrich_side(raw.get("rem"), products)
    return {
        "slug": raw.get("slug", ""),
        "category": raw.get("category", ""),
        "code": raw.get("code") or competitor.get("code") or "",
        "title": raw.get("title", ""),
        "purpose": raw.get("purpose", ""),
        "corrosivity": raw.get("corrosivity", ""),
        "durability": raw.get("durability", ""),
        "total_dft": raw.get("total_dft") or rem.get("total_dft") or competitor.get("total_dft") or 0,
        "temperature": raw.get("temperature", ""),
        "competitor": competitor,
        "rem": rem,
        "others": raw.get("others") or [],
        "advantages": raw.get("advantages") or [],
        "notes": (raw.get("notes") or "").strip(),
    }


@lru_cache(maxsize=1)
def _raw_schemes(mtime: float) -> list[dict]:
    if not DATA_PATH.exists():
        return []
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def load_raw_schemes() -> list[dict]:
    mtime = DATA_PATH.stat().st_mtime if DATA_PATH.exists() else 0
    return _raw_schemes(mtime)


def load_schemes(products: dict[str, dict] | None = None) -> list[dict]:
    products = products or {}
    return [_prepare(item, products) for item in load_raw_schemes()]


def group_schemes(schemes: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {}
    for scheme in schemes:
        buckets.setdefault(scheme["category"], []).append(scheme)
    groups = []
    seen = set()
    for key, title, description in CATEGORY_META:
        items = buckets.get(key) or []
        if not items:
            continue
        groups.append({
            "key": key,
            "title": title,
            "description": description,
            "schemes": items,
        })
        seen.add(key)
    for key, items in buckets.items():
        if key in seen:
            continue
        groups.append({
            "key": key,
            "title": key,
            "description": "",
            "schemes": items,
        })
    return groups


def get_scheme(slug: str, products: dict[str, dict] | None = None) -> dict | None:
    for scheme in load_schemes(products):
        if scheme["slug"] == slug:
            return scheme
    return None


def schemes_for_product(slug: str, products: dict[str, dict] | None = None) -> list[dict]:
    found = []
    for scheme in load_schemes(products):
        layers = scheme["competitor"]["layers"] + scheme["rem"]["layers"]
        if any(layer.get("slug") == slug for layer in layers):
            found.append(scheme)
    return found
