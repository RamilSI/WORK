#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Собирает автономную копию визуализатора: все изображения вшиты в HTML как data:URI.
Такой файл можно отправить письмом или в мессенджере — он откроется у любого без сервера.
Запуск:  python3 сделать_офлайн.py
"""
import base64
import os
import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_HTML = ROOT / "полуфабрикаты" / "визуализатор_дефекта.html"
OUT_HTML = ROOT / "готовые" / "07_визуализатор_офлайн.html"
MAX_SIDE = "1800"
QUALITY = "78"

html = SRC_HTML.read_text(encoding="utf-8")
tmp = pathlib.Path(tempfile.mkdtemp(prefix="defect_offline_"))
cache = {}


def data_uri(rel_path: str) -> str:
    if rel_path in cache:
        return cache[rel_path]
    src = (SRC_HTML.parent / rel_path).resolve()
    if not src.exists():
        raise SystemExit("Нет файла: %s" % src)
    out = tmp / (str(abs(hash(rel_path))) + ".jpg")
    subprocess.run(
        ["sips", "-Z", MAX_SIDE, "-s", "format", "jpeg", "-s", "formatOptions", QUALITY,
         str(src), "--out", str(out)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    uri = "data:image/jpeg;base64," + base64.b64encode(out.read_bytes()).decode("ascii")
    cache[rel_path] = uri
    print("  вшито: %-58s %6.0f КБ" % (rel_path, len(uri) / 1024))
    return uri


pattern = re.compile(r"(orig|film|enh|relief|edge):'([^']+)'")


def repl(m: "re.Match") -> str:
    rel = m.group(2)
    # пропускаем не-пути: в коде есть карта слоёв вида { enh:'enhImg', edge:'edgeImg' }
    if not (SRC_HTML.parent / rel).is_file():
        return m.group(0)
    return "%s:'%s'" % (m.group(1), data_uri(rel))


print("Собираю автономную версию…")
result = pattern.sub(repl, html)
OUT_HTML.write_text(result, encoding="utf-8")
print("\nГотово: %s" % OUT_HTML)
print("Размер: %.1f МБ — один файл, работает без сервера и без интернета." % (OUT_HTML.stat().st_size / 1e6))
