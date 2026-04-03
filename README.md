# Parser Bot 🤖

Telegram бот для автоматического парсинга и сбора контактов компаний из **2ГИС** и **Kaspi**.

## Возможности 🚀

✅ **Парсинг из 2ГИС** - Получение контактов и информации о компаниях  
✅ **Парсинг из Kaspi** - Сбор данных о продавцах и товарах  
✅ **Интеллектуальный поиск** - По ключевым словам, регионам и категориям  
✅ **Экспорт данных** - В CSV и Excel форматы  
✅ **Локальная база** - SQLite для быстрого доступа к результатам  
✅ **User-friendly интерфейс** - Удобное управление через Telegram  

## Требования 📋

- Python 3.8+
- pip (менеджер пакетов Python)
- Telegram Bot Token (получить от [@BotFather](https://t.me/botfather))

## Установка 🔧

### 1. Клонируем репозиторий
```bash
git clone <repo-url>
cd parser
```

### 2. Создаём виртуальное окружение
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Устанавливаем зависимости
```bash
pip install -r requirements.txt
```

### 4. Настраиваем переменные окружения
Копируем `.env.example` в `.env` и добавляем токен:
```bash
cp .env.example .env
```

Отредактируйте `.env`:
```
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklmnoPQRstuvWXYZ
DATABASE_URL=sqlite:///./parser_data.db
LOG_LEVEL=INFO
API_TIMEOUT=30
MAX_WORKERS=5
```

Для Railway используйте PostgreSQL и переменную `DATABASE_URL` из сервиса базы данных.

### 5. Запускаем бота
```bash
python bot.py
```

## Использование 📲

### Команды бота

- `/start` - Запуск бота и показ главного меню
- `/help` - Справка по использованию

### Основные функции

1. **🔍 Новый поиск**
   - Выберите источник (2ГИС, Kaspi или оба)
   - Выберите регион (для 2ГИС)
   - Введите поисковый запрос
   - Получите результаты

2. **📊 Посмотреть результаты**
   - Просмотр последних найденных контактов
   - Отображение 50 последних записей

3. **⬇️ Экспортировать**
   - Экспорт в CSV
   - Экспорт в Excel
   - Включены все данные (название, телефон, адрес и т.д.)

## Структура проекта 📁

```
parser/
├── bot.py                  # Основной файл Telegram бота
├── config.py              # Конфигурация приложения
├── database.py            # Модели БД и инициализация
├── parser_manager.py      # Менеджер парсеров
├── export.py              # Экспорт в CSV/Excel
├── logger.py              # Логирование
├── parsers/
│   ├── __init__.py
│   ├── gis2.py           # Парсер 2ГИС
│   └── kaspi.py          # Парсер Kaspi
├── data/                  # Хранилище данных
│   └── exports/          # Экспортированные файлы
├── logs/                  # Логи приложения
├── requirements.txt       # Зависимости Python
└── .env.example          # Пример переменных окружения
```

## Поддерживаемые города 🌍

**2ГИС:**
- Алматы
- Нур-Султан
- Караганда
- Актобе
- Шымкент
- Москва
- Санкт-Петербург
- Екатеринбург
- Новосибирск

**Kaspi:**
- Казахстан (все регионы)

## Категории поиска 🏢

- Розница
- Оптовая торговля
- Производство
- Услуги
- Продукты и напитки
- Аптеки
- Автомобильные услуги
- Красота и здоровье

## Примеры использования 💡

### Пример 1: Поиск кафе в Алматы
```
1. Нажми "🔍 Новый поиск"
2. Выбери "2ГИС"
3. Выбери "Алматы"
4. Введи "кафе"
5. Получи результаты
6. Экспортируй в Excel
```

### Пример 2: Поиск электроники на Kaspi
```
1. Нажми "🔍 Новый поиск"
2. Выбери "Kaspi"
3. Введи "электроника"
4. Получи результаты
5. Экспортируй в CSV
```

## Развёртывание 🚀

### Локальное запуска
```bash
python bot.py
```

### Запуск на сервере

### Railway

Проект готов к Railway как worker-сервис через `Dockerfile`.

- Подключите PostgreSQL service
- Передайте `TELEGRAM_BOT_TOKEN`
- Передайте `DATABASE_URL` из PostgreSQL service
- Оставьте только `1 replica`, чтобы long polling не конфликтовал

Подробная инструкция: `RAILWAY_DEPLOY.md`

#### Используя Systemd (Linux/VPS)

Создайте файл `/etc/systemd/system/parser-bot.service`:
```ini
[Unit]
Description=Parser Bot
After=network.target

[Service]
Type=simple
User=parser
WorkingDirectory=/home/parser/parser
ExecStart=/home/parser/parser/venv/bin/python bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Затем:
```bash
sudo systemctl daemon-reload
sudo systemctl enable parser-bot
sudo systemctl start parser-bot
```

#### Используя Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "bot.py"]
```

Построить и запустить:
```bash
docker build -t parser-bot .
docker run -e TELEGRAM_BOT_TOKEN=your_token parser-bot
```

## Расширение функционала 🔧

### Добавление нового источника парсинга

1. Создайте новый парсер в папке `parsers/`:
```python
# parsers/mynewparser.py
class ParserMySource:
    def search(self, query: str) -> List[Dict]:
        # Ваш код парсинга
        pass
```

2. Добавьте в `parser_manager.py`:
```python
from parsers.mynewparser import ParserMySource

class ParserManager:
    def __init__(self):
        self.parser_my_source = ParserMySource()
```

### Добавление новой команды бота

```python
async def my_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ответ")

app.add_handler(CommandHandler("mycommand", bot.my_command))
```

## Логирование 📝

Логи хранятся в папке `logs/`:
- `parser.log` - Основные логи
- `parsers.gis2.log` - Логи 2ГИС парсера
- `parsers.kaspi.log` - Логи Kaspi парсера
- `bot.log` - Логи бота

Уровень логирования настраивается в `.env` переменной `LOG_LEVEL`.

## Решение проблем 🐛

### Бот не отвечает
- Проверьте TELEGRAM_BOT_TOKEN в .env
- Убедитесь, что бот зареган в @BotFather
- Проверьте интернет соединение

### При парсинге выходит ошибка
- Проверьте логи в папке `logs/`
- Убедитесь, что сайты доступны
- Попробуйте использовать VPN (для РФ)

### Экспорт не работает
- Проверьте наличие данных в БД
- Убедитесь, что папка `data/exports/` существует
- Проверьте права доступа к файлам

## API Лимиты ⚡

- 2ГИС: ~50 запросов в минуту (рекомендуемо)
- Kaspi: ~100 запросов в минуту (зависит от IP)
- Тайм-аут запроса: 30 секунд

## Безопасность 🔒

- **Никогда** не коммитьте `.env` файл с реальными токенами
- Используйте переменные окружения для чувствительных данных
- Регулярно обновляйте зависимости
- Используйте VPN при парсинге данных

## Планы развития 📚

- [ ] Поддержка Яндекс.Карт
- [ ] Добавление рейтинговой системы
- [ ] Интеграция с CRM системами
- [ ] Веб-интерфейс
- [ ] API для интеграции
- [ ] Автоматические уведомления
- [ ] Поддержка прокси

## Лицензия 📄

MIT License. Описание смотрите в файле [LICENSE](LICENSE).

## Контакты 📞

- Email: support@parserbot.com
- Telegram: [@parserbot_support](https://t.me/parserbot_support)
- Issues: [GitHub Issues](../../issues)

## Участие в проекте 🤝

Приветствуются pull requests. Для серьёзных изменений сначала откройте issue для обсуждения.

---

**Сделано с ❤️ для МСБ**
