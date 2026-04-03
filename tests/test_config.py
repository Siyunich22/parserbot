import unittest

from config import normalize_database_url


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


if __name__ == "__main__":
    unittest.main()
