FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt
COPY requirements.txt .

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаём необходимые директории
RUN mkdir -p data/exports logs

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Команда запуска
CMD ["python", "bot.py"]
