# Railway Deploy

## Что уже подготовлено

- `railway.toml` включает сборку через `Dockerfile`
- `DATABASE_URL` автоматически нормализуется для PostgreSQL / Railway
- `requirements.txt` включает PostgreSQL-драйвер `psycopg`
- `.dockerignore` исключает локальную БД, `.env`, `venv`, логи и кеши из образа

## Как деплоить

1. Создай новый Railway project.
2. Добавь PostgreSQL service.
3. Добавь этот репозиторий как отдельный service.
4. Деплой делай как worker-сервис с одним экземпляром.

## Обязательные переменные

В variables сервиса задай:

```env
TELEGRAM_BOT_TOKEN=...
DATABASE_URL=${{Postgres.DATABASE_URL}}
LOG_LEVEL=INFO
ENABLE_DEMO_FALLBACK=false
DEFAULT_PARSE_LIMIT=30
```

## Важно

- Держи `1 replica`, иначе у Telegram long polling появится `getUpdates conflict`.
- Это не HTTP-приложение, поэтому healthcheck path не нужен.
- Логи, кэш и экспортные файлы внутри контейнера эфемерны. Данные сессий и результатов должны храниться в PostgreSQL.
- Экспорт в CSV / XLSX работает, но файл живёт только внутри текущего контейнера до перезапуска. Пользователь получает его сразу в Telegram, поэтому обычный сценарий не ломается.

## Локально перед деплоем

```powershell
python -m py_compile bot.py config.py database.py export.py
python -m unittest discover -s tests -v
```
