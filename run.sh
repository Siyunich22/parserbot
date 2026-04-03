#!/bin/bash

# Скрипт запуска для Linux/macOS

echo "🚀 Запуск Parser Bot..."

# Проверяем виртуальное окружение
if [ ! -d "venv" ]; then
    echo "📦 Создание виртуального окружения..."
    python3 -m venv venv
fi

# Активируем окружение
source venv/bin/activate

# Устанавливаем зависимости
echo "📦 Установка зависимостей..."
pip install -r requirements.txt

# Проверяем .env
if [ ! -f ".env" ]; then
    echo "📝 Создание .env файла..."
    cp .env.example .env
    echo "⚠️  Отредактируйте .env и добавьте TELEGRAM_BOT_TOKEN"
fi

# Запускаем бота
echo "✅ Запуск бота..."
python bot.py
