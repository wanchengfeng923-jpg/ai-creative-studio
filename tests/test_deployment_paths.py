import os
import tempfile
import unittest
from pathlib import Path

from creative_studio.app import create_application


class DeploymentPathTests(unittest.TestCase):
    def test_data_root_environment_is_used_by_composition_root(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("CREATIVE_STUDIO_DATA_DIR")
            os.environ["CREATIVE_STUDIO_DATA_DIR"] = directory
            try:
                application = create_application()
            finally:
                if previous is None:
                    os.environ.pop("CREATIVE_STUDIO_DATA_DIR", None)
                else:
                    os.environ["CREATIVE_STUDIO_DATA_DIR"] = previous

            root = Path(directory).resolve()
            self.assertEqual(application.repository.database_path, root / "creative_studio.db")
            self.assertEqual(application.uploads_dir, root / "uploads")


if __name__ == "__main__":
    unittest.main()
