import hashlib
from typing import Dict, List, Optional
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse

import requests

from cache import get_search_cache
from config import (
    API_TIMEOUT,
    ENABLE_DEMO_FALLBACK,
    KASPI_BASE_URL,
    KASPI_CITIES_URL,
    KASPI_OFFERS_URL,
    KASPI_PRODUCTS_URL,
    get_region_name,
)
from logger import setup_logger

logger = setup_logger("parsers.kaspi")

REGION_TO_KASPI_CODE = {
    "almaty": "almaty",
    "nur_sultan": "nur-sultan",
    "karaganda": "karaganda",
    "aktobe": "aktobe",
    "shymkent": "shymkent",
}


class ParserKaspi:
    """Парсер Kaspi на публичных yml-эндпоинтах магазина."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Origin": KASPI_BASE_URL,
                "Referer": f"{KASPI_BASE_URL}/shop/search/",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        self.base_url = KASPI_BASE_URL
        self.products_url = KASPI_PRODUCTS_URL
        self.offers_url = KASPI_OFFERS_URL
        self.cities_url = KASPI_CITIES_URL
        self._cities_by_code: Optional[Dict[str, Dict]] = None

    def search(self, query: str, city: str = "", category: str = "", limit: int = 50) -> List[Dict]:
        """Поиск продавцов в Kaspi Магазине."""
        try:
            logger.info("[KASPI] Searching: '%s' in city '%s'", query, city)

            cache = get_search_cache()
            cache_city = city or "almaty"
            cached = cache.get("kaspi", query, cache_city)
            if cached:
                logger.info("[CACHE HIT] Kaspi: %s results", len(cached))
                return cached[:limit]

            real_results = self._search_real_kaspi(query, city, category, limit)
            if real_results:
                logger.info("[REAL] Kaspi found %s results for '%s'", len(real_results), query)
                cache.set("kaspi", query, cache_city, real_results)
                return real_results[:limit]

            logger.warning("[KASPI] No live results for '%s' in %s", query, cache_city)
            if ENABLE_DEMO_FALLBACK:
                demo_results = self._generate_demo_results(query, city, limit)
                cache.set("kaspi", query, cache_city, demo_results)
                return demo_results
            return []

        except Exception as exc:
            logger.error("[ERROR] Kaspi parsing failed: %s", exc, exc_info=True)
            if ENABLE_DEMO_FALLBACK:
                return self._generate_demo_results(query, city, min(limit, 5))
            return []

    def _search_real_kaspi(self, query: str, city: str, category: str, limit: int) -> List[Dict]:
        city_info = self._resolve_city(city)
        if not city_info:
            logger.warning("[KASPI] Unsupported or unresolved city: %s", city)
            return []

        city_id = str(city_info["id"])
        city_name = city_info["name"] or get_region_name(city or "almaty")
        max_pages = max(1, min(5, (limit // 12) + 2))

        merchants: Dict[str, Dict] = {}

        for page in range(max_pages):
            products = self._fetch_products(query, page)
            if not products:
                break

            new_merchants_on_page = 0

            for product in products:
                offers = self._fetch_offers(product, city_id)

                if offers:
                    for offer in offers[:3]:
                        result = self._build_result_from_offer(
                            product=product,
                            offer=offer,
                            city_id=city_id,
                            city_name=city_name,
                            requested_category=category,
                        )
                        if not result:
                            continue

                        key = result["source_id"]
                        if key in merchants:
                            self._merge_result(merchants[key], result)
                            continue

                        merchants[key] = result
                        new_merchants_on_page += 1
                        if len(merchants) >= limit:
                            break
                else:
                    result = self._build_result_from_best_merchant(
                        product=product,
                        city_id=city_id,
                        city_name=city_name,
                        requested_category=category,
                    )
                    if result:
                        key = result["source_id"]
                        if key in merchants:
                            self._merge_result(merchants[key], result)
                        else:
                            merchants[key] = result
                            new_merchants_on_page += 1

                if len(merchants) >= limit:
                    break

            if len(merchants) >= limit or new_merchants_on_page == 0:
                break

        return list(merchants.values())[:limit]

    def _resolve_city(self, city: str) -> Optional[Dict]:
        cities_by_code = self._get_cities_by_code()
        region_key = (city or "almaty").strip().lower()
        kaspi_code = REGION_TO_KASPI_CODE.get(region_key, region_key.replace("_", "-"))
        city_info = cities_by_code.get(kaspi_code)

        if city_info:
            return city_info

        human_name = get_region_name(region_key).lower()
        for item in cities_by_code.values():
            candidates = [str(item.get("name", "")).lower()]
            for localized in item.get("dictionaryList", []):
                candidates.append(str(localized.get("name", "")).lower())
            if human_name in candidates:
                return item

        return None

    def _get_cities_by_code(self) -> Dict[str, Dict]:
        if self._cities_by_code is not None:
            return self._cities_by_code

        payload = self._request_json("GET", self.cities_url)
        if not isinstance(payload, list):
            raise ValueError("Kaspi city directory returned unexpected payload")

        self._cities_by_code = {
            str(item.get("code")): item
            for item in payload
            if item.get("code") and item.get("visible", True)
        }
        return self._cities_by_code

    def _fetch_products(self, query: str, page: int) -> List[Dict]:
        payload = self._request_json(
            "GET",
            self.products_url,
            params={"text": query, "page": page},
            headers={"Referer": f"{KASPI_BASE_URL}/shop/search/?text={quote(query)}"},
        )
        if isinstance(payload, dict):
            data = payload.get("data", [])
            return data if isinstance(data, list) else []
        return []

    def _fetch_offers(self, product: Dict, city_id: str) -> List[Dict]:
        product_id = product.get("id")
        if not product_id:
            return []

        payload = {
            "cityId": city_id,
            "options": ["PRICE"],
            "entries": [
                {
                    "sku": str(product_id),
                    "hasVariants": bool(product.get("hasVariants")),
                    "product": {
                        "brand": product.get("brand") or "",
                        "categoryCodes": product.get("categoryCodes") or [],
                        "baseProductCodes": product.get("baseProductCodes") or [],
                        "groups": product.get("groups") or [str(product_id)],
                    },
                }
            ],
        }

        response = self._request_json(
            "POST",
            self.offers_url,
            json=payload,
            headers={
                "Content-Type": "application/json;charset=UTF-8",
                "Referer": f"{KASPI_BASE_URL}{product.get('shopLink', '/shop/search/')}",
            },
        )

        if isinstance(response, dict):
            offers = response.get("data", [])
        else:
            offers = response

        if not isinstance(offers, list):
            return []

        return [item for item in offers if isinstance(item, dict) and item.get("merchantName")]

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        timeout = kwargs.pop("timeout", API_TIMEOUT)
        headers = kwargs.pop("headers", {})
        last_error: Optional[Exception] = None

        for attempt in range(3):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=timeout,
                    headers=headers,
                    **kwargs,
                )
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                logger.warning(
                    "[KASPI] Request failed (%s/3): %s %s - %s",
                    attempt + 1,
                    method,
                    url,
                    exc,
                )

        if last_error:
            raise last_error
        raise RuntimeError(f"Kaspi request failed without exception for {url}")

    def _request_json(self, method: str, url: str, **kwargs):
        response = self._request(method, url, **kwargs)
        return response.json()

    def _build_result_from_offer(
        self,
        product: Dict,
        offer: Dict,
        city_id: str,
        city_name: str,
        requested_category: str,
    ) -> Optional[Dict]:
        merchant_name = offer.get("merchantName")
        merchant_id = offer.get("merchantId") or merchant_name
        if not merchant_name or not merchant_id:
            return None

        source_url = self._build_product_url(product.get("shopLink"), city_id)
        product_title = product.get("title") or offer.get("title")
        price = offer.get("priceFormatted") or self._format_price(offer.get("price"))
        reviews = offer.get("merchantReviewsQuantity")

        description_parts = []
        if product_title:
            description_parts.append(f"Товар: {product_title}")
        if price:
            description_parts.append(f"Цена: {price}")
        if reviews:
            description_parts.append(f"Отзывы продавца: {reviews}")

        return {
            "name": merchant_name,
            "phone": None,
            "email": None,
            "website": None,
            "address": None,
            "city": city_name,
            "rating": offer.get("merchantRating") or product.get("rating"),
            "source_id": self._build_source_id(merchant_id, city_id),
            "source": "kaspi",
            "source_url": source_url,
            "description": " | ".join(description_parts) or None,
            "category": self._extract_category(product, requested_category),
        }

    def _build_result_from_best_merchant(
        self,
        product: Dict,
        city_id: str,
        city_name: str,
        requested_category: str,
    ) -> Optional[Dict]:
        merchant_name = product.get("bestMerchant")
        if not merchant_name:
            return None

        description_parts = []
        if product.get("title"):
            description_parts.append(f"Товар: {product['title']}")
        if product.get("priceFormatted"):
            description_parts.append(f"Цена: {product['priceFormatted']}")
        if product.get("reviewsQuantity"):
            description_parts.append(f"Отзывы товара: {product['reviewsQuantity']}")

        return {
            "name": merchant_name,
            "phone": None,
            "email": None,
            "website": None,
            "address": None,
            "city": city_name,
            "rating": product.get("rating"),
            "source_id": self._build_source_id(merchant_name, city_id),
            "source": "kaspi",
            "source_url": self._build_product_url(product.get("shopLink"), city_id),
            "description": " | ".join(description_parts) or None,
            "category": self._extract_category(product, requested_category),
        }

    def _extract_category(self, product: Dict, requested_category: str) -> Optional[str]:
        if requested_category:
            return requested_category
        return (
            product.get("categoryRu")
            or product.get("category")
            or (product.get("categoryCodes") or [None])[0]
        )

    def _build_product_url(self, path: Optional[str], city_id: str) -> Optional[str]:
        if not path:
            return None
        absolute = urljoin(f"{self.base_url}/", path.lstrip("/"))
        parsed = urlparse(absolute)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["c"] = city_id
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _build_source_id(self, merchant_identifier: str, city_id: str) -> str:
        digest = hashlib.md5(str(merchant_identifier).encode("utf-8")).hexdigest()[:16]
        return f"kaspi_merchant_{digest}_{city_id}"

    def _merge_result(self, current: Dict, incoming: Dict) -> None:
        current_rating = current.get("rating")
        incoming_rating = incoming.get("rating")
        if incoming_rating and (not current_rating or incoming_rating > current_rating):
            current["rating"] = incoming_rating

        if not current.get("description") and incoming.get("description"):
            current["description"] = incoming["description"]

        if not current.get("source_url") and incoming.get("source_url"):
            current["source_url"] = incoming["source_url"]

        if not current.get("category") and incoming.get("category"):
            current["category"] = incoming["category"]

    def _format_price(self, value) -> Optional[str]:
        if value in (None, ""):
            return None
        try:
            amount = int(float(value))
        except (TypeError, ValueError):
            return None
        return f"{amount:,}".replace(",", " ") + " ₸"

    def _generate_demo_results(self, query: str, city: str, limit: int) -> List[Dict]:
        city_name = get_region_name(city or "almaty")
        fallback = [
            {
                "name": f"{query.title()} Demo Seller",
                "phone": None,
                "email": None,
                "website": None,
                "address": None,
                "city": city_name,
                "rating": None,
                "source_id": self._build_source_id(f"demo:{query}:{city_name}", "demo"),
                "source": "kaspi",
                "source_url": None,
                "description": "Демо-режим включён вручную через ENABLE_DEMO_FALLBACK",
                "category": query,
            }
        ]
        return fallback[:limit]
