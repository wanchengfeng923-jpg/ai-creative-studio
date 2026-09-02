from __future__ import annotations

import sys
import unittest
from pathlib import Path


CHAT2API = Path(__file__).resolve().parents[1] / "chat2api"
if str(CHAT2API) not in sys.path:
    sys.path.insert(0, str(CHAT2API))

from auth_refresh import _apply_set_cookie_rotation, _session_cookie_header


class AuthRefreshCookieTests(unittest.TestCase):
    def test_session_cookie_prefers_chunks_over_legacy_value(self) -> None:
        cookie = "; ".join(
            [
                "__Secure-next-auth.session-token=legacy-value",
                "__Secure-next-auth.session-token.0=chunk-zero",
                "__Secure-next-auth.session-token.1=chunk-one",
                "other=value",
            ]
        )

        normalized = _session_cookie_header(cookie)

        self.assertNotIn("__Secure-next-auth.session-token=legacy-value", normalized)
        self.assertIn("__Secure-next-auth.session-token.0=chunk-zero", normalized)
        self.assertIn("__Secure-next-auth.session-token.1=chunk-one", normalized)
        self.assertIn("other=value", normalized)

    def test_cookie_rotation_keeps_chunk_precedence(self) -> None:
        rotated = _apply_set_cookie_rotation(
            "__Secure-next-auth.session-token.0=old-zero; __Secure-next-auth.session-token.1=old-one",
            [
                "__Secure-next-auth.session-token=legacy-value; Path=/",
                "__Secure-next-auth.session-token.0=new-zero; Path=/",
                "__Secure-next-auth.session-token.1=new-one; Path=/",
            ],
        )

        self.assertNotIn("__Secure-next-auth.session-token=legacy-value", rotated)
        self.assertIn("__Secure-next-auth.session-token.0=new-zero", rotated)
        self.assertIn("__Secure-next-auth.session-token.1=new-one", rotated)


if __name__ == "__main__":
    unittest.main()
