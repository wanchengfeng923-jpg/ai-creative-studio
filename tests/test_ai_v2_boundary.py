from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import os
import subprocess
import sys

from creative_studio.ai_v2.boundary import AiV2BoundaryViolation, assert_ai_v2_boundary


class AiV2BoundaryTests(unittest.TestCase):
    def test_importing_v2_does_not_load_legacy_ai_modules(self) -> None:
        source_root = Path(__file__).resolve().parents[1] / "src"
        script = (
            "import sys\n"
            "import creative_studio.ai_v2.input_contract\n"
            "legacy = {'creative_studio.ai_creative', 'creative_studio.model_client', "
            "'creative_studio.prompt_registry', 'creative_studio.generation_service'}\n"
            "loaded = sorted(legacy.intersection(sys.modules))\n"
            "if loaded:\n"
            "    raise SystemExit(','.join(loaded))\n"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(source_root)
        result = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

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

    def test_allows_v2_adoption_table_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "src" / "creative_studio" / "ai_v2"
            source_dir.mkdir(parents=True)
            (source_dir / "store.py").write_text("TABLE = 'ai_v2_adoptions'", encoding="utf-8")
            assert_ai_v2_boundary(root)


if __name__ == "__main__":
    unittest.main()
