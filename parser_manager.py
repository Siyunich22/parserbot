import hashlib
from typing import List, Dict, Optional
from datetime import UTC, datetime

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from config import get_region_name
from database import Company, ParseSession, ParseResult
from logger import setup_logger
from parsers.gis2 import Parser2GIS
from parsers.kaspi import ParserKaspi

logger = setup_logger("parser_manager")


def utcnow():
    """Наивный UTC datetime для записи в текущую схему БД."""
    return datetime.now(UTC).replace(tzinfo=None)


class ParserManager:
    """Менеджер парсеров"""
    
    def __init__(self):
        self.parser_2gis = Parser2GIS()
        self.parser_kaspi = ParserKaspi()
    
    def parse(
        self,
        db: Session,
        query: str,
        source: str = "both",
        city: str = "almaty",
              user_id: int = None, limit: int = 50) -> ParseSession:
        """
        Парсить данные из источников
        
        Args:
            db: Сессия БД
            query: Поисковый запрос
            source: Источник (2gis, kaspi, both)
            city: Город
            user_id: ID пользователя Telegram
            limit: Лимит результатов на источник
            
        Returns:
            Сессия парсинга с результатами
        """
        logger.info(
            "Новая сессия парсинга - query: %s, source: %s, city: %s",
            query,
            source,
            city,
        )

        parse_session = ParseSession(
            user_id=user_id,
            query=query,
            region=get_region_name(city),
            source=source,
            status="processing",
        )
        db.add(parse_session)
        db.commit()
        db.refresh(parse_session)

        logger.info("Сессия %s создана в БД", parse_session.id)

        total_results = 0

        try:
            if source in ["2gis", "both"]:
                logger.info("Запуск парсера 2ГИС для: %s", query)
                results = self.parser_2gis.search(query, city, limit)
                logger.info("Парсер 2ГИС вернул %s результатов", len(results))
                linked = self._save_results(db, parse_session.id, results, "2gis")
                total_results += linked
                logger.info("К сессии %s привязано %s результатов из 2ГИС", parse_session.id, linked)

            if source in ["kaspi", "both"]:
                logger.info("Запуск парсера Kaspi для: %s", query)
                results = self.parser_kaspi.search(query, city=city, limit=limit)
                logger.info("Парсер Kaspi вернул %s результатов", len(results))
                linked = self._save_results(db, parse_session.id, results, "kaspi")
                total_results += linked
                logger.info("К сессии %s привязано %s результатов из Kaspi", parse_session.id, linked)

            parse_session.status = "completed"
            parse_session.results_count = total_results
            parse_session.completed_at = utcnow()

            db.commit()
            db.refresh(parse_session)

            logger.info(
                "Парсинг завершён: %s - найдено %s результатов (session_id=%s)",
                query,
                total_results,
                parse_session.id,
            )

        except Exception as e:
            logger.error("Ошибка при парсинге: %s", e, exc_info=True)
            db.rollback()

            failed_session = db.query(ParseSession).filter(
                ParseSession.id == parse_session.id
            ).first()
            if failed_session:
                failed_session.status = "failed"
                failed_session.error_message = f"{type(e).__name__}: {e}"
                failed_session.completed_at = utcnow()
                db.commit()
                db.refresh(failed_session)
                logger.info("Сессия %s обновлена в БД со статусом failed", failed_session.id)
                return failed_session

            raise

        logger.info("Сессия %s обновлена в БД", parse_session.id)
        return parse_session

    def _save_results(
        self,
        db: Session,
        parse_session_id: int,
        results: List[Dict],
        source: str,
    ) -> int:
        """Сохранить результаты парсинга и привязать их к конкретной сессии."""
        linked_count = 0
        seen_source_ids = set()

        for item in results:
            source_id = item.get("source_id")
            if not source_id or source_id in seen_source_ids:
                continue

            seen_source_ids.add(source_id)
            added_link = False
            payload = self._prepare_company_payload(item, source)

            try:
                with db.begin_nested():
                    company = db.query(Company).filter(Company.source_id == payload["source_id"]).first()

                    if not company:
                        company = Company(**payload)
                        db.add(company)
                    else:
                        company.name = payload["name"] or company.name
                        company.phone = payload["phone"] or company.phone
                        company.email = payload["email"] or company.email
                        company.website = payload["website"] or company.website
                        company.address = payload["address"] or company.address
                        company.city = payload["city"] or company.city
                        company.category = payload["category"] or company.category
                        company.rating = payload["rating"] or company.rating
                        company.source_url = payload["source_url"] or company.source_url
                        company.description = payload["description"] or company.description
                        company.last_updated = utcnow()

                    db.flush()

                    link_exists = db.query(ParseResult).filter(
                        ParseResult.parse_session_id == parse_session_id,
                        ParseResult.company_id == company.id,
                    ).first()
                    if not link_exists:
                        db.add(ParseResult(parse_session_id=parse_session_id, company_id=company.id))
                        db.flush()
                        added_link = True
            except SQLAlchemyError as exc:
                logger.warning(
                    "Пропускаем запись source=%s session=%s source_id=%s: %s",
                    source,
                    parse_session_id,
                    payload["source_id"],
                    exc,
                    exc_info=True,
                )
                continue

            if added_link:
                linked_count += 1

        db.commit()
        logger.info("К сессии %s привязано %s записей из %s", parse_session_id, linked_count, source)
        return linked_count

    def _prepare_company_payload(self, item: Dict, source: str) -> Dict:
        """Нормализовать и ограничить поля под текущую схему БД."""
        return {
            "name": self._fit_string(item.get("name"), 255, fallback="Без названия"),
            "phone": self._fit_contact(item.get("phone"), 20),
            "email": self._fit_contact(item.get("email"), 255),
            "website": self._fit_contact(item.get("website"), 255),
            "address": self._fit_string(item.get("address"), 500),
            "city": self._fit_string(item.get("city"), 100),
            "category": self._fit_string(item.get("category"), 100),
            "source": self._fit_string(source, 50),
            "rating": item.get("rating"),
            "source_url": self._fit_string(item.get("source_url"), 500),
            "source_id": self._fit_source_id(item.get("source_id"), 100),
            "description": item.get("description"),
        }

    def _fit_contact(self, value, max_length: int) -> Optional[str]:
        """Сохранить только первый контакт, чтобы не ломать текущую схему."""
        if value is None:
            return None
        parts = [part.strip() for part in str(value).split("|") if part.strip()]
        primary = parts[0] if parts else str(value).strip()
        return self._fit_string(primary, max_length)

    def _fit_string(self, value, max_length: int, fallback: Optional[str] = None) -> Optional[str]:
        """Обрезать строку под ограничение столбца."""
        if value is None:
            return fallback
        text = str(value).strip()
        if not text:
            return fallback
        return text[:max_length]

    def _fit_source_id(self, value, max_length: int) -> str:
        """Стабильно укоротить source_id без потери уникальности."""
        text = self._fit_string(value, 2048, fallback="unknown-source") or "unknown-source"
        if len(text) <= max_length:
            return text
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]
        prefix = text[: max_length - len(digest) - 1]
        return f"{prefix}-{digest}"

    def get_latest_session(self, db: Session, user_id: int) -> Optional[ParseSession]:
        """Получить последнюю завершённую сессию пользователя."""
        return db.query(ParseSession).filter(
            ParseSession.user_id == user_id,
            ParseSession.status == "completed",
        ).order_by(ParseSession.started_at.desc()).first()

    def get_session_results(
        self,
        db: Session,
        parse_session_id: int,
        limit: Optional[int] = None,
    ) -> List[Company]:
        """Получить компании, относящиеся к конкретной сессии."""
        query_obj = db.query(Company).join(
            ParseResult,
            ParseResult.company_id == Company.id,
        ).filter(
            ParseResult.parse_session_id == parse_session_id,
            Company.is_active == True,
        ).order_by(Company.rating.is_(None), Company.rating.desc(), Company.name.asc())

        if limit:
            query_obj = query_obj.limit(limit)

        return query_obj.all()

    def search_in_db(self, db: Session, query: str, city: str = None,
                     source: str = None) -> List[Company]:
        """Поиск в локальной базе"""
        query_obj = db.query(Company)
        
        if query:
            query_obj = query_obj.filter(
                (Company.name.ilike(f"%{query}%")) |
                (Company.description.ilike(f"%{query}%"))
            )
        
        if city:
            query_obj = query_obj.filter(Company.city.ilike(f"%{city}%"))
        
        if source:
            query_obj = query_obj.filter(Company.source == source)
        
        return query_obj.all()
