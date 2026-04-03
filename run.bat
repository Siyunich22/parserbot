@echo off
REM Скрипт запуска для Windows

echo 🚀 Запуск Parser Bot...

REM Проверяем виртуальное окружение
if not exist "venv" (
    echo 📦 Создание виртуального окружения...
    python -m venv venv
)

REM Активируем окружение
call venv\Scripts\activate.bat

REM Устанавливаем зависимости
echo 📦 Установка зависимостей...
pip install -r requirements.txt

REM Проверяем .env
if not exist ".env" (
    echo 📝 Создание .env файла...
    copy .env.example .env
    echo ⚠️  Отредактируйте .env и добавьте TELEGRAM_BOT_TOKEN
)

REM Запускаем бота
echo ✅ Запуск бота...
python bot.py

pause
