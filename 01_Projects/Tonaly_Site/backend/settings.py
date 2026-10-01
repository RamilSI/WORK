from pathlib import Path

SITE_ENV_PATH = Path(__file__).resolve().parent / "site.env"

DEFAULTS = {
    "SITE_URL": "https://rml-s.ru",
    "YANDEX_METRIKA_ID": "",
}


def load_settings():
    settings = dict(DEFAULTS)
    if not SITE_ENV_PATH.exists():
        return settings
    for line in SITE_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        settings[key.strip()] = value.strip()
    return settings

SETTINGS = load_settings()
