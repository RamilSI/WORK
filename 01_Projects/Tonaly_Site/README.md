# Tonal — Сайт компании ООО «Тональ»

Промышленные лакокрасочные материалы Rem Color. Каталог продукции, цифровые сервисы, личный кабинет.

## Стек

**Бэкенд:** FastAPI + Jinja2 + SQLite  
**Фронтенд:** HTML5 + CSS3 (через шаблоны Jinja2)  
**Хостинг:** Beget VPS (Ubuntu + Nginx)

## Структура

```
01_Projects/Tonaly_Site/
├── backend/           # FastAPI сервер
│   ├── main.py        # Маршруты, Jinja2, БД
│   ├── models.py      # SQLAlchemy модели
│   ├── init_db.py     # Заполнение БД
│   └── templates/     # Шаблоны Jinja2
├── frontend/          # Статика (раздаётся Nginx)
│   ├── css/
│   ├── img/           # Фото тары, логотип, фон
│   └── docs/          # TDS (PDF)
└── Dockerfile
```

## Запуск локально

```bash
cd 01_Projects/Tonaly_Site/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 init_db.py
uvicorn main:app --reload --port 8000
```

## Добавление нового продукта

1. Добавить запись в БД через `init_db.py`
2. Положить фото в `frontend/img/{slug}-can.png`
3. Положить TDS в `frontend/docs/tds-{slug}.pdf`
4. Загрузить на сервер: `scp img/* root@46.173.19.173:/var/www/tonal/frontend/img/`

## Продакшен

Сайт: [https://rml-s.ru](https://rml-s.ru)  
Сервер: Beget VPS (Ubuntu 24.04)  
SSL: Let's Encrypt (certbot)
