"""Окрасочное оборудование: JSON → вкладка каталога и карточки /product."""
import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "equipment.json"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

CATEGORY_META = [
    ("guns", "Пистолеты", "Безвоздушные распылители высокого давления под промышленные покрытия"),
    ("tips", "Сопла XHD", "Оригинальные реверсивные сопла Graco XHD RAC до 500 бар"),
    ("consumables", "Фильтры, ремкомплекты и рукава", "Расходники к пистолетам HANDOK / Graco и линии 500 бар"),
]


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in (text or "").split("\n\n") if part.strip()]


def _resolve_image(raw_path: str) -> str:
    image = (raw_path or "").strip()
    if not image.startswith("/"):
        return ""
    disk = FRONTEND_DIR / image.lstrip("/")
    return image if disk.is_file() else ""


def _prepare(raw: dict) -> dict:
    desc = (raw.get("description") or "").strip()
    paragraphs = _paragraphs(desc)
    short = (raw.get("short_desc") or "").strip()
    if not short and paragraphs:
        short = paragraphs[0]
    body = paragraphs[1:] if paragraphs and short and paragraphs[0] == short else [p for p in paragraphs if p != short]
    purpose = (raw.get("purpose") or "").strip()
    ptype = (raw.get("ptype") or "").strip()
    badge = (raw.get("badge") or "").strip()
    tds_file = (raw.get("tds_file") or "").strip()
    docs_path = FRONTEND_DIR / "docs" / tds_file if tds_file else None
    if tds_file and docs_path and not docs_path.is_file():
        tds_file = ""
    image = _resolve_image(raw.get("image") or "")
    benefits = [item for item in (raw.get("benefits") or []) if item]
    family = (raw.get("family") or "").strip().upper() or "EQUIPMENT"
    return {
        "slug": raw.get("slug", ""),
        "name": raw.get("name", ""),
        "brand": "equipment",
        "kind": "equipment",
        "family": family,
        "category": raw.get("category", ""),
        "badge": badge,
        "type": ptype,
        "binder": "",
        "purpose": purpose,
        "short_desc": short,
        "description": desc,
        "body_paragraphs": body,
        "application_tag": purpose,
        "application": desc,
        "benefits": benefits,
        "specs": raw.get("specs") or [],
        "related": raw.get("related") or [],
        "tds_file": tds_file,
        "docs_label": (raw.get("docs_label") or "").strip() or "Технический лист (PDF)",
        "image": image,
        "has_image": bool(image),
        "analog": None,
        "part_no": (raw.get("part_no") or "").strip(),
    }


@lru_cache(maxsize=1)
def _raw_equipment(mtime: float) -> list[dict]:
    if not DATA_PATH.exists():
        return []
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def load_equipment() -> list[dict]:
    mtime = DATA_PATH.stat().st_mtime if DATA_PATH.exists() else 0
    return [_prepare(item) for item in _raw_equipment(mtime)]


def group_equipment(items: list[dict] | None = None) -> list[dict]:
    items = items if items is not None else load_equipment()
    buckets: dict[str, list[dict]] = {}
    for item in items:
        buckets.setdefault(item["category"], []).append(item)
    groups = []
    seen = set()
    for key, title, description in CATEGORY_META:
        group_items = buckets.get(key) or []
        if not group_items:
            continue
        groups.append({
            "key": key,
            "title": title,
            "description": description,
            "products": group_items,
        })
        seen.add(key)
    for key, group_items in buckets.items():
        if key in seen:
            continue
        groups.append({
            "key": key,
            "title": key,
            "description": "",
            "products": group_items,
        })
    return groups


def get_equipment(slug: str) -> dict | None:
    for item in load_equipment():
        if item["slug"] == slug:
            return item
    return None
