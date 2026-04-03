import unittest
import uuid
from pathlib import Path

from cache import SearchCache


class SearchCacheTestCase(unittest.TestCase):
    def test_limit_participates_in_cache_key(self):
        cache_root = Path.cwd() / "data"
        cache_root.mkdir(exist_ok=True)
        cache_dir = cache_root / f"test-cache-{uuid.uuid4().hex}"
        cache_dir.mkdir()

        try:
            cache = SearchCache(cache_dir=str(cache_dir), ttl_hours=1)
            small_results = [{"name": "one"}]
            large_results = [{"name": "one"}, {"name": "two"}]

            cache.set("2gis", "кафе", "almaty", small_results, limit=5)
            cache.set("2gis", "кафе", "almaty", large_results, limit=30)

            self.assertEqual(cache.get("2gis", "кафе", "almaty", limit=5), small_results)
            self.assertEqual(cache.get("2gis", "кафе", "almaty", limit=30), large_results)
        finally:
            for path in cache_dir.glob("*"):
                if path.is_file():
                    path.unlink()
            cache_dir.rmdir()


if __name__ == "__main__":
    unittest.main()
