# Базовый образ
FROM python:3.9-slim

# Установка рабочей директории
WORKDIR /app

# Копирование файлов в контейнер
COPY . .

# Установка зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Команда для запуска приложения
CMD ["python", "main.py"]