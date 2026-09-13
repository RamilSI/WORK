"""TONAL — FastAPI + Jinja2 + SQLite"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import json
from database import SessionLocal
from models import Product
from settings import SETTINGS
from rem_analog import parse_analog_json, resolve_rem_slug

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = BASE_DIR / "backend" / "templates"

app = FastAPI(title="TONAL", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

def render_template(name, context=None):
    ctx = {
        "site_url": SETTINGS["SITE_URL"],
        "metrika_id": SETTINGS["YANDEX_METRIKA_ID"],
    }
    if context:
        ctx.update(context)
    t = jinja_env.get_template(name)
    return HTMLResponse(content=t.render(**ctx))

for name, path in [("css","css"),("img","img"),("docs","docs"),("images","images"),("offers","offers"),("documents","documents"),("reports","reports")]:
    p = FRONTEND_DIR / path
    if p.exists():
        app.mount("/"+name, StaticFiles(directory=str(p)), name=name)

REM_FAMILY_META = [
    ("POX", "Эпоксидные грунтовки и грунт-эмали"),
    ("LUX", "Алкидные одно- и двухкомпонентные системы"),
    ("PUR", "Полиуретановые эмали и грунт-эмали"),
    ("ZINK", "Цинконаполненные составы катодной защиты"),
    ("CRYL", "Акриловые и полиуретановые покрытия"),
    ("VINYL", "Виниловые составы для агрессивных сред"),
]

AKZO_FAMILY_META = [
    ("INTERGARD", "Эпоксидные грунты и грунт-эмали"),
    ("INTERZONE", "Высоконаполненные эпоксидные системы"),
    ("INTERTHANE", "Полиуретановые финишные покрытия"),
    ("INTERZINC", "Цинконаполненные грунты"),
    ("INTERLINE", "Химстойкие внутренние покрытия"),
    ("INTERTHERM", "Термостойкие покрытия"),
    ("CHARTEK", "Огнезащита"),
    ("ENVIROLINE", "Покрытия для резервуаров"),
    ("INTERSEAL", "Эпоксидные грунт-эмали"),
    ("INTERCURE", "Быстросохнущие эпоксидные грунты"),
    ("INTERPLATE", "Эпоксидные грунт-эмали"),
    ("INTERPRIME", "Эпоксидные грунты"),
    ("INTERSHIELD", "Эпоксидные грунт-эмали"),
    ("INTERCHAR", "Огнезащитные вспучивающиеся покрытия"),
    ("CEILCOTE", "Химстойкие покрытия Ceilcote"),
    ("INTERBOND", "Эпоксидные связующие системы"),
    ("INTERFINE", "Полиуретановые финишные эмали"),
    ("INTERLAC", "Алкидные и акриловые покрытия"),
    ("INTERPLUS", "Эпоксидные грунты"),
    ("INTERSHEEN", "Алкидные финишные покрытия"),
    ("POLIBRID", "Полиуретановые химстойкие покрытия"),
    ("INTERCRETE", "Ремонт и защита бетона"),
    ("INTERTUF", "Полиуретановые покрытия"),
]


def group_by_family(products, family_meta):
    buckets = {}
    for product in products:
        family = (product.get("family") or "").upper()
        buckets.setdefault(family, []).append(product)
    groups = []
    seen = set()
    for title, description in family_meta:
        items = buckets.get(title, [])
        if items:
            groups.append({
                "key": title.lower().replace(" ", "-"),
                "title": title,
                "description": description,
                "products": sorted(items, key=lambda p: p["slug"]),
            })
            seen.add(title)
    for family, items in sorted(buckets.items()):
        if family and family not in seen:
            groups.append({
                "key": family.lower().replace(" ", "-"),
                "title": family,
                "description": "",
                "products": sorted(items, key=lambda p: p["slug"]),
            })
    return groups


def rem_product_index(products: list[dict]) -> dict[str, dict]:
    return {
        p["slug"]: {"name": p["name"]}
        for p in products
        if p.get("brand") == "rem-color"
    }


def build_analog_view(analog_raw: str, rem_index: dict[str, dict]) -> dict | None:
    data = parse_analog_json(analog_raw)
    if not data:
        return None
    notice = (data.get("notice") or "").strip()
    name = (data.get("name") or "").strip()
    note = (data.get("note") or "").strip()
    if not notice and not name:
        return None

    rem_slug = (data.get("rem_slug") or "").strip()
    if not rem_slug or rem_slug not in rem_index:
        rem_slug = resolve_rem_slug(data.get("url", ""), name, rem_index) or ""

    if not rem_slug:
        return None

    rem_name = rem_index[rem_slug]["name"]
    link_label = name or rem_name
    return {
        "notice": notice,
        "note": note,
        "rem_slug": rem_slug,
        "link_label": link_label,
        "rem_name": rem_name,
    }


def serialize_product(p, rem_index: dict[str, dict] | None = None):
    purpose = (p.purpose or "").strip()
    binder = (p.binder or "").strip()
    badge = (p.badge or "").strip()
    ptype = (p.ptype or "").strip()
    brand = (p.brand or "rem-color").strip()
    family = (p.family or "").strip().upper()
    tds_file = (p.tds_file or f"tds-{p.slug}.pdf").strip()
    desc_raw = (p.description or "").strip()
    paragraphs = [part.strip() for part in desc_raw.split("\n\n") if part.strip()]
    short = (p.short_desc or "").strip()
    if not short and paragraphs:
        short = paragraphs[0]
    body_paragraphs = []
    if paragraphs:
        if short and paragraphs[0] == short:
            body_paragraphs = paragraphs[1:]
        else:
            body_paragraphs = [p for p in paragraphs if p != short]
    benefits = [item for item in (badge, binder.capitalize() if binder else "", purpose.capitalize() if purpose else "") if item]
    analog = build_analog_view(getattr(p, "analog_json", "") or "", rem_index or {})
    return {
        "slug": p.slug,
        "name": p.name,
        "brand": brand,
        "family": family,
        "badge": badge,
        "type": ptype,
        "binder": binder.capitalize() if binder else "",
        "purpose": purpose,
        "short_desc": short,
        "description": desc_raw,
        "body_paragraphs": body_paragraphs,
        "application_tag": purpose.capitalize() if purpose else "",
        "application": p.description,
        "benefits": benefits,
        "specs": json.loads(p.specs) if p.specs else [],
        "related": json.loads(p.related) if p.related else [],
        "tds_file": tds_file,
        "has_image": brand == "rem-color",
        "analog": analog,
    }


def get_products():
    db = SessionLocal()
    try:
        rows = db.query(Product).all()
        rem_index = {
            p.slug: {"name": p.name}
            for p in rows
            if (p.brand or "rem-color") == "rem-color"
        }
        return [serialize_product(p, rem_index) for p in rows]
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
async def root():
    return render_template("index.html")

@app.get("/about", response_class=HTMLResponse)
async def about():
    return render_template("about.html")

@app.get("/catalog", response_class=HTMLResponse)
async def catalog():
    products = get_products()
    rem_products = [p for p in products if p["brand"] == "rem-color"]
    akzo_products = [p for p in products if p["brand"] == "akzo"]
    return render_template("catalog.html", {
        "products": products,
        "rem_groups": group_by_family(rem_products, REM_FAMILY_META),
        "akzo_groups": group_by_family(akzo_products, AKZO_FAMILY_META),
        "rem_count": len(rem_products),
        "akzo_count": len(akzo_products),
    })

@app.get("/contacts", response_class=HTMLResponse)
async def contacts():
    return render_template("contacts.html")

@app.get("/offwork", response_class=HTMLResponse)
async def offwork():
    return render_template("offwork.html")

@app.get("/offwork/kiteboarding", response_class=HTMLResponse)
async def offwork_kiteboarding():
    return render_template("kiteboarding.html")

@app.get("/product/{slug}", response_class=HTMLResponse)
async def product_page(slug: str):
    products = get_products()
    by_slug = {p["slug"]: p for p in products}
    p = by_slug.get(slug)
    if not p:
        return HTMLResponse("Товар не найден", status_code=404)
    related = [{"slug": s, "name": by_slug[s]["name"], "has_image": by_slug[s]["has_image"]} for s in p.get("related", []) if s in by_slug]
    pd = dict(p)
    pd["related"] = related
    return render_template("product.html", {"product": pd})

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/robots.txt", response_class=Response)
async def robots():
    site = SETTINGS["SITE_URL"].rstrip("/")
    body = f"""User-agent: *
Allow: /

Sitemap: {site}/sitemap.xml
"""
    return Response(content=body, media_type="text/plain")

@app.get("/sitemap.xml", response_class=Response)
async def sitemap():
    site = SETTINGS["SITE_URL"].rstrip("/")
    products = get_products()
    urls = [
        ("", "daily", "1.0"),
        ("/about", "monthly", "0.8"),
        ("/catalog", "weekly", "0.9"),
        ("/contacts", "monthly", "0.7"),
        ("/offwork", "monthly", "0.5"),
        ("/offwork/kiteboarding", "monthly", "0.5"),
    ]
    for product in products:
        urls.append((f"/product/{product['slug']}", "monthly", "0.8"))

    items = []
    for path, freq, priority in urls:
        loc = f"{site}{path}"
        items.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(items)
        + "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
