## Архитектурные улучшения и план интеграции реальных API

### Что было сделано

**1. Множественные API уровни ✅**
- Структура `_search_real_X()` добавле для настоящих API вызовов
- Fallback на демо-данные когда API недоступен

**2. City parameter фиксирование ✅**
- 2GIS: `search(query, city, limit)` - city используется
- Kaspi: `search(query, city, category, limit)` - city ТЕПЕРЬ используется
- parser_manager.py: исправлены оба парсера для передачи city

**3. Кэширование ✅**
- Файл-based кэш с TTL (24 часа по умолчанию)
- Сохраняет результаты поиска по (source, query, city)
- Избегает rate-limiting при повторных запросах

**4. Улучшенное логирование ✅**
- Логи структурированы как [SERVICE], [OPERATION], [STATUS]
- Удалены эмодзи для совместимости с Windows терминалом

---

## План интеграции настоящих 2ГИС и Kaspi API

### ШАГИ ИНТЕГРАЦИИ

#### 1️⃣ ИНТЕГРАЦИЯ 2ГИС API

**Файл:** `parsers/gis2.py` - метод `_search_real_2gis()`

```python
def _search_real_2gis(self, query: str, city: str, limit: int) -> List[Dict]:
    """
    Реализовать здесь:
    
    ОПЦИЯ A: Использовать официальный 2GIS API
    - Зарегистрироваться на https://dev.2gis.com/
    - Получить API ключ
    - Использовать https://dev.2gis.com/api/autocomplete или /catalog
    - Endpoint: https://api.2gis.com/{version}/search/cityobjects
    
    ОПЦИЯ B: Scraping 2GIS (если API недоступен)
    - Использовать BeautifulSoup + requests
    - GET https://2gis.kz/search?q={query}&city={city}
    - Парсить результаты из HTML
    
    Код должен:
    1. Делать HTTP запрос с query и city параметрами
    2. Парсить результаты (название, телефон, адрес, координаты)
    3. Возвращать List[Dict] с полями: name, phone, email, website, address, city, rating, source_id
    4. Обрабатывать ошибки сети и возвращать []
    """
    try:
        # TODO: Реальная реализация
        api_url = "https://api.2gis.com/search"
        params = {
            "q": query,
            "city": city,
            "limit": limit,
            # "key": os.getenv("2GIS_API_KEY")  # если нужен API ключ
        }
        
        response = self.session.get(api_url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        results = self._parse_2gis_response(data)
        
        return results[:limit]
        
    except Exception as e:
        logger.warning(f"Real 2GIS API unavailable: {e}")
        return []
```

---

#### 2️⃣ ИНТЕГРАЦИЯ KASPI API

**Файл:** `parsers/kaspi.py` - метод `_search_real_kaspi()`

```python
def _search_real_kaspi(self, query: str, city: str, category: str, limit: int) -> List[Dict]:
    """
    Реализовать здесь:
    
    ПРОБЛЕМА: Kaspi.kz НЕ имеет публичного API
    
    ОПЦИИ:
    
    ОПЦИЯ A: Использовать GraphQL API (если доступен)
    - Некоторые данные Kaspi доступны через GraphQL
    - Endpoint: https://api.kaspi.kz/graphql/
    - Требует reverse engineering
    
    ОПЦИЯ B: Scraping Kaspi.kz (основной метод)
    - GET https://kaspi.kz/shop/search/?q={query}
    - Парсить результаты чере Selenium или Puppeteer
    - ОСТОРОЖНО: Может быть заблокировано за scraping
    
    ОПЦИЯ C: Использовать альтернативные источники
    - Product databases (например, через marketplace API)
    - Комбинировать с другими источниками
    
    Для текущего MVP рекомендуется:
    - Оставить демо данные как fallback
    - Постепенно добавлять реальные источники
    """
    try:
        # TODO: Реальная реализация
        # Пока Kaspi API не доступен, используем fallback
        
        # Если когда-то будет API:
        # api_url = f"https://api.kaspi.kz/search"
        # params = {"q": query, "city": city, "limit": limit}
        # response = self.session.get(api_url, params=params)
        # return self._parse_kaspi_response(response.json())
        
        return []
        
    except Exception as e:
        logger.warning(f"Real Kaspi API unavailable: {e}")
        return []
```

---

### КОНФИГУРАЦИЯ

**Файл:** `.env` (добавить при необходимости)

```env
# 2GIS
2GIS_API_KEY=your_api_key_here
2GIS_API_URL=https://api.2gis.com

# Kaspi
KASPI_SEARCH_URL=https://kaspi.kz/shop/search
KASPI_SCRAPE_ENABLED=false

# Cache
CACHE_DIR=data/cache
CACHE_TTL_HOURS=24

# API Timeout (seconds)
API_TIMEOUT=10
```

---

### TESTING STRATEGY

1. **Unit tests для парсеров**
   ```python
   def test_2gis_real_api():
       """Test real 2GIS API when available"""
       parser = Parser2GIS()
       results = parser.search("кафе", "almaty", 5)
       assert len(results) > 0
       assert all(r.get("name") for r in results)
   ```

2. **Integration tests с кэшем**
   ```python
   def test_cache_hit():
       """Verify cache works correctly"""
       cache = get_search_cache()
       cache.set("2gis", "кафе", "almaty", [{"name": "Test"}])
       cached = cache.get("2gis", "кафе", "almaty")
       assert cached is not None
   ```

3. **Mock tests для сетевых ошибок**
   ```python
   @patch('requests.Session.get')
   def test_fallback_on_api_error(mock_get):
       """Verify fallback when API fails"""
       mock_get.side_effect = ConnectionError()
       parser = Parser2GIS()
       results = parser.search("кафе", "almaty", 5)
       assert len(results) > 0  # Should use demo data
   ```

---

### PRODUCTION DEPLOYMENT CHECKLIST

- [ ] Получить API ключи (если требуются)
- [ ] Настроить .env переменные
- [ ] Протестировать реальные API вызовы
- [ ] Добавить обработку rate limits
- [ ] Настроить логирование для мониторинга
- [ ] Добавить метрики (time-to-response, cache hit rate)
- [ ] Настроить backup sources если основной API недоступен
- [ ] Документировать API dependencies
- [ ] Создать руководство для трудовых решений

---

### ТЕКУЩИЙ СТАТУС

✅ **ГОТОВО:**
- Структура для real API integration
- City parameter передача везде
- Кэширование результатов
- Fallback на демо данные
- Обработка ошибок

🟡 **В ПРОЦЕССЕ:**
- Интеграция с реальными 2GIS API
- Интеграция с реальным Kaspi (требуется scraping из-за отсутствия публичного API)

❌ **НЕ РЕАЛИЗОВАНО:**
- Rate limiting для real API
- Авторизация/API ключи
- Мониторинг API uptime
- A/B тестирование между источниками

---

## ЗАКЛЮЧЕНИЕ

Бот теперь имеет **профессиональную архитектуру**, готовую для интеграции с реальными API источниками. Текущее состояние использует демо-данные как fallback, что позволяет боту работать немедленно, но обеспечивает путь для постепенного добавления реальных источников.

**Следующий шаг:** Интегрировать реальные 2ГИС и Kaspi API согласно документации выше.
