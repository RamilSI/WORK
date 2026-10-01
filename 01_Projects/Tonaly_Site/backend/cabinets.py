"""Client cabinets: JSON records + password hashes in cabinets_secrets.json."""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
CABINETS_PATH = DATA_DIR / "cabinets.json"
SECRETS_PATH = DATA_DIR / "cabinets_secrets.json"
MEDIA_DIR = Path(__file__).resolve().parent.parent / "frontend" / "img" / "media" / "clients"


def load_cabinets() -> list[dict]:
    if not CABINETS_PATH.exists():
        return []
    try:
        data = json.loads(CABINETS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _secrets() -> dict:
    if not SECRETS_PATH.exists():
        return {}
    try:
        data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def cabinet_by_login(login: str) -> dict | None:
    key = (login or "").strip().lower()
    for item in load_cabinets():
        if (item.get("login") or item.get("slug") or "").lower() == key:
            return item
    return None


def cabinet_by_slug(slug: str) -> dict | None:
    for item in load_cabinets():
        if item.get("slug") == slug:
            return item
    return None


def verify_password(login: str, password: str) -> dict | None:
    cabinet = cabinet_by_login(login)
    if not cabinet or not password:
        return None
    users = _secrets().get("users") or {}
    rec = users.get(cabinet["slug"])
    if not rec:
        return None
    salt = rec.get("salt") or ""
    expected = rec.get("hash") or ""
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120000).hex()
    if not hmac.compare_digest(digest, expected):
        return None
    return cabinet


def sign_session(slug: str) -> str:
    secret = (_secrets().get("session_secret") or "").encode()
    sig = hmac.new(secret, slug.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{slug}.{sig}"


def read_session(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    slug, sig = token.split(".", 1)
    expected = sign_session(slug)
    if not hmac.compare_digest(expected, f"{slug}.{sig}"):
        return None
    return cabinet_by_slug(slug)


def media_for(slug: str) -> list[dict]:
    folder = MEDIA_DIR / slug
    if not folder.exists():
        return []
    items = []
    allowed_img = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    allowed_vid = {".mp4", ".webm", ".mov"}
    for path in sorted(folder.iterdir()):
        if path.name.startswith(".") or path.name == ".gitkeep":
            continue
        suffix = path.suffix.lower()
        if suffix in allowed_vid:
            kind = "video"
        elif suffix in allowed_img:
            kind = "image"
        else:
            continue
        items.append({"kind": kind, "src": f"/img/media/clients/{slug}/{path.name}", "name": path.name})
    return items
