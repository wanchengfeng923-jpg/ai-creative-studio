from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creative_studio.ai_v2.boundary import AiV2BoundaryViolation, assert_ai_v2_boundary


class AiV2BoundaryTests(unittest.TestCase):
    def test_rejects_old_ai_imports_routes_and_tables_with_file_details(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "src" / "creative_studio" / "ai_v2"
            source_dir.mkdir(parents=True)
            (source_dir / "bad.py").write_text(
                "from creative_studio.ai_creative import validate_creative_recommendations\n"
                "import generation_service\n"
                "OLD_ROUTE = '/api/projects/1/generate'\n"
                "OLD_TABLE = 'visual_items'\n",
                encoding="utf-8",
            )

            with self.assertRaises(AiV2BoundaryViolation) as context:
                assert_ai_v2_boundary(root)

            message = str(context.exception)
            self.assertIn("bad.py", message)
            self.assertIn("ai_creative", message)
            self.assertIn("generation_service", message)
            self.assertIn("/api/projects/1/generate", message)
            self.assertIn("visual_items", message)

    def test_allows_neutral_dependencies_and_v2_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "src" / "creative_studio" / "ai_v2"
            source_dir.mkdir(parents=True)
            (source_dir / "good.py").write_text(
                "from dataclasses import dataclass\n"
                "import json\n"
                "import sqlite3\n"
                "import requests\n"
                "V2_ROUTE = '/api/v2/projects/1/generate'\n"
                "V2_TABLE = 'ai_v2_runs'\n",
                encoding="utf-8",
            )

            assert_ai_v2_boundary(root)


if __name__ == "__main__":
    unittest.main()
