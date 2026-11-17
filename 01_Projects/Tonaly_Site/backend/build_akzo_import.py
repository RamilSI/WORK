"""Сканирует TDS Akzo Nobel и генерирует JSON + копирует PDF в frontend/docs.

Источник (по умолчанию):
  ~/Documents/Производители/Akzo Nobel/ТДС/tds_folder

Запуск:
  python3 build_akzo_import.py
  python3 build_akzo_import.py --import   # + импорт в SQLite
"""
import argparse
import json
import re
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
DOCS_DIR = PROJECT / "frontend" / "docs"
DATA_DIR = BASE / "data"

DEFAULT_TDS_ROOT = Path.home() / "Documents/Производители/Akzo Nobel/ТДС/tds_folder"

FAMILIES = [
    "INTERGARD",
    "INTERZONE",
    "INTERTHANE",
    "INTERZINC",
    "INTERLINE",
    "CHARTEK",
    "ENVIROLINE",
    "INTERTHERM",
    "INTERSEAL",
]

FAMILY_HINTS = {
    "INTERGARD": ("грунтовка / грунт-эмаль", "эпоксидная", "антикоррозионная"),
    "INTERZONE": ("грунт-эмаль", "эпоксидная", "антикоррозионная"),
    "INTERTHANE": ("эмаль", "полиуретановая", "атмосферостойкая"),
    "INTERZINC": ("грунт", "цинконаполненная", "антикоррозионная"),
    "INTERLINE": ("покрытие", "эпоксидная", "химстойкая"),
    "CHARTEK": ("огнезащита", "эпоксидная", "огнезащитная"),
    "ENVIROLINE": ("покрытие", "эпоксидная", "химстойкая"),
    "INTERTHERM": ("покрытие", "силиконовая", "термостойкая"),
    "INTERSEAL": ("грунт-эмаль", "эпоксидная", "антикоррозионная"),
}

SKIP_RE = re.compile(
    r"копия|схем|заключ|письм|вниист|референс|protocol|evaluation|testing|"
    r"опытн|руковод|introduction|конкурент|акт |замен|presentation|brochure|"
    r"регламент|опи |track record|сравнен|project list|перевод|document|"
    r"рабочие процедуры|тз\.|сетка|список|отзыв|pipetest|доп\.|"
    r"flakeline|linings brochure|pdfdownload|госни|авиагсм|термостойкость для",
    re.I,
)

CODE_RE = re.compile(r"^[A-Za-z0-9]+(?:[A-Z]{1,3})?$")


def normalize_code(raw: str) -> str:
    return re.sub(r"[^a-z0-9]", "", raw.lower())


def extract_product_code(family: str, stem: str) -> str | None:
    s = stem.replace("_", " ").strip()
    m = re.match(rf"{re.escape(family)}[\s_\-]*(.+)$", s, re.I)
    if not m:
        return None
    code = m.group(1).strip()
    code = re.sub(r"\s+rus.*$", "", code, flags=re.I).strip()
    code = code.split()[0] if code.split() else ""
    code = re.sub(r"[^A-Za-z0-9]", "", code)
    if not code or len(code) > 12:
        return None
    if not CODE_RE.match(code):
        return None
    return code


def product_display_name(family: str, code: str) -> str:
    return f"{family} {code.upper()}"


def slug_for(family: str, code: str) -> str:
    return f"{family.lower()}-{normalize_code(code)}"


def score_pdf(path: Path, family: str, code: str) -> int:
    name = path.name.lower()
    score = 0
    if "rus" in name:
        score += 10
    if path.suffix.lower() == ".pdf" and "+" not in name and "td" not in name:
        score += 2
    if path.parent.name == family or path.parent.name.upper() == family:
        score += 3
    if re.search(rf"{family}[\s_\-]*{re.escape(code)}", path.stem, re.I):
        score += 5
    if "eng" in name:
        score -= 3
    if "br" in name:
        score -= 1
    depth = len(path.parts)
    score -= max(0, depth - 8)
    return score


def collect_pdfs(tds_root: Path, family: str) -> list[Path]:
    folder = tds_root / family
    if not folder.exists():
        return []
    pdfs = list(folder.rglob("*.pdf")) + list(folder.rglob("*.PDF"))
    out = []
    for pdf in pdfs:
        rel = pdf.relative_to(folder)
        if SKIP_RE.search(pdf.name) or SKIP_RE.search(str(rel)):
            continue
        if any(p.lower() in ("схемы", "схем", "конкуренты") for p in rel.parts[:-1]):
            continue
        if len(rel.parts) > 2:
            continue
        code = extract_product_code(family, pdf.stem)
        if not code:
            continue
        out.append((pdf, code))
    return out


def pick_best_per_code(pdfs_with_code: list[tuple[Path, str]], family: str) -> dict[str, Path]:
    buckets: dict[str, list[Path]] = {}
    for pdf, code in pdfs_with_code:
        buckets.setdefault(normalize_code(code), []).append(pdf)
    chosen = {}
    for norm, paths in buckets.items():
        code = extract_product_code(family, paths[0].stem) or norm
        best = max(paths, key=lambda p: score_pdf(p, family, code))
        chosen[norm] = best
    return chosen


def build_records(tds_root: Path) -> list[dict]:
    records = []
    seen_slugs = set()

    for family in FAMILIES:
        pdfs = collect_pdfs(tds_root, family)
        picked = pick_best_per_code(pdfs, family)
        ptype, binder, purpose = FAMILY_HINTS.get(family, ("материал", "", ""))

        for norm_code, pdf_path in sorted(picked.items(), key=lambda x: x[0]):
            code = extract_product_code(family, pdf_path.stem) or norm_code
            slug = slug_for(family, code)
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            tds_filename = f"akzo-{slug}.pdf"
            name = product_display_name(family, code)
            badge = "2K Система" if family not in ("CHARTEK",) else "Система"

            records.append({
                "slug": slug,
                "name": name,
                "brand": "akzo",
                "family": family,
                "badge": badge,
                "ptype": ptype.split("/")[0].strip() if "/" in ptype else ptype,
                "binder": binder,
                "purpose": purpose,
                "short_desc": f"{family} — {ptype}",
                "description": f"{name} — промышленное покрытие Akzo Nobel ({ptype}).",
                "specs": [],
                "related": [],
                "tds_file": tds_filename,
                "source_id": f"akzo-tds:{pdf_path.name}",
                "_source_path": str(pdf_path),
            })
    return records


def copy_tds_files(records: list[dict], docs_dir: Path) -> int:
    docs_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for item in records:
        src = Path(item["_source_path"])
        dst = docs_dir / item["tds_file"]
        if not src.exists():
            continue
        shutil.copy2(src, dst)
        copied += 1
    return copied


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tds-root", type=Path, default=DEFAULT_TDS_ROOT)
    parser.add_argument("--import", dest="do_import", action="store_true")
    args = parser.parse_args()

    if not args.tds_root.exists():
        print(f"❌ Папка TDS не найдена: {args.tds_root}")
        raise SystemExit(1)

    records = build_records(args.tds_root)
    copied = copy_tds_files(records, DOCS_DIR)

    export = []
    for r in records:
        export.append({k: v for k, v in r.items() if not k.startswith("_")})

    out_json = DATA_DIR / "products_import_akzo.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8")

    by_family = {}
    for r in export:
        by_family.setdefault(r["family"], 0)
        by_family[r["family"]] += 1

    print(f"✅ Найдено {len(export)} позиций Akzo")
    for fam, cnt in sorted(by_family.items()):
        print(f"   {fam}: {cnt}")
    print(f"✅ PDF скопировано в frontend/docs: {copied}")
    print(f"✅ JSON: {out_json}")

    if args.do_import:
        from import_products import import_file
        import_file(out_json)


if __name__ == "__main__":
    main()
