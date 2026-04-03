from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Float,
    Text,
    Boolean,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import UTC, datetime
from config import DATABASE_URL

# Создаём базу данных
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 300

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utcnow():
    """Наивный UTC datetime для совместимости с текущей схемой SQLite."""
    return datetime.now(UTC).replace(tzinfo=None)

class Company(Base):
    """Модель компании"""
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20))
    email = Column(String(255))
    website = Column(String(255))
    address = Column(String(500))
    city = Column(String(100))
    category = Column(String(100))
    source = Column(String(50))  # 2gis, kaspi
    rating = Column(Float, nullable=True)
    employee_count = Column(Integer, nullable=True)
    description = Column(Text)
    source_url = Column(String(500))
    source_id = Column(String(100), unique=True)
    last_updated = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)
    is_active = Column(Boolean, default=True)

class ParseSession(Base):
    """Модель сессии парсинга"""
    __tablename__ = "parse_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    query = Column(String(255))
    region = Column(String(100))
    source = Column(String(50))
    results_count = Column(Integer, default=0)
    status = Column(String(20))  # processing, completed, failed
    started_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class ParseResult(Base):
    """Связь между сессией парсинга и компаниями из выдачи."""
    __tablename__ = "parse_results"
    __table_args__ = (
        UniqueConstraint("parse_session_id", "company_id", name="uq_parse_results_session_company"),
    )

    id = Column(Integer, primary_key=True, index=True)
    parse_session_id = Column(Integer, ForeignKey("parse_sessions.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)


class Export(Base):
    """Модель экспорта данных"""
    __tablename__ = "exports"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    filename = Column(String(255))
    format = Column(String(10))  # csv, xlsx
    records_count = Column(Integer)
    created_at = Column(DateTime, default=utcnow)

# Создаём таблицы
Base.metadata.create_all(bind=engine)

def get_db():
    """Получить сессию БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
