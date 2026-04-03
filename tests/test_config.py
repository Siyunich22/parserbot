import unittest
from unittest import mock

from config import (
    GIS2_SUPPORTED_REGIONS,
    build_database_url_from_pg_env,
    detect_database_url_source,
    KASPI_SUPPORTED_REGIONS,
    normalize_database_url,
    resolve_database_url,
)


class ConfigTestCase(unittest.TestCase):
    def test_normalize_postgres_url(self):
        self.assertEqual(
            normalize_database_url("postgres://user:pass@host:5432/dbname"),
            "postgresql+psycopg://user:pass@host:5432/dbname",
        )

    def test_normalize_postgresql_url(self):
        self.assertEqual(
            normalize_database_url("postgresql://user:pass@host:5432/dbname"),
            "postgresql+psycopg://user:pass@host:5432/dbname",
        )

    def test_keep_sqlite_url(self):
        self.assertEqual(
            normalize_database_url("sqlite:///./parser_data.db"),
            "sqlite:///./parser_data.db",
        )

    def test_keep_psycopg_url(self):
        self.assertEqual(
            normalize_database_url("postgresql+psycopg://user:pass@host:5432/dbname"),
            "postgresql+psycopg://user:pass@host:5432/dbname",
        )

    def test_build_database_url_from_pg_env(self):
        with mock.patch.dict(
            "os.environ",
            {
                "PGHOST": "junction.proxy.rlwy.net",
                "PGPORT": "5432",
                "PGUSER": "postgres",
                "PGPASSWORD": "secret",
                "PGDATABASE": "railway",
                "PGSSLMODE": "require",
            },
            clear=False,
        ):
            self.assertEqual(
                build_database_url_from_pg_env(),
                "postgresql+psycopg://postgres:secret@junction.proxy.rlwy.net:5432/railway?sslmode=require",
            )

    def test_resolve_database_url_from_pg_env_when_database_url_is_invalid(self):
        with mock.patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "junction.proxy.rlwy.net",
                "PGHOST": "junction.proxy.rlwy.net",
                "PGPORT": "5432",
                "PGUSER": "postgres",
                "PGPASSWORD": "secret",
                "PGDATABASE": "railway",
                "PGSSLMODE": "require",
            },
            clear=False,
        ):
            self.assertEqual(
                resolve_database_url("sqlite:///fallback.db"),
                "postgresql+psycopg://postgres:secret@junction.proxy.rlwy.net:5432/railway?sslmode=require",
            )

    def test_detect_database_url_source_prefers_pg_env_when_database_url_invalid(self):
        with mock.patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "junction.proxy.rlwy.net",
                "PGHOST": "junction.proxy.rlwy.net",
                "PGPORT": "5432",
                "PGUSER": "postgres",
                "PGPASSWORD": "secret",
                "PGDATABASE": "railway",
            },
            clear=False,
        ):
            self.assertEqual(
                detect_database_url_source("sqlite:///fallback.db"),
                "PG_ENV",
            )

    def test_supported_regions_are_kazakhstan_only(self):
        self.assertEqual(GIS2_SUPPORTED_REGIONS, KASPI_SUPPORTED_REGIONS)
        self.assertNotIn("moscow", GIS2_SUPPORTED_REGIONS)
        self.assertNotIn("spb", GIS2_SUPPORTED_REGIONS)


if __name__ == "__main__":
    unittest.main()
