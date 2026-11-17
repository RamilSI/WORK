"""Миграция SQLite: новые поля products + backfill Rem Color."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "tonal.db"

REM_FAMILIES = {
    "pox": "POX",
    "lux": "LUX",
    "pur": "PUR",
    "zink": "ZINK",
    "cryl": "CRYL",
    "vinyl": "VINYL",
}


def family_from_slug(slug: str) -> str:
    parts = (slug or "").split("-")
    if len(parts) < 2:
        return ""
    key = parts[1]
    return REM_FAMILIES.get(key, key.upper())


def column_names(conn):
    return {row[1] for row in conn.execute("PRAGMA table_info(products)")}


def migrate():
    conn = sqlite3.connect(DB_PATH)
    try:
        cols = column_names(conn)
        additions = [
            ("brand", "TEXT DEFAULT 'rem-color'"),
            ("family", "TEXT DEFAULT ''"),
            ("tds_file", "TEXT DEFAULT ''"),
            ("source_id", "TEXT DEFAULT ''"),
            ("analog_json", "TEXT DEFAULT ''"),
        ]
        for name, typedef in additions:
            if name not in cols:
                conn.execute(f"ALTER TABLE products ADD COLUMN {name} {typedef}")

        rows = conn.execute("SELECT id, slug, brand, family, tds_file FROM products").fetchall()
        for row_id, slug, brand, family, tds_file in rows:
            slug = slug or ""
            new_brand = brand or "rem-color"
            if slug.startswith("rem-") or slug.startswith("rem"):
                new_brand = "rem-color"
            new_family = family or family_from_slug(slug)
            new_tds = tds_file or f"tds-{slug}.pdf"
            conn.execute(
                "UPDATE products SET brand=?, family=?, tds_file=? WHERE id=?",
                (new_brand, new_family, new_tds, row_id),
            )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        print(f"✅ Миграция OK. {count} товаров в БД.")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
