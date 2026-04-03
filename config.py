import os
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, urlparse

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback для окружений без python-dotenv
    def load_dotenv(*args, **kwargs):
        return False

# Загружаем переменные окружения
load_dotenv()


def normalize_database_url(database_url: str) -> str:
    """Привести URL БД к формату, совместимому с SQLAlchemy и psycopg."""
    if not database_url:
        return database_url

    normalized = database_url.strip()
    if normalized.startswith("postgresql+psycopg://"):
        return normalized
    if normalized.startswith("postgres://"):
        return "postgresql+psycopg://" + normalized[len("postgres://"):]
    if normalized.startswith("postgresql://"):
        return "postgresql+psycopg://" + normalized[len("postgresql://"):]
    return normalized


def build_database_url_from_pg_env() -> str:
    """Собрать PostgreSQL URL из Railway PG* переменных."""
    host = os.getenv("PGHOST", "").strip()
    port = os.getenv("PGPORT", "").strip()
    user = os.getenv("PGUSER", "").strip()
    password = os.getenv("PGPASSWORD", "").strip()
    database = os.getenv("PGDATABASE", "").strip()

    if not all((host, port, user, password, database)):
        return ""

    sslmode = (
        os.getenv("PGSSLMODE", "").strip()
        or os.getenv("DATABASE_SSLMODE", "").strip()
        or "require"
    )
    query = f"?sslmode={quote_plus(sslmode)}" if sslmode else ""
    return (
        f"postgresql+psycopg://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{quote_plus(database)}{query}"
    )


def resolve_database_url(default_sqlite_url: str) -> str:
    """Выбрать рабочий URL БД из DATABASE_URL или PG* переменных Railway."""
    raw_database_url = os.getenv("DATABASE_URL", "").strip()
    normalized = normalize_database_url(raw_database_url)
    if normalized and "://" in normalized:
        return normalized

    pg_database_url = build_database_url_from_pg_env()
    if pg_database_url:
        return pg_database_url

    return normalize_database_url(default_sqlite_url)


def detect_database_url_source(default_sqlite_url: str) -> str:
    """Определить источник итоговой строки подключения."""
    raw_database_url = os.getenv("DATABASE_URL", "").strip()
    normalized = normalize_database_url(raw_database_url)
    if normalized and "://" in normalized:
        return "DATABASE_URL"
    if build_database_url_from_pg_env():
        return "PG_ENV"
    return "DEFAULT_SQLITE"


def summarize_database_url(database_url: str) -> dict:
    """Вернуть безопасную сводку по строке подключения без секретов."""
    parsed = urlparse(database_url)
    query = parse_qs(parsed.query)
    database = parsed.path.lstrip("/") if parsed.path else ""
    summary = {
        "scheme": parsed.scheme or "",
        "host": parsed.hostname or "",
        "port": str(parsed.port or ""),
        "database": database,
        "sslmode": (query.get("sslmode") or [""])[0],
    }

    if database_url.startswith("sqlite"):
        summary["database"] = database or database_url.rsplit("/", 1)[-1]

    return summary


# Базовые настройки
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR = Path(os.getenv("LOGS_DIR", str(PROJECT_ROOT / "logs")))
LOGS_DIR.mkdir(exist_ok=True)
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", str(DATA_DIR / "exports")))
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# База данных
DEFAULT_SQLITE_DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'parser_data.db'}"
DATABASE_URL_SOURCE = detect_database_url_source(DEFAULT_SQLITE_DATABASE_URL)
DATABASE_URL = resolve_database_url(DEFAULT_SQLITE_DATABASE_URL)
DATABASE_URL_SUMMARY = summarize_database_url(DATABASE_URL)

# Логирование
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# API настройки
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
DEFAULT_PARSE_LIMIT = int(os.getenv("DEFAULT_PARSE_LIMIT", "15"))

# Кэш
CACHE_DIR = Path(os.getenv("CACHE_DIR", str(DATA_DIR / "cache")))
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))
CACHE_SCHEMA_VERSION = os.getenv("CACHE_SCHEMA_VERSION", "4").strip() or "4"

# Режимы разработки
ENABLE_DEMO_FALLBACK = os.getenv("ENABLE_DEMO_FALLBACK", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

# 2ГИС настройки
GIS2_BASE_URL = os.getenv("GIS2_BASE_URL", "https://2gis.kz").rstrip("/")
GIS2_API_URL = os.getenv("GIS2_API_URL", "https://api.2gis.com/api/search").rstrip("/")

# Kaspi настройки
KASPI_BASE_URL = os.getenv("KASPI_BASE_URL", "https://kaspi.kz").rstrip("/")
KASPI_PRODUCTS_URL = os.getenv("KASPI_PRODUCTS_URL", f"{KASPI_BASE_URL}/yml/product-view/pl/results").rstrip("/")
KASPI_SEARCH_URL = KASPI_PRODUCTS_URL
KASPI_OFFERS_URL = os.getenv("KASPI_OFFERS_URL", f"{KASPI_BASE_URL}/yml/offer-view/offers").rstrip("/")
KASPI_CITIES_URL = os.getenv("KASPI_CITIES_URL", f"{KASPI_BASE_URL}/yml/city-registry/cities").rstrip("/")

# Регионы
REGIONS = {
    "almaty": "Алматы",
    "nur_sultan": "Астана",
    "karaganda": "Караганда",
    "aktobe": "Актобе",
    "shymkent": "Шымкент",
    "moscow": "Москва",
    "spb": "Санкт-Петербург",
    "ekb": "Екатеринбург",
    "novosib": "Новосибирск",
}

# Категории для парсинга
CATEGORIES = {
    "retail": "Розница",
    "wholesale": "Оптовая торговля",
    "manufacturing": "Производство",
    "services": "Услуги",
    "food": "Продукты и напитки",
    "pharmacy": "Аптеки",
    "auto": "Автомобильные услуги",
    "beauty": "Красота и здоровье",
}


KASPI_SUPPORTED_REGIONS = tuple(
    key
    for key in ("almaty", "nur_sultan", "karaganda", "aktobe", "shymkent")
    if key in REGIONS
)


def require_telegram_token() -> str:
    """Вернуть токен Telegram или выбросить понятную ошибку."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не установлен в .env")
    return TELEGRAM_BOT_TOKEN


def get_region_name(region_key: str) -> str:
    """Получить человекочитаемое название региона."""
    return REGIONS.get(region_key, region_key)
