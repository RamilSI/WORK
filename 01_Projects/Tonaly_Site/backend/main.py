"""TONAL — FastAPI + Jinja2 + SQLite"""
from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import json
from database import SessionLocal
from models import Product
from settings import SETTINGS
from rem_analog import parse_analog_json, resolve_rem_slug
from schemes import get_scheme, group_schemes, load_schemes, schemes_for_product
from object_match import match as match_object
from equipment import get_equipment, group_equipment, load_equipment
from eleveight import get_eleveight, group_eleveight, load_eleveight, related_eleveight
from kite_requests import PHONE_DISPLAY, notify_email, save_request, topic_label
from cabinets import media_for, read_session, sign_session, verify_password

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = BASE_DIR / "backend" / "templates"

app = FastAPI(title="TONAL", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

NO_STORE = {"Cache-Control": "no-store, max-age=0"}


def render_template(name, context=None, status_code=200):
    ctx = {
        "site_url": SETTINGS["SITE_URL"],
        "metrika_id": SETTINGS["YANDEX_METRIKA_ID"],
    }
    if context:
        ctx.update(context)
    t = jinja_env.get_template(name)
    return HTMLResponse(content=t.render(**ctx), status_code=status_code, headers=NO_STORE)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        path = (request.url.path or "").lower().rstrip("/")
        if path not in {"/application", "/applications"} and any(
            token in path for token in ("applicat", "area", "примен", "област")
        ):
            return RedirectResponse("/applications", status_code=302, headers=NO_STORE)
        if "text/html" in (request.headers.get("accept") or ""):
            return render_template("not_found.html", status_code=404)
        return JSONResponse({"detail": "Not Found"}, status_code=404, headers=NO_STORE)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=NO_STORE)

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

TALATU_FAMILY_META = [
    ("THERM", "Термостойкие грунт-эмали TALATU"),
]

BRAND_LABELS = {
    "rem-color": "REM COLOR",
    "talatu": "TALATU",
    "akzo": "Akzo Nobel",
}

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


def rem_short_name(rem_name: str) -> str:
    if "«" in (rem_name or "") and "»" in rem_name:
        return rem_name[rem_name.find("«") + 1 : rem_name.find("»")].strip() or rem_name
    return rem_name


def analog_from_slug(
    rem_slug: str,
    rem_index: dict[str, dict],
    name: str = "",
    notice: str = "",
    note: str = "",
) -> dict | None:
    if not rem_slug or rem_slug not in rem_index:
        return None
    rem_name = rem_index[rem_slug]["name"]
    rem_short = rem_short_name(rem_name)
    brand = rem_index[rem_slug].get("brand") or "rem-color"
    return {
        "notice": notice,
        "note": note,
        "rem_slug": rem_slug,
        "link_label": name or rem_short,
        "rem_name": rem_name,
        "rem_short": rem_short,
        "brand": brand,
        "brand_label": BRAND_LABELS.get(brand, brand.upper()),
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

    view = analog_from_slug(rem_slug, rem_index, name=name, notice=notice, note=note)
    if not view:
        return None

    also = []
    for extra in data.get("also") or []:
        if isinstance(extra, str):
            extra_slug, extra_name = extra.strip(), ""
        elif isinstance(extra, dict):
            extra_slug = (extra.get("rem_slug") or "").strip()
            extra_name = (extra.get("name") or "").strip()
        else:
            continue
        item = analog_from_slug(extra_slug, rem_index, name=extra_name)
        if item and item["rem_slug"] != view["rem_slug"]:
            also.append(item)
    view["also"] = also
    return view


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
        "has_image": brand in ("rem-color", "talatu"),
        "analog": analog,
    }


def get_products():
    db = SessionLocal()
    try:
        rows = db.query(Product).all()
        rem_index = {
            p.slug: {"name": p.name, "brand": (p.brand or "rem-color")}
            for p in rows
        }
        return [serialize_product(p, rem_index) for p in rows]
    finally:
        db.close()


def get_all_items():
    return get_products() + load_equipment()


@app.get("/", response_class=HTMLResponse)
async def root():
    return render_template("index.html")

@app.get("/about", response_class=HTMLResponse)
async def about():
    return render_template("about.html")

@app.get("/catalog", response_class=HTMLResponse)
async def catalog(brand: str | None = None):
    if brand == "schemes":
        return RedirectResponse("/schemes", status_code=302)
    products = get_products()
    rem_products = [p for p in products if p["brand"] == "rem-color"]
    akzo_products = [p for p in products if p["brand"] == "akzo"]
    talatu_products = [p for p in products if p["brand"] == "talatu"]
    equipment = load_equipment()
    return render_template("catalog.html", {
        "products": products,
        "rem_groups": group_by_family(rem_products, REM_FAMILY_META),
        "akzo_groups": group_by_family(akzo_products, AKZO_FAMILY_META),
        "talatu_groups": group_by_family(talatu_products, TALATU_FAMILY_META),
        "equipment_groups": group_equipment(equipment),
        "rem_count": len(rem_products),
        "akzo_count": len(akzo_products),
        "talatu_count": len(talatu_products),
        "equipment_count": len(equipment),
    })

@app.get("/contacts", response_class=HTMLResponse)
async def contacts():
    return render_template("contacts.html")

@app.get("/services", response_class=HTMLResponse)
async def services():
    return render_template("services.html")

@app.get("/application", response_class=HTMLResponse)
@app.get("/application/", response_class=HTMLResponse)
@app.get("/applications", response_class=HTMLResponse)
@app.get("/applications/", response_class=HTMLResponse)
async def applications():
    return render_template("applications.html")


@app.get("/areas")
@app.get("/areas/")
async def application_areas():
    return RedirectResponse("/applications#areas", status_code=302, headers=NO_STORE)

@app.get("/offwork", response_class=HTMLResponse)
async def offwork():
    return render_template("offwork.html")

def _kite_form_context(
    order: str = "",
    sent: bool = False,
    error: str = "",
    values: dict | None = None,
) -> dict:
    product = get_eleveight(order) if order else None
    values = dict(values or {})
    if product and not values.get("topic"):
        values["topic"] = "order"
    if product and not values.get("message"):
        values["message"] = f"Заявка на {product['name']}. Нужен размер и цена."
    return {
        "order_product": product,
        "sent": sent,
        "form_error": error,
        "form": values,
        "phone_display": PHONE_DISPLAY,
        "topics": (("lesson", "Обучение кайту"), ("order", "Заказ снаряжения")),
    }


@app.get("/offwork/kiteboarding", response_class=HTMLResponse)
async def kiteboarding(order: str = "", sent: str = ""):
    return render_template("kiteboarding.html", _kite_form_context(order=order, sent=sent == "1"))


@app.post("/offwork/kiteboarding", response_class=HTMLResponse)
async def kiteboarding_post(
    name: str = Form(""),
    contact: str = Form(""),
    topic: str = Form("lesson"),
    size: str = Form(""),
    message: str = Form(""),
    product: str = Form(""),
    company: str = Form(""),
):
    name = (name or "").strip()[:80]
    contact = (contact or "").strip()[:120]
    size = (size or "").strip()[:40]
    message = (message or "").strip()[:2000]
    topic = topic if topic in ("lesson", "order") else "lesson"
    order_product = get_eleveight(product) if product else None
    values = {
        "name": name,
        "contact": contact,
        "topic": topic,
        "size": size,
        "message": message,
    }
    if company.strip():
        return RedirectResponse("/offwork/kiteboarding?sent=1#signup", status_code=303)
    if not name or not contact:
        return render_template(
            "kiteboarding.html",
            _kite_form_context(
                order=product,
                error="Нужны имя и контакт — телефон, Telegram или почта.",
                values=values,
            ),
        )
    payload = {
        "topic": topic,
        "topic_label": topic_label(topic),
        "name": name,
        "contact": contact,
        "size": size,
        "message": message,
        "product": order_product["slug"] if order_product else "",
        "product_name": order_product["name"] if order_product else "",
    }
    save_request(payload)
    notify_email(payload, SETTINGS.get("KITE_NOTIFY_EMAIL", "info@tonaly.ru"))
    return RedirectResponse("/offwork/kiteboarding?sent=1#signup", status_code=303)

@app.get("/offwork/eleveight", response_class=HTMLResponse)
async def eleveight_catalog():
    return render_template("eleveight.html", {"groups": group_eleveight()})

@app.get("/offwork/eleveight/{slug}", response_class=HTMLResponse)
async def eleveight_product(slug: str):
    product = get_eleveight(slug)
    if not product:
        return HTMLResponse("Модель не найдена", status_code=404)
    return render_template("eleveight_product.html", {
        "product": product,
        "related": related_eleveight(slug),
    })

@app.get("/guide", response_class=HTMLResponse)
async def guide_page():
    return render_template("guide.html")


OBJECT_PLACES = [
    ("shop", "Хранение и домонтажная окраска"),
    ("indoor", "Внутри цеха, в эксплуатации"),
    ("city", "Улица, город, обычный завод"),
    ("site", "Промплощадка или берег"),
    ("harsh", "Сильная агрессия, высокая соль"),
    ("insulation", "Под теплоизоляцией"),
    ("heat", "Горячая поверхность или труба"),
    ("water", "Погружение или переменное смачивание"),
    ("tank", "Внутри резервуара или ёмкости"),
]
OBJECT_SUBSTRATES = [
    ("steel", "Сталь, струйная очистка реальна"),
    ("hand", "Ремонт, только ручной инструмент"),
    ("zinc", "Оцинкованная сталь"),
]
OBJECT_LIVES = [
    ("", "Пока не задан"),
    ("to7", "До 7 лет"),
    ("m15", "7–15 лет"),
    ("h25", "15–25 лет"),
    ("vh", "Больше 25 лет"),
]


def _object_context(place: str, substrate: str, life: str) -> dict:
    return {
        "places": OBJECT_PLACES,
        "substrates": OBJECT_SUBSTRATES,
        "lives": OBJECT_LIVES,
        "place": place,
        "substrate": substrate,
        "life": life,
        "result": match_object(place, substrate, life),
    }


@app.get("/object", response_class=HTMLResponse)
async def object_page(place: str = "", substrate: str = "", life: str = ""):
    return render_template("object.html", _object_context(place, substrate, life))


@app.get("/object/match", response_class=HTMLResponse)
async def object_match_partial(place: str = "", substrate: str = "", life: str = ""):
    ctx = _object_context(place, substrate, life)
    template = jinja_env.get_template("object_results.html")
    return HTMLResponse(template.render(**ctx))


@app.get("/compare/rem-pox-0607-hs-izolep", response_class=HTMLResponse)
async def compare_0607hs_izolep():
    return render_template("compare_0607hs_izolep.html")


@app.get("/brochure/rem-pox-0607-hs-velesgard", response_class=HTMLResponse)
async def brochure_0607hs_velesgard():
    return render_template("brochure_0607hs_velesgard.html")


@app.get("/schemes", response_class=HTMLResponse)
async def schemes_page():
    products = get_products()
    by_slug = {p["slug"]: p for p in products}
    schemes = load_schemes(by_slug)
    return render_template("schemes.html", {
        "groups": group_schemes(schemes),
        "scheme_count": len(schemes),
    })

@app.get("/schemes/{slug}", response_class=HTMLResponse)
async def scheme_page(slug: str):
    products = get_products()
    by_slug = {p["slug"]: p for p in products}
    scheme = get_scheme(slug, by_slug)
    if not scheme:
        return HTMLResponse("Схема не найдена", status_code=404)
    return render_template("scheme.html", {"scheme": scheme})

def _cabinet_from_request(request: Request):
    return read_session(request.cookies.get("cabinet"))


@app.get("/cabinet", response_class=HTMLResponse)
async def cabinet_get(request: Request):
    cabinet = _cabinet_from_request(request)
    if cabinet:
        return render_template("cabinet.html", {"cabinet": cabinet, "media": media_for(cabinet["slug"])})
    return render_template("cabinet_login.html", {"error": ""})


@app.post("/cabinet", response_class=HTMLResponse)
async def cabinet_post(login: str = Form(""), password: str = Form("")):
    cabinet = verify_password(login, password)
    if not cabinet:
        return render_template("cabinet_login.html", {"error": "Неверный логин или пароль"})
    response = RedirectResponse("/cabinet", status_code=303)
    response.set_cookie("cabinet", sign_session(cabinet["slug"]), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return response


@app.get("/cabinet/logout")
async def cabinet_logout():
    response = RedirectResponse("/cabinet", status_code=303)
    response.delete_cookie("cabinet")
    return response


@app.get("/product/{slug}", response_class=HTMLResponse)
async def product_page(slug: str):
    by_slug = {p["slug"]: p for p in get_all_items()}
    p = by_slug.get(slug) or get_equipment(slug)
    if not p:
        return HTMLResponse("Товар не найден", status_code=404)
    related = []
    for s in p.get("related", []):
        item = by_slug.get(s)
        if not item:
            continue
        related.append({
            "slug": s,
            "name": item["name"],
            "has_image": item["has_image"],
            "image": item.get("image") or (f"/img/{s}-can.png" if item["has_image"] else ""),
        })
    paints = {k: v for k, v in by_slug.items() if v.get("kind") != "equipment"}
    pd = dict(p)
    pd["related"] = related
    pd["schemes"] = schemes_for_product(slug, paints) if p.get("kind") != "equipment" else []
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
    urls = [
        ("", "daily", "1.0"),
        ("/about", "monthly", "0.8"),
        ("/catalog", "weekly", "0.9"),
        ("/applications", "monthly", "0.8"),
        ("/guide", "monthly", "0.8"),
        ("/object", "monthly", "0.8"),
        ("/compare/rem-pox-0607-hs-izolep", "monthly", "0.7"),
        ("/brochure/rem-pox-0607-hs-velesgard", "monthly", "0.7"),
        ("/schemes", "weekly", "0.9"),
        ("/services", "monthly", "0.8"),
        ("/contacts", "monthly", "0.7"),
        ("/offwork", "monthly", "0.6"),
        ("/offwork/kiteboarding", "monthly", "0.6"),
        ("/offwork/eleveight", "monthly", "0.6"),
    ]
    for product in get_all_items():
        urls.append((f"/product/{product['slug']}", "monthly", "0.8"))
    for scheme in load_schemes():
        urls.append((f"/schemes/{scheme['slug']}", "monthly", "0.8"))
    for item in load_eleveight():
        urls.append((f"/offwork/eleveight/{item['slug']}", "monthly", "0.5"))

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
