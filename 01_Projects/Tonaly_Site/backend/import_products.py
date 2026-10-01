"""Импорт товаров из JSON (Akzo, доп. Rem Color).

Формат файла data/products_import.json:
[
  {
    "slug": "intergard-263",
    "name": "INTERGARD 263",
    "brand": "akzo",
    "family": "INTERGARD",
    "badge": "2K Система",
    "ptype": "грунтовка",
    "binder": "эпоксидная",
    "purpose": "антикоррозионная",
    "short_desc": "...",
    "description": "...",
    "specs": [{"name": "...", "value": "..."}],
    "related": ["intergard-269"],
    "tds_file": "tds-intergard-263.pdf",
    "source_id": "tonaly-123"
  }
]
"""
import json
import sys
from pathlib import Path

from database import SessionLocal, Base, engine
from models import Product

DATA_DIR = Path(__file__).resolve().parent / "data"


def upsert_product(db, item: dict):
    slug = item["slug"].strip()
    existing = db.query(Product).filter(Product.slug == slug).first()
    fields = {
        "name": item.get("name", slug),
        "badge": item.get("badge", ""),
        "ptype": item.get("ptype", ""),
        "binder": item.get("binder", ""),
        "purpose": item.get("purpose", ""),
        "short_desc": item.get("short_desc", ""),
        "description": item.get("description", ""),
        "specs": json.dumps(item.get("specs", []), ensure_ascii=False),
        "related": json.dumps(item.get("related", []), ensure_ascii=False),
        "brand": item.get("brand", "akzo"),
        "family": item.get("family", "").upper(),
        "tds_file": item.get("tds_file", f"tds-{slug}.pdf"),
        "source_id": item.get("source_id", ""),
        "analog_json": json.dumps(item.get("analog") or {}, ensure_ascii=False) if item.get("analog") else "",
    }
    if existing:
        for key, value in fields.items():
            setattr(existing, key, value)
        return "updated"
    db.add(Product(slug=slug, **fields))
    return "created"


def import_file(path: Path):
    Base.metadata.create_all(bind=engine)
    items = json.loads(path.read_text(encoding="utf-8"))
    db = SessionLocal()
    created, updated = 0, 0
    try:
        for item in items:
            result = upsert_product(db, item)
            if result == "created":
                created += 1
            else:
                updated += 1
        db.commit()
        print(f"✅ Импорт {path.name}: +{created} новых, {updated} обновлено")
    except Exception as exc:
        db.rollback()
        print(f"❌ Ошибка: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR / "products_import.json"
    if not target.exists():
        print(f"Файл не найден: {target}")
        print("Создайте backend/data/products_import.json для пакетного импорта Akzo.")
        sys.exit(1)
    import_file(target)
