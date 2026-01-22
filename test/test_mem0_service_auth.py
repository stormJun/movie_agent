import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


class TestMem0ServiceAuth(unittest.TestCase):
    def test_resolve_user_id_prefers_trusted_request_user_id(self) -> None:
        from server.mem0_service import auth

        with patch.object(auth, "MEM0_TRUST_REQUEST_USER_ID", True), patch.object(auth, "MEM0_AUTH_MODE", "api_key"):
            uid = auth.resolve_user_id(
                authorization=None,
                header_user_id=None,
                request_user_id="u1",
            )
        self.assertEqual(uid, "u1")

    def test_resolve_user_id_uses_header_when_not_trusting_body(self) -> None:
        from server.mem0_service import auth

        with patch.object(auth, "MEM0_TRUST_REQUEST_USER_ID", False), patch.object(auth, "MEM0_AUTH_MODE", "api_key"):
            uid = auth.resolve_user_id(
                authorization=None,
                header_user_id="u2",
                request_user_id=None,
            )
        self.assertEqual(uid, "u2")

    def test_resolve_user_id_jwt_claims(self) -> None:
        from server.mem0_service import auth

        with (
            patch.object(auth, "MEM0_TRUST_REQUEST_USER_ID", False),
            patch.object(auth, "MEM0_AUTH_MODE", "jwt"),
            patch.object(auth, "_bearer_token", return_value="jwt-token"),
            patch.object(auth, "_decode_jwt", return_value={"sub": "u3"}),
        ):
            uid = auth.resolve_user_id(
                authorization="Bearer jwt-token",
                header_user_id=None,
                request_user_id=None,
            )
        self.assertEqual(uid, "u3")

    def test_require_auth_accepts_api_key(self) -> None:
        from server.mem0_service import auth

        with patch.object(auth, "MEM0_API_KEY", "k1"), patch.object(auth, "MEM0_JWT_SECRET", ""), patch.object(
            auth, "MEM0_AUTH_MODE", "api_key"
        ):
            auth.require_auth(authorization="Bearer k1")

    def test_compute_ttl_defaults(self) -> None:
        from server.mem0_service.storage_postgres import PostgresMemoryStore

        self.assertEqual(PostgresMemoryStore._compute_ttl(tags=["preference"]), 90)
        self.assertEqual(PostgresMemoryStore._compute_ttl(tags=["constraint"]), 180)
        self.assertEqual(PostgresMemoryStore._compute_ttl(tags=["fact"]), 365)
        self.assertIsNone(PostgresMemoryStore._compute_ttl(tags=["identity"]))
