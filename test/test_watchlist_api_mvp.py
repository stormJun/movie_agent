import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from fastapi.testclient import TestClient

from domain.memory import WatchlistItem
from server.main import app


class _StubWatchlistStore:
    def __init__(self) -> None:
        self._items: list[WatchlistItem] = []

    async def list_items(
        self,
        *,
        user_id: str,
        status: str | None = None,
        query: str | None = None,
        include_deleted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ):
        items = [i for i in self._items if i.user_id == user_id]
        if not include_deleted:
            items = [i for i in items if i.deleted_at is None]
        if status:
            items = [i for i in items if (i.status or "to_watch") == status]
        if query:
            q = str(query).strip().lower()
            if q:
                items = [i for i in items if q in (i.title or "").lower()]
        items.sort(
            key=lambda x: (
                x.updated_at or x.created_at or datetime.min.replace(tzinfo=timezone.utc),
                x.id,
            ),
            reverse=True,
        )
        return items[int(offset) : int(offset) + int(limit)]

    async def count_items(
        self,
        *,
        user_id: str,
        status: str | None = None,
        query: str | None = None,
        include_deleted: bool = False,
    ) -> int:
        items = await self.list_items(
            user_id=user_id,
            status=status,
            query=query,
            include_deleted=include_deleted,
            limit=10000,
            offset=0,
        )
        return len(items)

    async def add_item(self, *, user_id: str, title: str, year=None, metadata=None):
        # mimic store dedupe behavior (same title => return existing)
        title_s = str(title).strip()
        for it in self._items:
            if it.user_id == str(user_id) and it.title.lower() == title_s.lower():
                if it.deleted_at is not None:
                    # Restore on re-add.
                    now = datetime.now(timezone.utc)
                    restored = WatchlistItem(
                        id=it.id,
                        user_id=it.user_id,
                        title=it.title,
                        year=it.year,
                        status="to_watch",
                        metadata=dict(it.metadata or {}),
                        created_at=it.created_at,
                        updated_at=now,
                        deleted_at=None,
                    )
                    self._items = [restored if x.id == it.id else x for x in self._items]
                    return restored
                return it

        now = datetime.now(timezone.utc)
        item = WatchlistItem(
            id=uuid4(),
            user_id=str(user_id),
            title=title_s,
            year=int(year) if year is not None else None,
            status="to_watch",
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        self._items.append(item)
        return item

    async def update_item(self, *, user_id: str, item_id: UUID, title=None, year=None, status=None, metadata=None):
        now = datetime.now(timezone.utc)
        for idx, it in enumerate(self._items):
            if it.user_id == str(user_id) and it.id == item_id and it.deleted_at is None:
                next_title = it.title if title is None else str(title).strip()
                if not next_title:
                    raise ValueError("title is required")
                next_year = it.year if year is None else int(year)
                next_status = it.status if status is None else str(status)
                if next_status not in {"to_watch", "watched", "dismissed"}:
                    raise ValueError("invalid status")
                next_meta = dict(it.metadata or {})
                if metadata:
                    next_meta.update(dict(metadata))
                updated = WatchlistItem(
                    id=it.id,
                    user_id=it.user_id,
                    title=next_title,
                    year=next_year,
                    status=next_status,
                    metadata=next_meta,
                    created_at=it.created_at,
                    updated_at=now,
                    deleted_at=None,
                )
                self._items[idx] = updated
                return updated
        return None

    async def delete_item(self, *, user_id: str, item_id: UUID) -> bool:
        now = datetime.now(timezone.utc)
        changed = False
        out: list[WatchlistItem] = []
        for it in self._items:
            if it.user_id == str(user_id) and it.id == item_id and it.deleted_at is None:
                out.append(
                    WatchlistItem(
                        id=it.id,
                        user_id=it.user_id,
                        title=it.title,
                        year=it.year,
                        status=it.status,
                        metadata=dict(it.metadata or {}),
                        created_at=it.created_at,
                        updated_at=now,
                        deleted_at=now,
                    )
                )
                changed = True
            else:
                out.append(it)
        self._items = out
        return changed

    async def restore_item(self, *, user_id: str, item_id: UUID):
        now = datetime.now(timezone.utc)
        for idx, it in enumerate(self._items):
            if it.user_id == str(user_id) and it.id == item_id and it.deleted_at is not None:
                restored = WatchlistItem(
                    id=it.id,
                    user_id=it.user_id,
                    title=it.title,
                    year=it.year,
                    status="to_watch",
                    metadata=dict(it.metadata or {}),
                    created_at=it.created_at,
                    updated_at=now,
                    deleted_at=None,
                )
                self._items[idx] = restored
                return restored
        return None

    async def dedup_merge(self, *, user_id: str):
        # Keep newest, soft-delete others for exact title matches.
        items = [i for i in self._items if i.user_id == str(user_id)]
        by_title: dict[str, list[WatchlistItem]] = {}
        for it in items:
            by_title.setdefault((it.title or "").strip().lower(), []).append(it)
        kept = deleted = merged = 0
        for _, group in by_title.items():
            group.sort(
                key=lambda x: (
                    x.updated_at or x.created_at or datetime.min.replace(tzinfo=timezone.utc),
                    x.id,
                ),
                reverse=True,
            )
            winner = group[0]
            kept += 1
            for it in group[1:]:
                if it.deleted_at is None:
                    await self.delete_item(user_id=str(user_id), item_id=it.id)
                    deleted += 1
        return {"kept": kept, "deleted": deleted, "merged": merged}

    async def close(self) -> None:
        return None


class TestWatchlistApiMvp(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        from server.api.rest import dependencies as deps

        self.store = _StubWatchlistStore()
        app.dependency_overrides[deps.get_watchlist_store] = lambda: self.store
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides = {}

    async def test_add_list_delete(self):
        # Add
        resp = self.client.post(
            "/api/v1/memory/watchlist",
            json={"user_id": "u1", "title": "Interstellar"},
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["title"], "Interstellar")
        self.assertTrue(body.get("id"))
        self.assertEqual((body.get("metadata") or {}).get("source"), "manual")

        # List
        resp2 = self.client.get("/api/v1/memory/watchlist", params={"user_id": "u1", "limit": 10, "offset": 0})
        self.assertEqual(resp2.status_code, 200, resp2.text)
        items = resp2.json()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Interstellar")
        self.assertEqual((items[0].get("metadata") or {}).get("source"), "manual")

        # Delete
        item_id = body["id"]
        resp3 = self.client.delete(f"/api/v1/memory/watchlist/{item_id}", params={"user_id": "u1"})
        self.assertEqual(resp3.status_code, 204, resp3.text)

        # List again
        resp4 = self.client.get("/api/v1/memory/watchlist", params={"user_id": "u1", "limit": 10, "offset": 0})
        self.assertEqual(resp4.status_code, 200, resp4.text)
        self.assertEqual(resp4.json(), [])

        # List deleted only
        resp5 = self.client.get(
            "/api/v1/memory/watchlist",
            params={"user_id": "u1", "limit": 10, "offset": 0, "only_deleted": True},
        )
        self.assertEqual(resp5.status_code, 200, resp5.text)
        deleted_items = resp5.json()
        self.assertEqual(len(deleted_items), 1)
        self.assertEqual(deleted_items[0]["id"], item_id)

        # Restore
        resp6 = self.client.post(f"/api/v1/memory/watchlist/{item_id}/restore", params={"user_id": "u1"})
        self.assertEqual(resp6.status_code, 200, resp6.text)
        self.assertEqual(resp6.json()["status"], "to_watch")

        # Update status
        resp7 = self.client.patch(
            f"/api/v1/memory/watchlist/{item_id}",
            json={"user_id": "u1", "status": "watched"},
        )
        self.assertEqual(resp7.status_code, 200, resp7.text)
        self.assertEqual(resp7.json()["status"], "watched")

        # Filter by status
        resp8 = self.client.get("/api/v1/memory/watchlist", params={"user_id": "u1", "status": "watched"})
        self.assertEqual(resp8.status_code, 200, resp8.text)
        self.assertEqual(len(resp8.json()), 1)
