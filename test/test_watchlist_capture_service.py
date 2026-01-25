import sys
import unittest
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from application.chat.watchlist_capture_service import WatchlistCaptureService


class _StubWatchlistStore:
    def __init__(self) -> None:
        self.items: list[dict] = []

    async def list_items(self, *, user_id: str, limit: int = 50, offset: int = 0):
        _ = (limit, offset)
        return [
            type("Item", (), {"title": it["title"]})  # minimal duck-typing
            for it in self.items
            if it["user_id"] == user_id
        ]

    async def count_items(self, *, user_id: str) -> int:
        return len([it for it in self.items if it["user_id"] == user_id])

    async def add_item(self, *, user_id: str, title: str, year=None, metadata=None):
        from uuid import uuid4
        from datetime import datetime, timezone

        _ = metadata
        item = type(
            "WatchItem",
            (),
            {
                "id": uuid4(),
                "user_id": user_id,
                "title": title,
                "year": year,
                "created_at": datetime.now(timezone.utc),
            },
        )()
        self.items.append({"user_id": user_id, "title": title, "year": year})
        return item

    async def delete_item(self, *, user_id: str, item_id):
        raise NotImplementedError

    async def close(self) -> None:
        return None


class TestWatchlistCaptureService(unittest.IsolatedAsyncioTestCase):
    async def test_capture_recommendations_adds_titles(self):
        store = _StubWatchlistStore()
        svc = WatchlistCaptureService(store=store, enabled=True, max_items_per_turn=5)

        user = "u1"
        user_msg = "我喜欢看科幻片，有什么推荐？"
        assistant_msg = "- 《星际穿越》(2014)\n- 《盗梦空间》\n- 《银翼杀手》"

        res = await svc.maybe_capture(user_id=user, user_message=user_msg, assistant_message=assistant_msg)
        self.assertGreaterEqual(len(res.added), 2)
        titles = {x["title"] for x in store.items if x["user_id"] == user}
        self.assertIn("星际穿越", titles)
        self.assertIn("盗梦空间", titles)

    async def test_capture_parses_year_from_brackets(self):
        store = _StubWatchlistStore()
        svc = WatchlistCaptureService(store=store, enabled=True, max_items_per_turn=5)

        user = "u1"
        user_msg = "推荐几部科幻片？"
        assistant_msg = "- 《星际穿越》(2014)\n- 《盗梦空间》（2010）"
        await svc.maybe_capture(user_id=user, user_message=user_msg, assistant_message=assistant_msg)
        by_title = {x["title"]: x.get("year") for x in store.items if x["user_id"] == user}
        self.assertEqual(by_title.get("星际穿越"), 2014)
        self.assertEqual(by_title.get("盗梦空间"), 2010)

    async def test_no_capture_when_no_intent(self):
        store = _StubWatchlistStore()
        svc = WatchlistCaptureService(store=store, enabled=True, max_items_per_turn=5)

        res = await svc.maybe_capture(
            user_id="u1",
            user_message="你好",
            assistant_message="你好，有什么可以帮你？",
        )
        self.assertEqual(res.added, [])
        self.assertEqual(store.items, [])

    async def test_no_capture_for_movie_qa(self):
        store = _StubWatchlistStore()
        svc = WatchlistCaptureService(store=store, enabled=True, max_items_per_turn=5)

        res = await svc.maybe_capture(
            user_id="u1",
            user_message="《喜宴》导演是谁？",
            assistant_message="《喜宴》导演是李安。",
        )
        self.assertEqual(res.added, [])
        self.assertEqual(store.items, [])

    async def test_explicit_add_only_parses_user_message(self):
        store = _StubWatchlistStore()
        svc = WatchlistCaptureService(store=store, enabled=True, max_items_per_turn=5)

        res = await svc.maybe_capture(
            user_id="u1",
            user_message="把《盗梦空间》加入想看清单",
            assistant_message="- 《星际穿越》\n- 《银翼杀手》",
        )
        titles = {x["title"] for x in store.items if x["user_id"] == "u1"}
        self.assertEqual(titles, {"盗梦空间"})
