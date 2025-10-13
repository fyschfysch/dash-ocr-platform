# Используем официальный Python образ
FROM python:3.9-slim-bullseye

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаем пользователя без root прав
RUN useradd --create-home --shell /bin/bash ocr_user \
    && chown -R ocr_user:ocr_user /app
USER ocr_user

# Открываем порт
EXPOSE 9050

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV TESSERACT_CMD=/usr/bin/tesseract

# Команда запуска
CMD ["python", "app.py", "--host", "0.0.0.0", "--port", "9050"]
