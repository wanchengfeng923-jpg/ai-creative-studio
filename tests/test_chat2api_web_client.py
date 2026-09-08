from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path


CHAT2API = Path(__file__).resolve().parents[1] / "chat2api"
if str(CHAT2API) not in sys.path:
    sys.path.insert(0, str(CHAT2API))

from web_client import WebImageClient  # noqa: E402


class _BootstrapSession:
    async def get(self, *_args, **_kwargs):
        raise OSError("proxy closed connection")


class Chat2ApiWebClientTests(unittest.TestCase):
    def test_bootstrap_failure_does_not_block_image_session_setup(self) -> None:
        client = WebImageClient("token", base_url="https://chatgpt.com")

        asyncio.run(client._bootstrap(_BootstrapSession()))

    def test_continuation_excludes_assets_already_in_conversation(self) -> None:
        client = WebImageClient("token", base_url="https://chatgpt.com")

        self.assertEqual(
            client._exclude_existing(["old", "new", "new"], {"old"}),
            ["new", "new"],
        )


if __name__ == "__main__":
    unittest.main()
