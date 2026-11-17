FROM python:3.12-slim

WORKDIR /app

# Копируем зависимости
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt jinja2 aiofiles

# Копируем весь проект
COPY . .

# Инициализация БД
RUN cd backend && python3 init_db.py

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
