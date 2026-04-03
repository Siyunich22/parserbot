"""
Кэширование результатов парсинга
Сохраняет результаты поиска во время для улучшения производительности и избегания rate limiting
"""
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from logger import setup_logger
import os
from config import CACHE_DIR, CACHE_TTL_HOURS, CACHE_SCHEMA_VERSION

logger = setup_logger("cache")

class SearchCache:
    """Простой file-based кэш для результатов поиска"""
    
    def __init__(self, cache_dir: str = "data/cache", ttl_hours: int = 24):
        """
        Args:
            cache_dir: Директория для хранения кэша
            ttl_hours: Время жизни кэша в часах
        """
        self.cache_dir = cache_dir
        self.ttl = timedelta(hours=ttl_hours)
        
        # Создаём директорию если её нет
        os.makedirs(cache_dir, exist_ok=True)
        logger.info(f"Cache initialized: {cache_dir} (TTL: {ttl_hours}h)")
    
    def _get_cache_key(self, source: str, query: str, city: str, limit: Optional[int] = None) -> str:
        """Генерируем ключ кэша"""
        limit_suffix = str(limit) if limit is not None else "all"
        key_string = f"v{CACHE_SCHEMA_VERSION}:{source}:{query}:{city}:{limit_suffix}".lower()
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cache_path(self, key: str) -> str:
        """Получить путь файла кэша"""
        return os.path.join(self.cache_dir, f"{key}.json")
    
    def get(self, source: str, query: str, city: str, limit: Optional[int] = None) -> Optional[List[Dict]]:
        """
        Получить результаты из кэша
        
        Args:
            source: Источник (2gis, kaspi)
            query: Поисковый запрос
            city: Город
            
        Returns:
            Результаты если кэш актуален, иначе None
        """
        try:
            key = self._get_cache_key(source, query, city, limit)
            path = self._get_cache_path(key)
            
            if not os.path.exists(path):
                logger.debug(f"Cache MISS: {source}/{query}/{city}/{limit or 'all'}")
                return None
            
            # Проверяем TTL
            file_mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if datetime.now() - file_mtime > self.ttl:
                logger.info(f"Cache EXPIRED: {source}/{query}/{city}/{limit or 'all'}")
                os.remove(path)
                return None
            
            # Читаем данные
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            logger.info(f"Cache HIT: {source}/{query}/{city}/{limit or 'all'} ({len(data)} results)")
            return data
            
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None
    
    def set(
        self,
        source: str,
        query: str,
        city: str,
        results: List[Dict],
        limit: Optional[int] = None,
    ) -> bool:
        """
        Сохранить результаты в кэш
        
        Args:
            source: Источник (2gis, kaspi)
            query: Поисковый запрос
            city: Город
            results: Результаты для сохранения
            
        Returns:
            True если успешно, False иначе
        """
        try:
            key = self._get_cache_key(source, query, city, limit)
            path = self._get_cache_path(key)
            
            # Сохраняем JSON
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Cache SET: {source}/{query}/{city}/{limit or 'all'} ({len(results)} results)")
            return True
            
        except Exception as e:
            logger.error(f"Cache write error: {e}")
            return False
    
    def clear(self) -> bool:
        """Очистить весь кэш"""
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.json'):
                    os.remove(os.path.join(self.cache_dir, filename))
            
            logger.info("Cache CLEARED")
            return True
            
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False


# Глобальный экземпляр кэша
_search_cache = None

def get_search_cache() -> SearchCache:
    """Получить глобальный экземпляр кэша"""
    global _search_cache
    if _search_cache is None:
        _search_cache = SearchCache(str(CACHE_DIR), CACHE_TTL_HOURS)
    return _search_cache
