"""TONAL — FastAPI + Jinja2 + SQLite"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import json
from database import SessionLocal
from models import Product

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = BASE_DIR / "backend" / "templates"

app = FastAPI(title="TONAL", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

def render_template(name, context=None):
    t = jinja_env.get_template(name)
    return HTMLResponse(content=t.render(**(context or {})))

for name, path in [("css","css"),("img","img"),("docs","docs"),("images","images"),("offers","offers"),("documents","documents"),("reports","reports")]:
    p = FRONTEND_DIR / path
    if p.exists():
        app.mount("/"+name, StaticFiles(directory=str(p)), name=name)

def get_products():
    db = SessionLocal()
    try:
        products = db.query(Product).all()
        result = []
        for p in products:
            result.append({
                "slug": p.slug, "name": p.name, "badge": p.badge,
                "type": p.ptype, "binder": p.binder, "purpose": p.purpose,
                "short_desc": p.short_desc, "description": p.description,
                "specs": json.loads(p.specs) if p.specs else [],
                "related": json.loads(p.related) if p.related else [],
            })
        return result
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def root():
    return render_template("index.html")

@app.get("/catalog", response_class=HTMLResponse)
async def catalog():
    return render_template("catalog.html", {"products": get_products()})

@app.get("/product/{slug}", response_class=HTMLResponse)
async def product_page(slug: str):
    products = get_products()
    by_slug = {p["slug"]: p for p in products}
    p = by_slug.get(slug)
    if not p:
        return HTMLResponse("Товар не найден", status_code=404)
    related = [{"slug": s, "name": by_slug[s]["name"]} for s in p.get("related", []) if s in by_slug]
    pd = dict(p)
    pd["related"] = related
    return render_template("product.html", {"product": pd})

@app.get("/health")
async def health():
    return {"status": "ok"}
