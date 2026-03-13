import importlib
import sys
import unittest
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from api_common.request_logging import AdminRequestLoggingRoute, MiniProgramRequestLoggingRoute


class TestRequestLoggingRoute(unittest.TestCase):
    def test_admin_route_logs_success(self) -> None:
        app = FastAPI()
        router = APIRouter(route_class=AdminRequestLoggingRoute)

        @router.get("/ping")
        async def ping() -> dict:
            return {"ok": True}

        app.include_router(router)
        client = TestClient(app)

        with self.assertLogs("api.request.admin", level="INFO") as logs:
            response = client.get("/ping", headers={"x-request-id": "req-admin-1"})

        self.assertEqual(response.status_code, 200)
        output = "\n".join(logs.output)
        self.assertIn("http_request", output)
        self.assertIn("channel=admin", output)
        self.assertIn("method=GET", output)
        self.assertIn("path=/ping", output)
        self.assertIn("status_code=200", output)
        self.assertIn("request_id=req-admin-1", output)

    def test_miniprogram_route_logs_exception(self) -> None:
        app = FastAPI()
        router = APIRouter(route_class=MiniProgramRequestLoggingRoute)

        @router.get("/boom")
        async def boom() -> dict:
            raise RuntimeError("boom")

        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        with self.assertLogs("api.request.miniprogram", level="ERROR") as logs:
            response = client.get("/boom")

        self.assertEqual(response.status_code, 500)
        output = "\n".join(logs.output)
        self.assertIn("http_request_failed", output)
        self.assertIn("channel=miniprogram", output)
        self.assertIn("method=GET", output)
        self.assertIn("path=/boom", output)


class TestDomainRoutersUseLoggingRoute(unittest.TestCase):
    def test_admin_routers_use_admin_logging_route(self) -> None:
        modules = [
            "admin.api.rest.v1.chat",
            "admin.api.rest.v1.chat_stream",
            "admin.api.rest.v1.clear",
            "admin.api.rest.v1.conversations",
            "admin.api.rest.v1.debug",
            "admin.api.rest.v1.examples",
            "admin.api.rest.v1.feedback",
            "admin.api.rest.v1.knowledge_graph",
            "admin.api.rest.v1.memory",
            "admin.api.rest.v1.messages",
            "admin.api.rest.v1.source",
        ]
        for module_name in modules:
            module = importlib.import_module(module_name)
            self.assertIs(module.router.route_class, AdminRequestLoggingRoute, module_name)

    def test_miniprogram_routers_use_miniprogram_logging_route(self) -> None:
        modules = [
            "miniprogram.api.rest.v1.mp_chat_stream",
            "miniprogram.api.rest.v1.mp_feedback",
            "miniprogram.api.rest.v1.mp_movies",
        ]
        for module_name in modules:
            module = importlib.import_module(module_name)
            self.assertIs(module.router.route_class, MiniProgramRequestLoggingRoute, module_name)


if __name__ == "__main__":
    unittest.main()
