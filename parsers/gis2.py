import re
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from cache import get_search_cache
from config import API_TIMEOUT, ENABLE_DEMO_FALLBACK, GIS2_BASE_URL, get_region_name
from logger import setup_logger

logger = setup_logger("parsers.gis2")

NOISE_TOKENS = {
    "реклама",
    "забронировать столик",
    "позвонить",
    "написать",
    "whatsapp",
}

ADDRESS_HINTS = (
    "алматы",
    "астана",
    "караганда",
    "актобе",
    "шымкент",
    "микрорайон",
    "мкр",
    "улица",
    "ул.",
    "проспект",
    "пр.",
    "бульвар",
    "переулок",
    "шоссе",
)

SOCIAL_DOMAINS = (
    "instagram.com",
    "facebook.com",
    "vk.com",
    "youtube.com",
    "t.me",
)

MESSENGER_DOMAINS = (
    "wa.me",
    "api.whatsapp.com",
)

REGION_TO_2GIS_ROUTE = {
    "almaty": (GIS2_BASE_URL, "almaty"),
    "nur_sultan": (GIS2_BASE_URL, "astana"),
    "karaganda": (GIS2_BASE_URL, "karaganda"),
    "aktobe": (GIS2_BASE_URL, "aktobe"),
    "shymkent": (GIS2_BASE_URL, "shymkent"),
    "moscow": ("https://2gis.ru", "moscow"),
    "spb": ("https://2gis.ru", "spb"),
    "ekb": ("https://2gis.ru", "ekaterinburg"),
    "novosib": ("https://2gis.ru", "novosibirsk"),
}


class Parser2GIS:
    """Парсер 2GIS с реальными данными из публичной веб-выдачи."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        self.base_url = GIS2_BASE_URL

    def search(self, query: str, city: str = "almaty", limit: int = 50) -> List[Dict]:
        """Поиск компаний в 2GIS."""
        try:
            logger.info("[2GIS] Searching: '%s' in city %s", query, city)

            cache = get_search_cache()
            cached = cache.get("2gis", query, city, limit=limit)
            if cached:
                logger.info("[CACHE HIT] 2GIS: %s results", len(cached))
                return cached[:limit]

            real_results = self._search_real_2gis(query, city, limit)
            if real_results:
                logger.info("[REAL] 2GIS found %s results for '%s'", len(real_results), query)
                cache.set("2gis", query, city, real_results, limit=limit)
                return real_results[:limit]

            logger.warning("[2GIS] No live results for '%s' in %s", query, city)
            if ENABLE_DEMO_FALLBACK:
                demo_results = self._generate_demo_results(query, city, limit)
                cache.set("2gis", query, city, demo_results, limit=limit)
                return demo_results
            return []

        except Exception as exc:
            logger.error("[ERROR] 2GIS parsing failed: %s", exc, exc_info=True)
            if ENABLE_DEMO_FALLBACK:
                return self._generate_demo_results(query, city, min(limit, 5))
            return []

    def _search_real_2gis(self, query: str, city: str, limit: int) -> List[Dict]:
        base_url, city_slug = self._resolve_location(city)
        search_url = f"{base_url}/{city_slug}/search/{quote(query)}"
        response = self._request("GET", search_url)
        city_name = get_region_name(city)
        search_context = self._extract_search_context(response.text)

        candidates = self._collect_candidates(
            html=response.text,
            base_url=base_url,
            city_slug=city_slug,
            city_name=city_name,
        )

        total_hint = int(search_context.get("total") or len(candidates))
        if total_hint > len(candidates) and len(candidates) < limit:
            for probe_url in self._build_probe_urls(
                search_url=search_url,
                search_context=search_context,
                limit=limit,
            ):
                try:
                    probe_response = self._request("GET", probe_url)
                except requests.RequestException as exc:
                    logger.warning("[2GIS] Probe failed %s: %s", probe_url, exc)
                    continue

                self._merge_candidates(
                    candidates,
                    self._collect_candidates(
                        html=probe_response.text,
                        base_url=base_url,
                        city_slug=city_slug,
                        city_name=city_name,
                    ),
                )

                if len(candidates) >= min(limit, total_hint):
                    break

        results: List[Dict] = []
        for candidate in candidates[:limit]:
            details = self._fetch_firm_details(candidate["source_url"])
            results.append(
                {
                    "name": candidate.get("name"),
                    "phone": details.get("phone"),
                    "email": details.get("email"),
                    "website": details.get("website"),
                    "address": candidate.get("address"),
                    "city": city_name,
                    "rating": candidate.get("rating"),
                    "source_id": candidate.get("source_id"),
                    "source": "2gis",
                    "source_url": candidate.get("source_url"),
                    "description": candidate.get("description"),
                    "category": candidate.get("category"),
                }
            )

        return results

    def _resolve_location(self, city: str) -> tuple[str, str]:
        route = REGION_TO_2GIS_ROUTE.get(city)
        if route:
            return route
        return self.base_url, city

    def _collect_candidates(
        self,
        html: str,
        base_url: str,
        city_slug: str,
        city_name: str,
    ) -> List[Dict]:
        soup = BeautifulSoup(html, "lxml")
        candidates = []
        seen_ids = set()

        for link in soup.select('a[href*="/firm/"]'):
            href = (link.get("href") or "").strip()
            if not href.startswith(f"/{city_slug}/firm/"):
                continue

            firm_id = self._extract_firm_id(href)
            if not firm_id or firm_id in seen_ids:
                continue

            seen_ids.add(firm_id)
            card = self._find_card_container(link)
            summary = self._parse_search_card(card, city_name)
            if not summary.get("name"):
                continue

            candidates.append(
                {
                    "name": summary.get("name"),
                    "address": summary.get("address"),
                    "rating": summary.get("rating"),
                    "source_id": f"2gis_{firm_id}",
                    "source_url": urljoin(f"{base_url}/", href.lstrip("/")),
                    "description": summary.get("description"),
                    "category": summary.get("category"),
                }
            )

        return candidates

    def _merge_candidates(self, current: List[Dict], incoming: List[Dict]) -> None:
        seen = {item["source_id"] for item in current}
        for item in incoming:
            source_id = item.get("source_id")
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            current.append(item)

    def _extract_search_context(self, html: str) -> Dict[str, float]:
        context: Dict[str, float] = {}

        total_match = re.search(r'"hasPagesToLoad":(?:true|false),"pages":(\d+),"total":(\d+)', html)
        if total_match:
            context["pages"] = float(total_match.group(1))
            context["total"] = float(total_match.group(2))

        viewpoint_match = re.search(
            r'"viewpoint":\[\{"lon":([-\d.]+),"lat":([-\d.]+)\},\{"lon":([-\d.]+),"lat":([-\d.]+)\}\]',
            html,
        )
        if viewpoint_match:
            context["lon1"] = float(viewpoint_match.group(1))
            context["lat1"] = float(viewpoint_match.group(2))
            context["lon2"] = float(viewpoint_match.group(3))
            context["lat2"] = float(viewpoint_match.group(4))

        center_match = re.search(
            r'"center":\{"lon":([-\d.]+),"lat":([-\d.]+)\},"zoom":([-\d.]+)',
            html,
        )
        if center_match:
            context["center_lon"] = float(center_match.group(1))
            context["center_lat"] = float(center_match.group(2))
            context["zoom"] = float(center_match.group(3))

        return context

    def _build_probe_urls(
        self,
        search_url: str,
        search_context: Dict[str, float],
        limit: int,
    ) -> List[str]:
        lon1 = search_context.get("lon1")
        lat1 = search_context.get("lat1")
        lon2 = search_context.get("lon2")
        lat2 = search_context.get("lat2")
        center_lon = search_context.get("center_lon")
        center_lat = search_context.get("center_lat")
        zoom = search_context.get("zoom")

        if None in {lon1, lat1, lon2, lat2, center_lon, center_lat, zoom}:
            return []

        min_lon, max_lon = sorted((lon1, lon2))
        min_lat, max_lat = sorted((lat1, lat2))
        zoom_levels = self._get_probe_zoom_levels(float(zoom), limit)
        points = self._build_probe_points(
            min_lon=min_lon,
            max_lon=max_lon,
            min_lat=min_lat,
            max_lat=max_lat,
            center_lon=float(center_lon),
            center_lat=float(center_lat),
            limit=limit,
        )

        probe_urls = []
        seen = set()
        for detail_zoom in zoom_levels:
            for lon, lat in points:
                key = (round(lon, 4), round(lat, 4), round(detail_zoom, 2))
                if key in seen:
                    continue
                seen.add(key)
                probe_urls.append(f"{search_url}?m={lon:.6f},{lat:.6f}/{detail_zoom:.2f}")

        return probe_urls

    def _get_probe_zoom_levels(self, zoom: float, limit: int) -> List[float]:
        zoom_levels = [min(max(zoom + 2.0, 12.5), 14.0)]
        if limit > 50:
            zoom_levels.append(min(max(zoom + 2.8, 13.5), 15.0))
        return zoom_levels

    def _build_probe_points(
        self,
        min_lon: float,
        max_lon: float,
        min_lat: float,
        max_lat: float,
        center_lon: float,
        center_lat: float,
        limit: int,
    ) -> List[tuple[float, float]]:
        if limit <= 20:
            ratios = [0.2, 0.5, 0.8]
        elif limit <= 50:
            ratios = [0.0, 0.25, 0.5, 0.75, 1.0]
        else:
            ratios = [0.0, 0.25, 0.5, 0.75, 1.0]

        ratio_points = [(x_ratio, y_ratio) for x_ratio in ratios for y_ratio in ratios]
        ratio_points.sort(key=lambda point: (abs(point[0] - 0.5) + abs(point[1] - 0.5), point[0], point[1]))

        points = [(center_lon, center_lat)]
        for x_ratio, y_ratio in ratio_points:
            points.append(
                (
                    min_lon + (max_lon - min_lon) * x_ratio,
                    min_lat + (max_lat - min_lat) * y_ratio,
                )
            )

        return points

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        timeout = kwargs.pop("timeout", API_TIMEOUT)
        last_error: Optional[Exception] = None

        for attempt in range(2):
            try:
                response = self.session.request(method, url, timeout=timeout, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                logger.warning(
                    "[2GIS] Request failed (%s/2): %s %s - %s",
                    attempt + 1,
                    method,
                    url,
                    exc,
                )

        if last_error:
            raise last_error
        raise RuntimeError(f"2GIS request failed without exception for {url}")

    def _find_card_container(self, link) -> BeautifulSoup:
        candidate = link
        best = link.parent or link

        for _ in range(5):
            candidate = candidate.parent
            if candidate is None:
                break

            firm_links = candidate.select('a[href*="/firm/"]')
            strings = [self._clean_text(item) for item in candidate.stripped_strings]
            strings = [item for item in strings if item]
            if len(firm_links) == 1 and len(strings) >= 4:
                best = candidate
                break

        return best

    def _parse_search_card(self, card, city_name: str) -> Dict:
        strings = [self._clean_text(item) for item in card.stripped_strings]
        strings = [item for item in strings if item]

        if not strings:
            return {}

        name = strings[0]
        rating = self._extract_rating(strings)
        address = self._extract_address(strings, city_name)
        category = self._extract_category(strings, address)
        description = self._extract_description(strings, address, category)

        return {
            "name": name,
            "rating": rating,
            "address": address,
            "category": category,
            "description": description,
        }

    def _fetch_firm_details(self, detail_url: str) -> Dict[str, Optional[str]]:
        try:
            response = self._request("GET", detail_url)
            soup = BeautifulSoup(response.text, "lxml")
        except requests.RequestException as exc:
            logger.warning("[2GIS] Failed to fetch details %s: %s", detail_url, exc)
            return {"phone": None, "email": None, "website": None}

        phone_values = self._dedupe(
            [
                self._normalize_phone((link.get("href") or "").removeprefix("tel:").strip())
                for link in soup.select('a[href^="tel:"]')
            ]
        )

        email_values = self._dedupe(
            [
                (link.get("href") or "").removeprefix("mailto:").strip()
                for link in soup.select('a[href^="mailto:"]')
            ]
        )

        external_links = []
        for link in soup.select('a[href^="http"]'):
            href = (link.get("href") or "").strip()
            if href and "2gis." not in href:
                external_links.append(href)

        external_links = self._dedupe(external_links)
        whatsapp_phones = self._extract_whatsapp_phones(external_links)
        website_links = self._pick_website_links(external_links)

        phone = self._format_phone_contacts(phone_values, whatsapp_phones)
        email = self._join_limited(email_values)
        website = self._join_limited(website_links)

        return {
            "phone": phone,
            "email": email,
            "website": website,
        }

    def _extract_firm_id(self, href: str) -> Optional[str]:
        match = re.search(r"/firm/(\d+)", href or "")
        return match.group(1) if match else None

    def _extract_rating(self, strings: List[str]) -> Optional[float]:
        for item in strings[:8]:
            if re.fullmatch(r"[1-5](?:[.,]\d+)?", item):
                try:
                    return float(item.replace(",", "."))
                except ValueError:
                    return None
        return None

    def _extract_address(self, strings: List[str], city_name: str) -> Optional[str]:
        city_name_lower = city_name.lower()

        for item in strings[1:]:
            lower = item.lower()
            if self._is_noise_token(lower):
                continue
            if city_name_lower in lower:
                return item
            if any(hint in lower for hint in ADDRESS_HINTS) and re.search(r"\d", item):
                return item
            if "," in item and re.search(r"\d", item) and len(item) >= 10:
                return item

        return None

    def _extract_category(self, strings: List[str], address: Optional[str]) -> Optional[str]:
        for item in strings[1:5]:
            lower = item.lower()
            if item == address:
                continue
            if self._is_noise_token(lower):
                continue
            if self._looks_like_metadata(item):
                continue
            if len(item) <= 60:
                return item
        return None

    def _extract_description(
        self,
        strings: List[str],
        address: Optional[str],
        category: Optional[str],
    ) -> Optional[str]:
        fragments: List[str] = []

        for item in strings[1:]:
            lower = item.lower()
            if item in {address, category}:
                continue
            if self._is_noise_token(lower):
                continue
            if self._looks_like_metadata(item):
                continue
            if len(item) < 6:
                continue
            fragments.append(item)
            if len(fragments) == 2:
                break

        if fragments:
            return " | ".join(fragments)
        return None

    def _looks_like_metadata(self, item: str) -> bool:
        lower = item.lower()
        return bool(
            re.fullmatch(r"[1-5](?:[.,]\d+)?", item)
            or re.search(r"\bоцен", lower)
            or re.search(r"\bфилиал", lower)
        )

    def _is_noise_token(self, lower: str) -> bool:
        return lower in NOISE_TOKENS

    def _pick_website_links(self, links: List[str]) -> List[str]:
        if not links:
            return []

        primary = []
        socials = []
        for link in links:
            lower = link.lower()
            if any(domain in lower for domain in MESSENGER_DOMAINS):
                continue
            if any(domain in lower for domain in SOCIAL_DOMAINS):
                socials.append(link)
            else:
                primary.append(link)

        return (primary[:2] + socials[:2]) or links[:2]

    def _extract_whatsapp_phones(self, links: List[str]) -> List[str]:
        phones = []
        for link in links:
            lower = link.lower()
            if not any(domain in lower for domain in MESSENGER_DOMAINS):
                continue

            match = re.search(r"wa\.me/(\d+)", link)
            if not match:
                match = re.search(r"phone=(\d+)", link)
            if match:
                phones.append(self._normalize_phone(match.group(1)))

        return self._dedupe(phones)

    def _format_phone_contacts(self, phones: List[str], whatsapp_phones: List[str]) -> Optional[str]:
        values = list(phones)
        for phone in whatsapp_phones:
            if phone and phone not in values:
                values.append(f"WhatsApp: {phone}")
        return self._join_limited(values, limit_chars=120)

    def _normalize_phone(self, value: str) -> str:
        value = value.strip()
        if not value:
            return ""

        digits = re.sub(r"[^\d+]", "", value)
        if digits.startswith("8") and len(digits) == 11:
            return "+7" + digits[1:]
        if digits.startswith("7") and not digits.startswith("+") and len(digits) == 11:
            return "+" + digits
        return digits

    def _join_limited(self, values: List[str], limit_chars: int = 250) -> Optional[str]:
        unique_values = self._dedupe(values)
        if not unique_values:
            return None

        result = []
        total = 0
        for value in unique_values:
            if not value:
                continue
            extra = len(value) if not result else len(value) + 3
            if result and total + extra > limit_chars:
                break
            result.append(value)
            total += extra

        return " | ".join(result) if result else None

    def _dedupe(self, values: List[str]) -> List[str]:
        seen = set()
        result = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _clean_text(self, value: str) -> str:
        return " ".join(value.replace("\u200b", " ").split()).strip()

    def _generate_demo_results(self, query: str, city: str, limit: int) -> List[Dict]:
        city_name = get_region_name(city)
        fallback = [
            {
                "name": f"{query.title()} Demo",
                "phone": None,
                "email": None,
                "website": None,
                "address": city_name,
                "city": city_name,
                "rating": None,
                "source_id": f"2gis_demo_{city}_{quote(query)}",
                "source": "2gis",
                "source_url": None,
                "description": "Демо-режим включён вручную через ENABLE_DEMO_FALLBACK",
                "category": query,
            }
        ]
        return fallback[:limit]
