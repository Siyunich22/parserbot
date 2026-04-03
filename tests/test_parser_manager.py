import importlib
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock


PROJECT_MODULES = [
    "config",
    "database",
    "cache",
    "parsers.gis2",
    "parsers.kaspi",
    "parser_manager",
]


def reload_project_modules(database_url: str, cache_dir: str):
    os.environ["DATABASE_URL"] = database_url
    os.environ["TELEGRAM_BOT_TOKEN"] = "test-token"
    os.environ["CACHE_DIR"] = cache_dir
    os.environ["ENABLE_DEMO_FALLBACK"] = "false"

    for module_name in PROJECT_MODULES:
        sys.modules.pop(module_name, None)

    config = importlib.import_module("config")
    database = importlib.import_module("database")
    parser_manager = importlib.import_module("parser_manager")
    return config, database, parser_manager


class ParserManagerTestCase(unittest.TestCase):
    def setUp(self):
        cache_root = Path.cwd() / "data"
        cache_root.mkdir(exist_ok=True)
        self.cache_dir = cache_root / f"parser-cache-{uuid.uuid4().hex}"
        self.cache_dir.mkdir()
        _, database, parser_manager_module = reload_project_modules(
            "sqlite:///:memory:",
            self.cache_dir.as_posix(),
        )
        self.database = database
        self.parser_manager_module = parser_manager_module
        self.manager = parser_manager_module.ParserManager()
        self.db = database.SessionLocal()

    def tearDown(self):
        self.db.close()
        self.database.engine.dispose()
        if self.cache_dir.exists():
            for path in self.cache_dir.glob("*"):
                if path.is_file():
                    path.unlink()
            self.cache_dir.rmdir()

    def sample_2gis_results(self):
        return [
            {
                "name": "Vilka",
                "phone": "+77073394049",
                "email": "vilkagrill@mail.ru",
                "website": "https://instagram.com/vilka.cafe",
                "address": "8-й микрорайон, 4Б, Алматы",
                "city": "Алматы",
                "rating": 4.6,
                "source_id": "2gis_70000001053127916",
                "source": "2gis",
                "source_url": "https://2gis.kz/almaty/firm/70000001053127916",
                "description": "Кафе · Европейская кухня",
                "category": "Стейк-хаус",
            }
        ]

    def sample_kaspi_results(self):
        return [
            {
                "name": "Sulpak",
                "phone": None,
                "email": None,
                "website": None,
                "address": None,
                "city": "Астана",
                "rating": 4.9,
                "source_id": "kaspi_merchant_sulpak_710000000",
                "source": "kaspi",
                "source_url": "https://kaspi.kz/p/apple-iphone-17-pro-256gb-nanosim-esim-oranzhevyi-145467625/?c=710000000",
                "description": "Товар: Apple iPhone 17 Pro | Цена: 852 990 ₸",
                "category": "Смартфоны",
            }
        ]

    def test_parse_links_results_to_session(self):
        with mock.patch.object(
            self.manager.parser_2gis,
            "search",
            return_value=self.sample_2gis_results(),
        ):
            parse_session = self.manager.parse(
                db=self.db,
                query="кафе",
                source="2gis",
                city="almaty",
                user_id=101,
                limit=5,
            )

        results = self.manager.get_session_results(self.db, parse_session.id)

        self.assertEqual(parse_session.status, "completed")
        self.assertEqual(parse_session.region, "Алматы")
        self.assertEqual(parse_session.results_count, len(results))
        self.assertGreater(len(results), 0)
        self.assertTrue(all(company.city == "Алматы" for company in results))

    def test_get_latest_session_is_user_specific(self):
        with mock.patch.object(
            self.manager.parser_2gis,
            "search",
            return_value=self.sample_2gis_results(),
        ):
            self.manager.parse(
                db=self.db,
                query="кафе",
                source="2gis",
                city="almaty",
                user_id=1,
                limit=3,
            )

        with mock.patch.object(
            self.manager.parser_kaspi,
            "search",
            return_value=self.sample_kaspi_results(),
        ):
            latest_user_two = self.manager.parse(
                db=self.db,
                query="электроника",
                source="kaspi",
                city="nur_sultan",
                user_id=2,
                limit=4,
            )

        latest = self.manager.get_latest_session(self.db, 2)
        results = self.manager.get_session_results(self.db, latest.id)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.id, latest_user_two.id)
        self.assertEqual(latest.region, "Астана")
        self.assertEqual(latest.results_count, len(results))
        self.assertGreater(len(results), 0)


if __name__ == "__main__":
    unittest.main()
