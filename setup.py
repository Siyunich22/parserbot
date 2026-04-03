#!/usr/bin/env python3
"""
Скрипт для быстрого запуска проекта Parser Bot
"""

import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Проверить версию Python"""
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        sys.exit(1)
    print(f"✅ Python версия: {sys.version.split()[0]}")

def create_env_file():
    """Создать .env файл если его нет"""
    env_file = Path(".env")
    if not env_file.exists():
        example_file = Path(".env.example")
        if example_file.exists():
            with open(example_file, 'r') as f:
                content = f.read()
            with open(env_file, 'w') as f:
                f.write(content)
            print("✅ Создан файл .env")
        else:
            print("⚠️  Файл .env.example не найден")

def install_dependencies():
    """Установить зависимости"""
    print("📦 Установка зависимостей...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Зависимости установлены")
    except subprocess.CalledProcessError:
        print("❌ Ошибка при установке зависимостей")
        sys.exit(1)

def check_token():
    """Проверить наличие токена"""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, 'r') as f:
            content = f.read()
            if "your_bot_token_here" in content or "TELEGRAM_BOT_TOKEN=" not in content:
                print("⚠️  ВНИМАНИЕ: TELEGRAM_BOT_TOKEN не установлен в .env")
                print("   1. Получите токен от @BotFather: https://t.me/botfather")
                print("   2. Отредактируйте .env и добавьте токен")
                return False
    return True

def main():
    """Основная функция"""
    print("🚀 Parser Bot - Быстрый запуск\n")
    
    # Проверяем Python версию
    check_python_version()
    
    # Создаём .env файл
    create_env_file()
    
    # Проверяем токен
    if not check_token():
        print("\n⚠️  Пожалуйста, установите токен и попробуйте снова")
        return
    
    # Устанавливаем зависимости
    install_dependencies()
    
    print("\n✅ Всё готово к запуску!")
    print("📍 Следующие шаги:")
    print("   1. Убедитесь, что TELEGRAM_BOT_TOKEN установлен в .env")
    print("   2. Запустите бота: python bot.py")
    print("   3. Найдите вашего бота в Telegram и нажмите /start\n")

if __name__ == "__main__":
    main()
