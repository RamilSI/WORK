"""
TONAL Document Management System
FastAPI Backend - Windows Compatible
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import os
import uuid

# === НАСТРОЙКА ПУТЕЙ (Windows-safe) ===
BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
IMAGES_DIR = FRONTEND_DIR / "images"
UPLOADS_DIR = IMAGES_DIR / "uploads"

# Создаём папку для загрузок, если нет
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# === ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ ===
app = FastAPI(
    title="TONAL Document System",
    description="Система управления документами ООО «ТОНАЛЬ»",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === МОДЕЛИ ДАННЫХ ===
class Offer(BaseModel):
    id: str
    client: str
    date: str
    status: str
    total: float

class Report(BaseModel):
    id: str
    project: str
    inspector: str
    date: str
    status: str

class Stats(BaseModel):
    offers: int
    reports: int
    documents: int
    projects: int

# === IN-MEMORY ХРАНИЛИЩЕ ===
offers_db: List[Offer] = []
reports_db: List[Report] = []
documents_db = []

# === МАРШРУТЫ ===

# 🏠 Главная страница
@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        return {"error": f"index.html not found at {index_path}"}
    return FileResponse(str(index_path))

# 📊 Статистика
@app.get("/api/stats", response_model=Stats)
async def get_stats():
    return Stats(
        offers=len(offers_db),
        reports=len(reports_db),
        documents=len(documents_db),
        projects=8
    )

# 📋 КП
@app.get("/api/offers", response_model=List[Offer])
async def get_offers():
    return offers_db

@app.post("/api/offers")
async def create_offer(offer: Offer):
    offers_db.append(offer)
    return {"message": "КП создано", "id": offer.id}

# 📊 Отчёты
@app.get("/api/reports", response_model=List[Report])
async def get_reports():
    return reports_db

@app.post("/api/reports")
async def create_report(report: Report):
    reports_db.append(report)
    return {"message": "Отчёт создан", "id": report.id}

# 📸 Загрузка фото
@app.post("/api/reports/{report_id}/upload-photo")
async def upload_photo(report_id: str, file: UploadFile = File(...)):
    file_path = UPLOADS_DIR / f"{uuid.uuid4()}_{file.filename}"
    with open(file_path, "wb") as buffer:
        buffer.write(await file.read())
    return {"message": "Фото загружено", "path": str(file_path)}

# 🔧 Отладка путей
@app.get("/debug/paths")
async def debug_paths():
    return {
        "base_dir": str(BASE_DIR),
        "frontend_dir": str(FRONTEND_DIR),
        "frontend_exists": FRONTEND_DIR.exists(),
        "index_html": str(FRONTEND_DIR / "index.html"),
        "index_exists": (FRONTEND_DIR / "index.html").exists(),
        "images_dir": str(IMAGES_DIR),
        "images_exists": IMAGES_DIR.exists(),
        "uploads_dir": str(UPLOADS_DIR),
        "uploads_exists": UPLOADS_DIR.exists(),
    }

# 🔍 Health check
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# 📄 Технический меморандум
@app.get("/documents/memorandum")
async def get_memorandum():
    doc_path = FRONTEND_DIR / "documents" / "memorandum.html"
    if not doc_path.exists():
        return JSONResponse(status_code=404, content={"error": "Document not found"})
    with open(doc_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# 📁 Список документов
@app.get("/documents")
async def get_documents_list():
    return {
        "documents": [
            {
                "id": "memorandum-001",
                "title": "Технический меморандум по смешиванию ЛКМ",
                "date": "2026-04-09",
                "type": "technical",
                "url": "/documents/memorandum"
            }
            # Добавить другие документы
        ]
    }


# === ЗАПУСК ===
# uvicorn main:app --reload --host 127.0.0.1 --port 8000