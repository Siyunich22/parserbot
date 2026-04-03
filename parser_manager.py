from typing import List, Dict, Optional
from datetime import UTC, datetime

from sqlalchemy.orm import Session

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

            logger.info(
                "Парсинг завершён: %s - найдено %s результатов (session_id=%s)",
                query,
                total_results,
                parse_session.id,
            )

        except Exception as e:
            logger.error("Ошибка при парсинге: %s", e, exc_info=True)
            parse_session.status = "failed"
            parse_session.error_message = str(e)

        db.commit()
        db.refresh(parse_session)
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
            company = db.query(Company).filter(Company.source_id == source_id).first()

            if not company:
                company = Company(
                    name=item.get("name", ""),
                    phone=item.get("phone"),
                    email=item.get("email"),
                    website=item.get("website"),
                    address=item.get("address"),
                    city=item.get("city"),
                    category=item.get("category"),
                    source=source,
                    rating=item.get("rating"),
                    source_url=item.get("source_url"),
                    source_id=source_id,
                    description=item.get("description"),
                )
                db.add(company)
            else:
                company.name = item.get("name") or company.name
                company.phone = item.get("phone") or company.phone
                company.email = item.get("email") or company.email
                company.website = item.get("website") or company.website
                company.address = item.get("address") or company.address
                company.city = item.get("city") or company.city
                company.category = item.get("category") or company.category
                company.rating = item.get("rating") or company.rating
                company.source_url = item.get("source_url") or company.source_url
                company.description = item.get("description") or company.description
                company.last_updated = utcnow()

            db.flush()

            link_exists = db.query(ParseResult).filter(
                ParseResult.parse_session_id == parse_session_id,
                ParseResult.company_id == company.id,
            ).first()
            if not link_exists:
                db.add(ParseResult(parse_session_id=parse_session_id, company_id=company.id))
                linked_count += 1

        db.commit()
        logger.info("К сессии %s привязано %s записей из %s", parse_session_id, linked_count, source)
        return linked_count

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
