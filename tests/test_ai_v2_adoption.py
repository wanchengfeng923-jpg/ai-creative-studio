from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.application import AiV2Application
from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel
from creative_studio.ai_v2.http_api import AiV2HttpApi
from creative_studio.ai_v2.store import SqliteAiV2Store


class AiV2AdoptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SqliteAiV2Store(Path(self.temp_dir.name) / "db.sqlite")
        self.store.connection.execute("CREATE TABLE adoptions (project_id INTEGER PRIMARY KEY)")
        result = json.dumps({
            "schema_version": "static-text-v1",
            "items": [{"title": str(i), "core_idea": "c", "ad_copy": "a", "image_description": "d", "execution": {"image_prompt": "p"}} for i in range(3)],
        })
        self.application = AiV2Application(
            self.store,
            text_model=DeterministicTextModel([result]),
            image_model=DeterministicImageModel(),
            project_provider=lambda project_id: {"id": project_id, "script_type": "展示类"},
        )
        self.api = AiV2HttpApi(self.application)

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_adoption_is_v2_public_snapshot_and_idempotent(self) -> None:
        body = {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": {}}
        _, run = self.api.dispatch("POST", "/api/v2/projects/1/generate", body)
        scheme_id = run["items"][0]["scheme_id"]
        status, adopted = self.api.dispatch("POST", "/api/v2/projects/1/adopt", {"scheme_id": scheme_id})
        self.assertEqual(status, 200)
        self.assertEqual(adopted["scheme_id"], scheme_id)
        encoded = json.dumps(adopted, ensure_ascii=False)
        self.assertNotIn("execution", encoded)
        self.assertNotIn("prompt", encoded)
        status, again = self.api.dispatch("POST", "/api/v2/projects/1/adopt", {"scheme_id": scheme_id})
        self.assertEqual(status, 200)
        self.assertEqual(again, adopted)
        status, current = self.api.dispatch("GET", "/api/v2/projects/1/adoption", None)
        self.assertEqual(status, 200)
        self.assertEqual(current, adopted)
        self.assertEqual(self.store.connection.execute("SELECT COUNT(*) FROM adoptions").fetchone()[0], 0)

    def test_adoption_rejects_foreign_scheme(self) -> None:
        status, payload = self.api.dispatch("POST", "/api/v2/projects/1/adopt", {"scheme_id": 999})
        self.assertEqual(status, 404)
        self.assertEqual(payload["error_code"], "scheme_not_found")
