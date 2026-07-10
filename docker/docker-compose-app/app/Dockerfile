FROM python:3.9

# Создаём рабочую директорию
WORKDIR /app

# Копируем файлы в контейнер
COPY app/main.py /app/main.py
COPY requirements.txt /app/requirements.txt

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Запускаем main.py
CMD ["python", "main.py"]
