import unittest
from unittest import mock

from parsers.gis2 import Parser2GIS
from parsers.kaspi import ParserKaspi


class Parser2GISTestCase(unittest.TestCase):
    def test_probe_urls_expand_for_higher_limit(self):
        parser = Parser2GIS()
        search_context = {
            "lon1": 76.7,
            "lat1": 43.3,
            "lon2": 77.0,
            "lat2": 43.1,
            "center_lon": 76.85,
            "center_lat": 43.2,
            "zoom": 11.6,
        }

        small = parser._build_probe_urls("https://2gis.kz/almaty/search/test", search_context, limit=20)
        medium = parser._build_probe_urls("https://2gis.kz/almaty/search/test", search_context, limit=50)
        large = parser._build_probe_urls("https://2gis.kz/almaty/search/test", search_context, limit=100)

        self.assertGreater(len(medium), len(small))
        self.assertGreater(len(large), len(medium))

    def test_extract_search_context_parses_drag_bounds(self):
        parser = Parser2GIS()
        html = (
            '"viewpoint":[{"lon":76.7,"lat":43.3},{"lon":77.0,"lat":43.1}],'
            '"center":{"lon":76.85,"lat":43.2},"zoom":11.6,'
            '"drag_bound":[{"latitude":43.54,"longitude":76.44},'
            '{"latitude":42.89,"longitude":76.44},'
            '{"latitude":42.89,"longitude":77.33},'
            '{"latitude":43.54,"longitude":77.33}],"external_source":0'
        )

        context = parser._extract_search_context(html)

        self.assertEqual(context["drag_min_lon"], 76.44)
        self.assertEqual(context["drag_max_lon"], 77.33)
        self.assertEqual(context["drag_min_lat"], 42.89)
        self.assertEqual(context["drag_max_lat"], 43.54)


class ParserKaspiTestCase(unittest.TestCase):
    def test_resolve_city_returns_none_for_unsupported_region(self):
        parser = ParserKaspi()
        with mock.patch.object(
            parser,
            "_get_cities_by_code",
            return_value={
                "almaty": {"code": "almaty", "id": 750000000, "name": "Алматы"},
                "nur-sultan": {"code": "nur-sultan", "id": 710000000, "name": "Астана"},
            },
        ):
            self.assertIsNone(parser._resolve_city("moscow"))
            self.assertEqual(parser._resolve_city("nur_sultan")["code"], "nur-sultan")

    def test_extract_merchant_profile_reads_phone_from_backend_payload(self):
        parser = ParserKaspi()
        html = (
            '<script>BACKEND.components.merchant = '
            '{"uid":"Sulpak","name":"Sulpak","phone":"+7 (707) 700-32-10"};'
            "</script>"
        )

        profile = parser._extract_merchant_profile(html)

        self.assertEqual(profile["merchant_id"], "Sulpak")
        self.assertEqual(profile["name"], "Sulpak")
        self.assertEqual(profile["phone"], "+7 (707) 700-32-10")

    def test_build_merchant_url_includes_merchant_and_product(self):
        parser = ParserKaspi()

        url = parser._build_merchant_url("Sulpak", product_code="107451877")

        self.assertIn("/shop/info/merchant/Sulpak/address-tab/", url)
        self.assertIn("merchantId=Sulpak", url)
        self.assertIn("productCode=107451877", url)
        self.assertIn("tabId=PRODUCT", url)


if __name__ == "__main__":
    unittest.main()
