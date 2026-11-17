"""Черновик 301 со старых адресов tonaly.ru на страницы rml-s.ru.

Читает карту сайта из архива этапа 1 и каталог нового сайта.
Пишет deploy/tonaly-url-map.tsv и deploy/tonaly-301.conf.
DNS не меняет и nginx на сервере не подключает.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = Path("/Users/ramil/Documents/WORK/archives/tonaly.ru-2026-10")
SITEMAP = ARCHIVE / "urls-sitemap.txt"
MIRROR = ARCHIVE / "tonaly.ru"
AKZO_JSON = ROOT / "backend" / "data" / "products_import_akzo_full.json"
SCHEMES_JSON = ROOT / "backend" / "data" / "coating_schemes.json"
OUT_DIR = ROOT / "deploy"

# Страницы-разделы конструктора. Ключ — путь без языка, в нижнем регистре.
SECTIONS = {
    "": "/",
    "контакты": "/contacts",
    "contacts": "/contacts",
    "отзывы": "/about",
    "услуги": "/services",
    "услуги-1": "/services",
    "сервис-и-услуги": "/services",
    "контроль-качества": "/services",
    "tests": "/services",
    "справочник": "/about",
    "регламентирующие-документы": "/about",
    "опыт-применения": "/about",
    "блог": "/about",
    "catalog": "/catalog?brand=akzo",
    "продукты": "/catalog",
    "грунтовки": "/catalog?brand=akzo",
    "грунт/эмали": "/catalog?brand=akzo",
    "промежуточные-грунты": "/catalog?brand=akzo",
    "финишные-покрытия": "/catalog?brand=akzo",
    "схемы-покрытий": "/schemes",
    "домонтажная-окраска": "/schemes",
    "грунт-эмали-3-в-1": "/schemes",
    "наружные-покрытия": "/schemes",
    "покрытия-под-теплоизоляцией": "/schemes",
    "термостойкие-покрытия": "/schemes",
    "термостойкие-покрытие": "/schemes",
    "внутренние-покрытия": "/schemes",
    "износоустойчивые-подводные-и-зоны-переменного-смачивания": "/schemes",
    "покрытия-для-внутренних-поверхностей-резервуаров": "/schemes",
    "огнезащита": "/catalog?brand=akzo",
    "огнезащита-1": "/catalog?brand=akzo",
    "целлюлозное-горение": "/catalog?brand=akzo",
    "углеводородное-горение": "/catalog?brand=akzo",
    "покрытия-по-бетону": "/catalog?brand=akzo",
    "восстановление-бетона": "/catalog?brand=akzo",
    "нефтегаз": "/catalog",
    "нефтегазовая-отрасль": "/catalog",
    "вода-и-канализация": "/catalog",
    "теплоэнергетика": "/catalog",
    "готовые-решения": "/schemes",
    "погружение-в-особо-агрессивные-среды-износоустойчивые-схемы": "/schemes",
    "термостойкие-покрытия-1": "/schemes",
    "промежуточные-покрытия": "/catalog?brand=akzo",
    "продукция": "/catalog",
    "каталог": "/catalog?brand=akzo",
    "заявка-на-тесты": "/contacts",
    "bar-rust": "/catalog",
}

# Буквы, которыми конструктор иногда подменяет латиницу в артикулах.
HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "к": "k", "м": "m", "т": "t", "в": "b", "н": "h",
})

FAMILIES = {
    "ceilcote",
    "chartek",
    "enviroline",
    "interbond",
    "interchar",
    "intercrete",
    "intercure",
    "interfine",
    "intergard",
    "interlac",
    "interline",
    "interplate",
    "interplus",
    "interprime",
    "interseal",
    "intersheen",
    "intershield",
    "intertuf",
    "interthane",
    "intertherm",
    "interzinc",
    "interzone",
    "polibrid",
}


def compact(value: str) -> str:
    return re.sub(r"[^0-9a-zа-яё]+", "", value.casefold())


def norm_slug(segment: str) -> str:
    text = unquote(segment).casefold().replace("_", "-").replace(" ", "-")
    text = text.replace("ё", "е")
    if re.search(r"[a-z]", text):
        text = text.translate(HOMOGLYPHS)
    text = re.sub(r"[^0-9a-zа-яё./-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text


def language_stripped(path: str) -> str:
    parts = [unquote(part) for part in path.split("/") if part]
    if parts and parts[0] in {"en", "zh3"}:
        parts = parts[1:]
    return "/".join(parts)


def load_products() -> dict[str, str]:
    products = json.loads(AKZO_JSON.read_text(encoding="utf-8"))
    slugs = {item["slug"]: f"/product/{item['slug']}" for item in products}
    # Rem Color есть в init_db.py, не в JSON Akzo.
    rem = [
        "rem-cryl-0606",
        "rem-cryl-1602",
        "rem-pox-0607-hs",
        "rem-pox-0607",
        "rem-pox-0607-as",
        "rem-lux-1607",
        "rem-lux-0605",
        "rem-pox-7605",
        "rem-vinyl-hv-0278",
        "rem-zink-7606",
        "rem-pur-210",
        "rem-pur-1604",
    ]
    for slug in rem:
        slugs[slug] = f"/product/{slug}"
    return slugs


def load_schemes() -> dict[str, str]:
    schemes = json.loads(SCHEMES_JSON.read_text(encoding="utf-8"))
    by_compact: dict[str, str] = {}
    for scheme in schemes:
        target = f"/schemes/{scheme['slug']}"
        for code in (scheme.get("code"), (scheme.get("competitor") or {}).get("code")):
            if code:
                by_compact[compact(code)] = target
    return by_compact


def collect_paths() -> list[str]:
    found: set[str] = set()
    if SITEMAP.exists():
        for line in SITEMAP.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or "sitemap.xml" in line:
                continue
            path = unquote(urlsplit(line).path) or "/"
            found.add(path if path.startswith("/") else "/" + path)
    if MIRROR.exists():
        for page in MIRROR.rglob("*.html"):
            rel = page.relative_to(MIRROR).as_posix()
            if rel in {"index.html", "index.html?.html"} or rel.startswith("index.html?"):
                found.add("/")
                continue
            if rel.endswith("/index.html"):
                found.add("/" + rel[: -len("index.html")])
            elif rel.endswith(".html") and "/en/" not in f"/{rel}" and not rel.startswith("en/"):
                # Сохранённые без каталога: Блог/Статья.html
                stem = rel[: -len(".html")]
                if "?" not in stem:
                    found.add("/" + stem + "/")
    extra = ARCHIVE / "extra-pages" / "README.txt"
    if extra.exists():
        for line in extra.read_text(encoding="utf-8").splitlines():
            if line.startswith("https://tonaly.ru/"):
                found.add(unquote(urlsplit(line).path) or "/")
    return sorted(found)


def classify(path: str, products: dict[str, str], schemes: dict[str, str]) -> tuple[str, str]:
    """Возвращает (новый путь, причина)."""
    rest = language_stripped(path)
    key = rest.casefold().replace("_", "-")
    if key in SECTIONS:
        return SECTIONS[key], "раздел"

    parts = [part for part in rest.split("/") if part]
    if len(parts) > 1 and parts[0].casefold() in {"блог", "услуги"}:
        return "/about", "блог"

    if len(parts) == 1:
        scheme_target = schemes.get(compact(parts[0]))
        if scheme_target:
            return scheme_target, "схема"
        slug = norm_slug(parts[0])
        product_target = match_product(slug, products)
        if product_target:
            return product_target, "товар"
        if slug in FAMILIES:
            return "/catalog?brand=akzo", "семейство"
        if re.search(r"[a-z]", slug):
            return "/catalog?brand=akzo", "нет карточки"
    return "/catalog", "нет страницы"


ALIASES = {
    "ceilcote-242": "ceilcote-242flakeline",
}


def match_product(slug: str, products: dict[str, str]) -> str:
    candidates = [slug, ALIASES.get(slug, ""), slug.replace("interzon-", "interzone-")]
    candidates = [item for item in candidates if item]
    if slug.startswith("nter"):
        candidates.append("i" + slug)
    by_compact = {compact(name): target for name, target in products.items()}
    for candidate in candidates:
        if candidate in products:
            return products[candidate]
        packed = by_compact.get(compact(candidate))
        if packed:
            return packed
    trimmed = re.sub(r"-\d+$", "", slug)
    if trimmed in products:
        return products[trimmed]
    code = re.fullmatch(r"\d+-(\d+)-\d+", slug)
    if code:
        token = code.group(1)
        hits = [name for name in products if name.endswith("-" + token)]
        if len(hits) == 1:
            return products[hits[0]]
    return ""


def nginx_quote(value: str) -> str:
    if re.search(r"[\s{};#]", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def main() -> None:
    products = load_products()
    schemes = load_schemes()
    paths = collect_paths()
    rows = []
    for path in paths:
        if path.rstrip("/") in {"", "/sitemap.xml"} or path.startswith("/js/") or path.startswith("/css/"):
            continue
        if path in {"/", "/en/", "/zh3/", "/en", "/zh3"}:
            target, reason = ("/", "главная") if path != "/" else ("", "главная уже новая")
            if path == "/":
                continue
        else:
            target, reason = classify(path, products, schemes)
        if not target or target == path.rstrip("/"):
            continue
        rows.append((path if path.endswith("/") or path == "/" else path + "/", target, reason))

    # Оба варианта слэша, nginx $uri бывает и так, и так.
    expanded = []
    seen = set()
    for path, target, reason in rows:
        variants = {path}
        if path != "/":
            variants.add(path.rstrip("/"))
        for variant in variants:
            if variant in seen or variant in {"", "/"}:
                continue
            if len(variant.encode()) > 180:
                continue
            seen.add(variant)
            expanded.append((variant, target, reason))
    expanded.sort()

    OUT_DIR.mkdir(exist_ok=True)
    tsv = OUT_DIR / "tonaly-url-map.tsv"
    conf = OUT_DIR / "tonaly-301.conf"
    lines = ["old\tnew\treason"]
    lines.extend(f"{old}\t{new}\t{reason}" for old, new, reason in expanded)
    tsv.write_text("\n".join(lines) + "\n", encoding="utf-8")

    conf_lines = [
        "# Черновик 301 для tonaly.ru → страницы нового сайта.",
        "# Не подключён к nginx. DNS не переключает.",
        "# Подключать внутри server { } только когда tonaly.ru уже смотрит на этот сервер:",
        "#   include /path/tonaly-301.conf;",
        "map $uri $tonaly_legacy_target {",
        "    default \"\";",
    ]
    for old, new, _reason in expanded:
        conf_lines.append(f"    {nginx_quote(old)} {nginx_quote(new)};")
    conf_lines.append("}")
    conf_lines.append("")
    conf.write_text("\n".join(conf_lines) + "\n", encoding="utf-8")

    from collections import Counter

    reasons = Counter(reason for _old, _new, reason in expanded)
    print(f"paths {len(expanded)}")
    for reason, count in reasons.most_common():
        print(f"  {count:4} {reason}")
    print(f"wrote {tsv}")
    print(f"wrote {conf}")


if __name__ == "__main__":
    main()
