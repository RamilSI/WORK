"""Сопоставление внешних ссылок tonaly/detalystaly с карточками Rem Color в каталоге."""
import re
from urllib.parse import urlparse

# Явные соответствия URL detalystaly.ru → slug на tonal
EXTERNAL_ALIASES = {
    "rem-poks-2k-ep-0607hs": "rem-pox-0607-hs",
    "rem-poks-2k-ep-0607": "rem-pox-0607",
    "rem-poks-2k-ep-0607-as": "rem-pox-0607-as",
    "rem-poks-2k-ep-7605": "rem-pox-7605",
    "rem-lux-1k-0605": "rem-lux-0605",
    "rem-lux-1k-1607": "rem-lux-1607",
    "rem-lyuks-as-1607": "rem-lux-1607",
    "rem-lyuks-1k-1607": "rem-lux-1607",
    "rem-cryl-2k-0606": "rem-cryl-0606",
    "rem-cryl-2k-1602": "rem-cryl-1602",
    "rem-pur-2k-210": "rem-pur-210",
    "rem-pur-2k-ur-1604": "rem-pur-1604",
    "rem-pur-2k": "rem-pur-210",
    "рем-пур-2к": "rem-pur-210",
    "rem-zink-1k-7606": "rem-zink-7606",
    "rem-tsink-2k-ep-0608": "rem-zink-7606",
    "rem-tsink-2k-ep-060": "rem-zink-7606",
    "рем-цинк-2к-эп-060": "rem-zink-7606",
    "rem-lyuks-as-1607": "rem-lux-1607",
    "рем-люкс-ас-1607": "rem-lux-1607",
    "rem-vinyl-hv-0278": "rem-vinyl-hv-0278",
}


def _norm_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _codes(text: str) -> set[str]:
    return set(re.findall(r"0\d{3}[a-z]{0,4}", _norm_key(text)))


def build_rem_slug_index(rem_slugs: set[str]) -> dict[str, str]:
    index: dict[str, str] = {}
    for slug in rem_slugs:
        index[slug] = slug
        index[_norm_key(slug)] = slug
        if slug.startswith("rem-"):
            rest = slug[4:]
            index[_norm_key(rest)] = slug
            parts = slug.split("-")
            if len(parts) >= 3:
                code = "-".join(parts[2:])
                index[_norm_key(code)] = slug
    for ext, local in EXTERNAL_ALIASES.items():
        if local in rem_slugs:
            index[ext] = local
            index[_norm_key(ext)] = local
    return index


def resolve_rem_slug(
    url: str,
    display_name: str,
    rem_products: dict[str, dict],
) -> str | None:
    """Найти slug Rem Color по URL или названию аналога."""
    if not rem_products:
        return None

    rem_slugs = set(rem_products.keys())
    index = build_rem_slug_index(rem_slugs)

    if url:
        path = urlparse(url).path.rstrip("/")
        ext_slug = path.split("/")[-1].lower()
        if ext_slug in index:
            return index[ext_slug]
        norm = _norm_key(ext_slug)
        if norm in index:
            return index[norm]

    if display_name:
        low = display_name.lower()
        if "1604" in low and "rem-pur-1604" in rem_slugs:
            return "rem-pur-1604"
        if ("пур" in low or "pur 2" in low) and "rem-pur-210" in rem_slugs:
            return "rem-pur-210"
        if ("цинк" in low or "zink" in low) and "rem-zink-7606" in rem_slugs:
            return "rem-zink-7606"
        if ("люкс" in low or "lux" in low) and "1607" in low and "rem-lux-1607" in rem_slugs:
            return "rem-lux-1607"
        if ("люкс" in low or "lux" in low) and "0605" in low and "rem-lux-0605" in rem_slugs:
            return "rem-lux-0605"

        codes = _codes(display_name)
        if codes:
            best_slug = None
            best_len = 0
            for slug, product in rem_products.items():
                slug_codes = _codes(slug) | _codes(product.get("name", ""))
                overlap = codes & slug_codes
                if not overlap:
                    continue
                score = max(len(code) for code in overlap)
                if score > best_len:
                    best_len = score
                    best_slug = slug
            if best_slug:
                return best_slug

    return None


def parse_analog_json(raw: str) -> dict | None:
    if not raw or not str(raw).strip():
        return None
    try:
        import json

        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None
