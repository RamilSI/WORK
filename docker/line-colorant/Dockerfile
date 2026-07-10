# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл с зависимостями (если есть)
COPY requirements.txt .

# Устанавливаем зависимости (если есть)
RUN pip install --no-cache-dir -r requirements.txt

# Копируем ваш Python-скрипт в контейнер
COPY line-color.py .

# Копируем папку с входящими файлами
COPY input /app/input

# Создаем папку для исходящих файлов
RUN mkdir -p /app/output

# Команда для запуска скрипта
CMD ["python", "line-color.py"]