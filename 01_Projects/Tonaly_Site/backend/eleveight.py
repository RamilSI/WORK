"""Каталог Eleveight во «Вне работы»: JSON → список и карточки моделей."""
import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "eleveight.json"
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

CATEGORIES = [
    ("kites", "Кайты", "Купола под фрирайд, лёгкий ветер, волну и big air."),
    ("boards", "Кайтборды", "Твинтипы Eleveight: от спокойного фрирайда до более жёстких досок."),
    ("bars", "Планки", "CS и Auto Bar под кайты Eleveight. Длину подтверждаем при заказе."),
    ("wings", "Винги", "Если нужен wingfoil на тот же спот — тоже через Романа."),
]

CATEGORY_TITLE = {key: title for key, title, _ in CATEGORIES}


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in (text or "").split("\n\n") if part.strip()]


@lru_cache(maxsize=1)
def _raw(mtime: float) -> list[dict]:
    if not DATA_PATH.exists():
        return []
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _prepare(raw: dict) -> dict:
    slug = raw.get("slug") or ""
    image = f"/img/offwork/eleveight/{slug}.jpg"
    disk = FRONTEND_DIR / image.lstrip("/")
    return {
        "slug": slug,
        "name": raw.get("name") or "",
        "category": raw.get("category") or "",
        "category_title": CATEGORY_TITLE.get(raw.get("category") or "", ""),
        "badge": raw.get("badge") or "",
        "meta": raw.get("meta") or "",
        "short_desc": raw.get("short_desc") or "",
        "who": (raw.get("who") or "").strip(),
        "sizes": [item for item in (raw.get("sizes") or []) if item],
        "facts": [item for item in (raw.get("facts") or []) if item],
        "body_paragraphs": _paragraphs(raw.get("body") or ""),
        "video": (raw.get("video") or "").strip(),
        "video_title": (raw.get("video_title") or "").strip(),
        "official": (raw.get("official") or "").strip(),
        "image": image if disk.is_file() else "",
    }


def load_eleveight() -> list[dict]:
    mtime = DATA_PATH.stat().st_mtime if DATA_PATH.exists() else 0
    return [_prepare(raw) for raw in _raw(mtime)]


def get_eleveight(slug: str) -> dict | None:
    for item in load_eleveight():
        if item["slug"] == slug:
            return item
    return None


def related_eleveight(slug: str, limit: int = 4) -> list[dict]:
    current = get_eleveight(slug)
    if not current:
        return []
    items = [
        item for item in load_eleveight()
        if item["category"] == current["category"] and item["slug"] != slug
    ]
    return items[:limit]


def group_eleveight(items: list[dict] | None = None) -> list[dict]:
    by_cat = {}
    for item in items or load_eleveight():
        by_cat.setdefault(item["category"], []).append(item)
    groups = []
    for key, title, description in CATEGORIES:
        products = by_cat.get(key) or []
        if products:
            groups.append({
                "key": key,
                "title": title,
                "description": description,
                "products": products,
            })
    return groups
