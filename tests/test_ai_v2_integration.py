from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.application import AiV2Application
from creative_studio.ai_v2.fakes import DeterministicImageModel, DeterministicTextModel, image_artifact
from creative_studio.ai_v2.http_api import AiV2HttpApi
from creative_studio.ai_v2.model_ports import ImageSessionCursor, ImageSubmission
from creative_studio.ai_v2.store import SqliteAiV2Store


class AiV2IntegrationTests(unittest.TestCase):
    def test_text_to_public_dto_and_images_keep_legacy_tables_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "db.sqlite"
            store = SqliteAiV2Store(db)
            try:
                text = json.dumps({"schema_version": "static-text-v1", "items": [{"title": str(i), "core_idea": "c", "ad_copy": "a", "image_description": "d", "content_extensions": ["e"], "reference_sources": [{"name": "r", "note": "n"}], "execution": {"image_prompt": "p"}} for i in range(3)]})
                image = DeterministicImageModel(start_submissions={"v2-run-1-scheme-1:frame:1": ImageSubmission("success", "job", ImageSessionCursor("fake", "c", "m", 1), image_artifact(b"x", "image/png"), None)})
                api = AiV2HttpApi(AiV2Application(store, text_model=DeterministicTextModel([text]), image_model=image))
                _, run = api.dispatch("POST", "/api/v2/projects/1/generate", {"task_description": "x", "aspect_ratio": "16:9", "creative_tags": {}})
                _, status = api.dispatch("POST", f"/api/v2/schemes/{run['items'][0]['scheme_id']}/image", {})
                self.assertEqual(status["status"], "success")
                check_db = sqlite3.connect(db)
                try:
                    names = {row[0] for row in check_db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                finally:
                    check_db.close()
                self.assertFalse({"generations", "visual_items", "adoptions"} & names)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
