import unittest
from datetime import datetime, timedelta


class TestDebugDataCache(unittest.TestCase):
    def test_lru_eviction(self) -> None:
        from infrastructure.debug.debug_cache import DebugDataCache
        from infrastructure.debug.debug_collector import DebugDataCollector

        cache = DebugDataCache(ttl_minutes=30, max_size=2)

        c1 = DebugDataCollector("r1", "u", "s")
        c2 = DebugDataCollector("r2", "u", "s")
        c3 = DebugDataCollector("r3", "u", "s")

        cache.set("r1", c1)
        cache.set("r2", c2)
        cache.set("r3", c3)  # evict r1

        self.assertIsNone(cache.get("r1"))
        self.assertIsNotNone(cache.get("r2"))
        self.assertIsNotNone(cache.get("r3"))

    def test_ttl_expiration(self) -> None:
        from infrastructure.debug.debug_cache import DebugDataCache
        from infrastructure.debug.debug_collector import DebugDataCollector

        cache = DebugDataCache(ttl_minutes=1, max_size=10)
        c1 = DebugDataCollector("r1", "u", "s")
        # Make it appear expired.
        c1.timestamp = datetime.now() - timedelta(minutes=5)
        cache.set("r1", c1)

        self.assertIsNone(cache.get("r1"))


if __name__ == "__main__":
    unittest.main()

