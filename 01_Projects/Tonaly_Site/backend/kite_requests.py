"""Заявки Роману: обучение и заказ Eleveight."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "kite_requests.jsonl"

TOPICS = {
    "lesson": "Обучение кайту",
    "order": "Заказ снаряжения",
}

PHONE_DISPLAY = "+7 (938) 348-01-65"


def topic_label(topic: str) -> str:
    return TOPICS.get(topic, TOPICS["lesson"])


def save_request(payload: dict) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}
    with DATA_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def notify_email(payload: dict, to_addr: str) -> None:
    if not to_addr:
        return
    topic = topic_label(payload.get("topic") or "")
    product = payload.get("product_name") or "—"
    body = (
        f"Тема: {topic}\n"
        f"Модель: {product}\n"
        f"Имя: {payload.get('name') or '—'}\n"
        f"Контакт: {payload.get('contact') or '—'}\n"
        f"Размер: {payload.get('size') or '—'}\n"
        f"Сообщение:\n{payload.get('message') or '—'}\n"
    )
    message = (
        f"From: noreply@rml-s.ru\n"
        f"To: {to_addr}\n"
        f"Subject: Заявка Роману: {topic}\n"
        f"Content-Type: text/plain; charset=utf-8\n"
        f"\n"
        f"{body}"
    )
    try:
        subprocess.run(
            ["/usr/sbin/sendmail", "-t", "-oi"],
            input=message.encode("utf-8"),
            check=False,
            timeout=8,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
