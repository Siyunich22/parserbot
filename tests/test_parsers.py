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


if __name__ == "__main__":
    unittest.main()
