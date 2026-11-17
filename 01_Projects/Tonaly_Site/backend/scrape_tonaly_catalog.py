"""Сбор полного каталога Akzo Nobel с tonaly.ru → JSON для import_products.

Запуск:
  python3 scrape_tonaly_catalog.py
  python3 scrape_tonaly_catalog.py --import
  python3 scrape_tonaly_catalog.py --download-pdf
"""
import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from rem_analog import resolve_rem_slug

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
DOCS_DIR = BASE.parent / "frontend" / "docs"
SITE = "https://tonaly.ru"

FAMILY_PAGES = {
    "CEILCOTE", "CHARTEK", "ENVIROLINE", "INTERBOND", "INTERCHAR", "INTERCRETE",
    "INTERCURE", "INTERFINE", "INTERGARD", "INTERLAC", "INTERLINE", "INTERPLATE",
    "INTERPLUS", "INTERPRIME", "INTERSEAL", "INTERSHEEN", "INTERSHIELD",
    "INTERTHANE", "INTERTHERM", "INTERTUF", "INTERZINC", "INTERZONE", "POLIBRID",
    "Catalog", "tests",
}

NON_PRODUCT = {
    "Блог", "Контакты", "Отзывы", "Услуги", "Справочник", "Контроль-качества",
    "Домонтажная-окраска", "Наружные-покрытия", "Покрытия-под-теплоизоляцией",
    "Термостойкие-покрытия", "Внутренние-покрытия", "interzone-954-1",
    "ОГНЕЗАЩИТА-1", "Покрытия-по-бетону", "Восстановление-бетона",
    "Износоустойчивые-подводные-и-зоны-переменного-смачивания",
    "Покрытия-для-внутренних-поверхностей-резервуаров", "Термостойкие-покрытие",
    "Огнезащита", "Целлюлозное-горение", "Углеводородное-горение",
    "Промежуточные-грунты", "Финишные-покрытия",
}

FAMILY_HINTS = {
    "CEILCOTE": ("покрытие", "эпоксидная", "химстойкая"),
    "CHARTEK": ("огнезащита", "эпоксидная", "огнезащитная"),
    "ENVIROLINE": ("покрытие", "эпоксидная", "химстойкая"),
    "INTERBOND": ("грунт-эмаль", "эпоксидная", "антикоррозионная"),
    "INTERCHAR": ("огнезащита", "эпоксидная", "огнезащитная"),
    "INTERCRETE": ("состав", "эпоксидная", "для бетона"),
    "INTERCURE": ("грунт", "эпоксидная", "антикоррозионная"),
    "INTERFINE": ("эмаль", "полиуретановая", "атмосферостойкая"),
    "INTERGARD": ("грунтовка", "эпоксидная", "антикоррозионная"),
    "INTERLAC": ("эмаль", "алкидная", "атмосферостойкая"),
    "INTERLINE": ("покрытие", "эпоксидная", "химстойкая"),
    "INTERPLATE": ("грунт-эмаль", "эпоксидная", "антикоррозионная"),
    "INTERPLUS": ("грунт", "эпоксидная", "антикоррозионная"),
    "INTERPRIME": ("грунт", "эпоксидная", "антикоррозионная"),
    "INTERSEAL": ("грунт-эмаль", "эпоксидная", "антикоррозионная"),
    "INTERSHEEN": ("эмаль", "алкидная", "атмосферостойкая"),
    "INTERSHIELD": ("грунт-эмаль", "эпоксидная", "антикоррозионная"),
    "INTERTHANE": ("эмаль", "полиуретановая", "атмосферостойкая"),
    "INTERTHERM": ("покрытие", "силиконовая", "термостойкая"),
    "INTERTUF": ("эмаль", "полиуретановая", "атмосферостойкая"),
    "INTERZINC": ("грунт", "цинконаполненная", "антикоррозионная"),
    "INTERZONE": ("грунт-эмаль", "эпоксидная", "антикоррозионная"),
    "POLIBRID": ("покрытие", "полиуретановая", "химстойкая"),
}

KNOWN_FAMILIES = sorted(FAMILY_HINTS.keys(), key=len, reverse=True)

FOOTER_MARKERS = (
    "Офис в г.", "Офис в г", "Дополнительная информация о продукте",
    "Адрес в Краснодарском", "e-mail:", "inbox@tonaly.ru", "Контакты",
    "Отправить запрос", "Я хочу получать рассылку",
)

SKIP_SPEC = {"имя", "эл. почта", "сообщение", "отправить запрос", "я хочу получать рассылку"}


def clean_description(text: str) -> str:
    for marker in FOOTER_MARKERS:
        idx = text.find(marker)
        if idx > 0:
            text = text[:idx]
    return re.sub(r"\n{3,}", "\n\n", text).strip()



# Позиции из меню «КАТАЛОГ» на tonaly.ru (резерв при ошибках парсинга главной)
CATALOG_PATHS = [
    "CEILCOTE-2000", "CEILCOTE-370HT", "CEILCOTE-380", "CEILCOTE140", "CEILCOTE180",
    "CEILCOTE282HB", "CEILCOTE_242_FLAKELINE", "CHARTEK-1709", "CHARTEK-2218",
    "ENVIROLINE-405HTR", "INTERBOND-1202UPC", "INTERBOND-2340UPC",
    "INTERCHAR-2060", "INTERCHAR-2090", "INTERCHAR-212",
    "Двухкомпонентный-эпоксидный-грунт-с-фосфатом-цинка/железной-слюдкой-производимый-по-собственной-полимерной-технологии-которая-обеспечивает-быстрое-отверждение-и-нанесение-следующего-слоя-даже-в-условиях-низких-температур-Высокое-содержание-сухого-остатка-и-низкое-летучих-органических-соединений",
    "Intercure-200HS", "Intercure-99", "Intercure-420", "Intercure-420HS", "Intercure-4500",
    "INTERFINE-878", "Interfine-979", "Interfine-1080",
    "INTERGARD-263", "Intergard-269", "Intergard-251", "Intergard-251HS", "Intergard-2509",
    "Intergard-2510", "Intergard-2511", "Intergard_345", "Intergard-740", "Intergard-475HS",
    "Intergard_821",
    "INTERLAC-665", "Interlac-789", "INTERLAC-665-1",
    "INTERLINE_850", "Interline-921", "INTERLINE-925", "Interline_994", "INTERLINE-982",
    "INTERLINE-955", "Interline-399", "INTERLINE-984", "INTERLINE-975", "INTERLINE-984C",
    "interplate_-855", "Interplate-937", "Interplate-5927",
    "Interplus-_356", "Interplus-256",
    "INTERPRIME-198", "INTERPRIME-306",
    "Interseal_1052", "Interseal-670HS",
    "INTERSHEEN_579",
    "INTERSHIELD-300", "INTERSHIELD-4000USP",
    "INTERTHANE-990E", "INTERTHANE-990SG", "Interthane-870", "Interthane-990",
    "Interthane-1070",
    "INTERTHERM-228HS", "INTERTHERM-875", "INTERTHERM-3350", "Intertherm-50", "Intertherm-7050",
    "Interzinc-22", "Interzinc-42", "Interzinc-52", "Interzinc-52E",
    "INTERZON-101", "INTERZONE-485", "INTERZONE-505", "INTERZONE-954GF",
    "Interzone-1000", "Interzone-954",
    "POLIBRID-705E",
]


def fetch(url: str, timeout: int = 45, retries: int = 5) -> str:
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; TonalCatalogBot/1.0)",
                    "Accept-Language": "ru-RU,ru;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_err = exc
            time.sleep(1.2 * (attempt + 1))
    raise last_err


def strip_html(text: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def catalog_paths(html: str) -> list[str]:
    links = re.findall(r'href="([^"#]+/)"', html)
    paths = []
    for href in links:
        if href.startswith("http"):
            path = href.replace(SITE + "/", "").replace(SITE, "")
        else:
            path = href
        path = path.strip("/")
        if not path or path in FAMILY_PAGES or path in NON_PRODUCT:
            continue
        if path.startswith("1-") or path.startswith("2-"):
            continue
        if "%" in path or any(ord(c) > 127 for c in path[:3] if c.isalpha()):
            # кириллические URL — не каталог материалов
            if not re.match(r"^[A-Za-z0-9_\-]+$", path.split("/")[0]):
                continue
        if "/" in path:
            continue
        if path in ("en", "zh3"):
            continue
        paths.append(path)
    merged = sorted(set(paths) | set(CATALOG_PATHS))
    return merged


def slug_from_path(path: str) -> str:
    seg = path.strip("/").split("/")[-1]
    seg = seg.replace("_", "-")
    m = re.match(r"^([a-z]+)[\-](.+)$", seg, re.I)
    if m:
        family = m.group(1).lower()
        code = re.sub(r"[^a-z0-9]", "", m.group(2).lower())
        return f"{family}-{code}" if code else family
    return re.sub(r"[^a-z0-9]+", "-", seg.lower()).strip("-")


def slug_from_name(name: str) -> str:
    parts = name.strip().split()
    if len(parts) < 2:
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    family = parts[0].lower()
    code = re.sub(r"[^a-z0-9]", "", parts[1].lower())
    return f"{family}-{code}"


def slug_for(path: str, name: str) -> str:
    return slug_from_path(path) or slug_from_name(name)


def family_from_name(name: str) -> str:
    upper = name.upper()
    for fam in KNOWN_FAMILIES:
        if upper.startswith(fam + " ") or upper == fam:
            return fam
    m = re.match(r"([A-Z]+)", name.upper())
    return m.group(1) if m else ""


def extract_analog(html: str) -> dict | None:
    """Блок «Внимание! протестирован аналог …» со ссылкой на Rem Color."""
    low = html.lower()
    if "протестирован" not in low or "аналог" not in low:
        return None

    notice = ""
    for m in re.finditer(r"<h5[^>]*>(.*?)</h5>", html, re.S | re.I):
        t = strip_html(m.group(1))
        if "протестирован" in t.lower() and "аналог" in t.lower():
            notice = clean_description(t)
            break

    start = low.find("протестирован")
    chunk = html[start:start + 4000] if start >= 0 else html

    href = ""
    name = ""
    for m in re.finditer(r"<a[^>]+href=\"([^\"]+)\"[^>]*>(.*?)</a>", chunk, re.S | re.I):
        u = m.group(1).strip()
        if "detalystaly.ru" in u.lower() or re.search(r"/product/rem[-_]", u, re.I):
            href = u
            name = strip_html(m.group(2))
            break

    note = ""
    for m in re.finditer(r"<strong>(.*?)</strong>", chunk, re.S | re.I):
        t = strip_html(m.group(1))
        if "совпадение" in t.lower():
            note = t
            break

    if not name:
        m = re.search(
            r"(РЕМ[-\s][А-ЯЁA-Z0-9\s\-]+(?:HS|AS|E)?)",
            re.sub(r"<[^>]+>", " ", chunk),
            re.I,
        )
        if m:
            name = m.group(1).strip()

    if not notice and not name:
        return None
    return {"notice": notice, "name": name, "url": href, "note": note}


def extract_body_paragraphs(html: str) -> list[str]:
    """Основные абзацы описания — часто в <li> на tonaly.ru."""
    skip_words = (
        "офис в", "тел.:", "e-mail", "адрес в", "отправить запрос",
        "презентация материала", "фотоотчет", "внимание!", "протестирован",
        "дополнительная информация",
    )
    items = []
    for m in re.finditer(r"<li>(.*?)</li>", html, re.S | re.I):
        t = strip_html(m.group(1))
        if len(t) < 25:
            continue
        low = t.lower()
        if any(s in low for s in skip_words):
            continue
        if t not in items:
            items.append(t)
    return items


def meta_description(html: str, name: str) -> str:
    m = re.search(r'<meta name="description" content="([^"]+)"', html, re.I)
    if not m:
        return ""
    text = strip_html(m.group(1))
    prefix = (name or "").strip()
    if prefix and text.lower().startswith(prefix.lower()):
        text = text[len(prefix):].lstrip(". ")
    return text.strip()


def parse_product_page(html: str) -> dict:
    title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
    name = strip_html(title_m.group(1)) if title_m else ""

    h1_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
    if h1_m:
        name = strip_html(h1_m.group(1)) or name

    list_paras = extract_body_paragraphs(html)
    meta = meta_description(html, name)

    if list_paras:
        short_desc = list_paras[0]
        description = "\n\n".join(list_paras)
    else:
        short_parts = []
        for m in re.finditer(r"<h5[^>]*class=\"[^\"]*\"[^>]*>(.*?)</h5>", html, re.S | re.I):
            t = strip_html(m.group(1))
            if t and len(t) > 10 and t.upper() != name.upper():
                if not any(s in t.lower() for s in ("дополнительная информация", "внимание", "фотоотчет")):
                    short_parts.append(t)

        extra_text = []
        for m in re.finditer(r"<p[^>]*class=\"wb-stl[^\"]*\"[^>]*>(.*?)</p>", html, re.S | re.I):
            t = strip_html(m.group(1))
            if not t or ".pdf" in t.lower() or t.startswith("http"):
                continue
            if len(t) > 15 and not any(s in t.lower() for s in ("офис", "тел.", "e-mail")):
                extra_text.append(t)

        short_desc = short_parts[0] if short_parts else (meta or (extra_text[0][:200] if extra_text else name))
        description_parts = short_parts + [t for t in extra_text if t not in short_parts]
        if meta and meta not in description_parts:
            description_parts.insert(0, meta)
        description = "\n\n".join(description_parts) if description_parts else short_desc

    short_desc = clean_description(short_desc)[:500]
    description = clean_description(description)[:8000]

    specs = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S | re.I)
        if len(cells) < 2:
            continue
        key = strip_html(cells[0])
        val = strip_html(cells[1])
        if not key or not val:
            continue
        if key.lower() in SKIP_SPEC or val.lower() in SKIP_SPEC:
            continue
        if key.lower() == "характеристики":
            continue
        specs.append({"name": key, "value": val})

    pdf_m = re.search(r'href="(gallery/[^"]+\.pdf)"', html, re.I)
    pdf_path = pdf_m.group(1) if pdf_m else ""

    return {
        "name": name,
        "short_desc": short_desc,
        "description": description,
        "specs": specs[:20],
        "pdf_path": pdf_path,
        "analog": extract_analog(html),
    }


def resolve_tds_file(slug: str, pdf_path: str, docs_dir: Path) -> str:
    candidates = [
        docs_dir / f"akzo-{slug}.pdf",
        docs_dir / f"tds-{slug}.pdf",
    ]
    for c in candidates:
        if c.exists():
            return c.name
    if pdf_path:
        return f"akzo-{slug}.pdf"
    return f"akzo-{slug}.pdf"


def download_pdf(pdf_path: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    parts = pdf_path.split("/")
    encoded = "/".join(urllib.parse.quote(p, safe="") for p in parts)
    url = f"{SITE}/{encoded}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        if len(data) < 500:
            return False
        dest.write_bytes(data)
        return True
    except Exception as exc:
        print(f"   ⚠ PDF {pdf_path}: {exc}")
        return False


REM_FALLBACK_SLUGS = (
    "rem-cryl-0606", "rem-cryl-1602", "rem-pox-0607-hs", "rem-pox-0607",
    "rem-pox-0607-as", "rem-lux-1607", "rem-lux-0605", "rem-pox-7605",
    "rem-vinyl-hv-0278", "rem-zink-7606", "rem-pur-210", "rem-pur-1604",
)


def load_rem_catalog() -> dict[str, dict]:
    try:
        import sqlite3

        db_path = BASE / "tonal.db"
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT slug, name FROM products WHERE brand = 'rem-color'"
            ).fetchall()
            conn.close()
            if rows:
                return {slug: {"name": name} for slug, name in rows}
    except Exception:
        pass
    return {slug: {"name": slug} for slug in REM_FALLBACK_SLUGS}


def build_records(paths: list[str], download_pdf_flag: bool) -> list[dict]:
    docs_dir = DOCS_DIR
    docs_dir.mkdir(parents=True, exist_ok=True)
    records = []
    seen_slugs = set()
    rem_catalog = load_rem_catalog()

    for i, path in enumerate(paths, 1):
        encoded_path = "/".join(urllib.parse.quote(p, safe="") for p in path.split("/"))
        url = f"{SITE}/{encoded_path}/"
        print(f"[{i}/{len(paths)}] {url}")
        try:
            html = fetch(url)
        except Exception as exc:
            print(f"   ❌ {exc}")
            continue

        parsed = parse_product_page(html)
        name = parsed["name"] or path.replace("-", " ").replace("_", " ")
        slug = slug_for(path, name)
        if slug in seen_slugs:
            slug = slug_from_path(path) + "-dup"
        seen_slugs.add(slug)

        family = family_from_name(name)
        ptype, binder, purpose = FAMILY_HINTS.get(family, ("материал", "", ""))
        tds_file = resolve_tds_file(slug, parsed["pdf_path"], docs_dir)

        if download_pdf_flag and parsed["pdf_path"]:
            dest = docs_dir / tds_file
            ok = download_pdf(parsed["pdf_path"], dest)
            if ok:
                print(f"   📄 {tds_file}")

        analog = parsed.get("analog")
        if analog:
            rem_slug = resolve_rem_slug(analog.get("url", ""), analog.get("name", ""), rem_catalog)
            if rem_slug:
                analog["rem_slug"] = rem_slug
                print(f"   🔗 аналог → {rem_slug}")

        records.append({
            "slug": slug,
            "name": name.upper() if family else name,
            "brand": "akzo",
            "family": family,
            "badge": "2K Система",
            "ptype": ptype,
            "binder": binder,
            "purpose": purpose,
            "short_desc": parsed["short_desc"],
            "description": parsed["description"],
            "specs": parsed["specs"],
            "related": [],
            "analog": analog or None,
            "tds_file": tds_file,
            "source_id": f"tonaly:{path}",
        })
        time.sleep(0.8)

    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--import", dest="do_import", action="store_true")
    parser.add_argument("--download-pdf", action="store_true")
    args = parser.parse_args()

    print("Загрузка списка с tonaly.ru …")
    home = fetch(SITE + "/")
    paths = catalog_paths(home)
    print(f"Найдено {len(paths)} позиций в каталоге")

    records = build_records(paths, download_pdf_flag=args.download_pdf)

    out = DATA_DIR / "products_import_akzo_full.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    by_family = {}
    for r in records:
        by_family.setdefault(r["family"], 0)
        by_family[r["family"]] += 1

    print(f"\n✅ Собрано {len(records)} позиций → {out}")
    for fam, cnt in sorted(by_family.items()):
        print(f"   {fam or '?'}: {cnt}")

    if args.do_import:
        from import_products import import_file
        import_file(out)


if __name__ == "__main__":
    main()
