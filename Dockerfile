# Используем легкий образ Python
FROM python:3.10-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONPATH=/app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium

# Копируем весь код
COPY . .

# Открываем порт для Chainlit
EXPOSE 8000

# Команда для запуска (с hot-reload для разработки)
CMD ["chainlit", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]