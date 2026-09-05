from __future__ import annotations

import unittest

from creative_studio.project_projection import ProjectProjection


class ProjectProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.projection = ProjectProjection()

    def test_project_whitelists_fields_and_hides_file_storage_details(self) -> None:
        public = self.projection.project(
            {
                "id": 7,
                "owner_user_id": 3,
                "name": "项目",
                "script_type": "展示类",
                "task_type": "宣传",
                "task_description": "展示玩法",
                "aspect_ratio": "16:9",
                "product_evidence_summary": "摘要",
                "created_at": "2026-09-05 10:00:00",
                "updated_at": "2026-09-05 11:00:00",
                "creative_tags": {
                    "target_audiences": ["玩家"],
                    "unknown": ["private"],
                },
                "reference_files": [
                    {
                        "id": 11,
                        "original_name": "../brief.txt",
                        "stored_name": "secret.bin",
                        "size_bytes": 12,
                        "sha256": "a" * 64,
                        "mime_type": "text/plain",
                        "extraction_status": "complete",
                        "safe_summary": "private summary",
                        "created_at": "2026-09-05 10:30:00",
                    }
                ],
                "adoption": {"reference_id": "legacy"},
                "private": "secret",
            }
        )

        self.assertEqual(public["id"], 7)
        self.assertEqual(public["creative_tags"], {"target_audiences": ["玩家"]})
        self.assertEqual(public["reference_files"][0]["original_name"], "brief.txt")
        self.assertNotIn("stored_name", public["reference_files"][0])
        self.assertNotIn("safe_summary", public["reference_files"][0])
        self.assertNotIn("private", public)
        self.assertIsNone(public["adoption"])

    def test_project_preserves_valid_carousel_rounds_only(self) -> None:
        public = self.projection.project(
            {
                "creative_tags": {
                    "visual_carousel_rounds": [
                        {
                            "index": 1,
                            "mode": "base",
                            "overrides": {
                                "visual_product_selling_points": ["卖点"],
                                "unknown": ["private"],
                            },
                        },
                        {"index": 0, "mode": "invalid", "overrides": {}},
                    ]
                }
            }
        )

        self.assertEqual(
            public["creative_tags"]["visual_carousel_rounds"],
            [
                {
                    "index": 1,
                    "mode": "base",
                    "overrides": {"visual_product_selling_points": ["卖点"]},
                }
            ],
        )

    def test_summary_exposes_only_project_list_fields(self) -> None:
        public = self.projection.summary(
            {
                "id": 7,
                "owner_user_id": 3,
                "name": "项目",
                "script_type": "展示类",
                "updated_at": "2026-09-05 11:00:00",
                "adopted_kind": "",
                "adopted_title": "",
                "task_description": "private from list",
            }
        )

        self.assertEqual(
            public,
            {
                "id": 7,
                "owner_user_id": 3,
                "name": "项目",
                "script_type": "展示类",
                "updated_at": "2026-09-05 11:00:00",
                "adopted_kind": "",
                "adopted_title": "",
            },
        )


if __name__ == "__main__":
    unittest.main()
