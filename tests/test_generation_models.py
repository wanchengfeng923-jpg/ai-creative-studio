import unittest
from pathlib import Path
import tempfile

from creative_studio.repository import StudioRepository
from creative_studio.reference_assets import FileReferenceAssetStore

from creative_studio.generation_models import (
    GenerationRun,
    ReferenceAsset,
    ReferenceAssetContent,
    ReferenceAssetError,
)


class GenerationModelTests(unittest.TestCase):
    def test_run_has_independent_mutable_defaults(self):
        first = GenerationRun(1, 2, "visual", 1, "pending", "visual.v1", "fp", "req", {})
        second = GenerationRun(2, 2, "visual", 2, "failed", "visual.v1", "fp2", "req2", {})
        self.assertEqual(first.usage, {})
        self.assertEqual(second.error, {})
        self.assertIsNot(first.usage, second.usage)

    def test_reference_asset_content_is_typed_and_keeps_summary_only(self):
        asset = ReferenceAsset(
            asset_id=7,
            project_id=3,
            original_name="brief.txt",
            sha256="a" * 64,
            mime_type="text/plain",
            size_bytes=12,
            extraction_status="complete",
            safe_summary="受控摘要",
        )
        content = ReferenceAssetContent(asset=asset, text="受控正文", truncated=False)
        self.assertEqual(content.asset.asset_id, 7)
        self.assertNotIn("stored_name", content.asset.__dict__)

    def test_repository_exposes_canonical_run_and_asset_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = StudioRepository(Path(directory) / "studio.db")
            project = repo.create_project("项目", "展示类")
            record = repo.add_project_file(
                project["id"], "brief.txt", "stored.txt", 12,
                sha256="b" * 64, mime_type="text/plain",
                extraction_status="complete", safe_summary="摘要",
            )
            assets = repo.list_reference_assets(project["id"])
            self.assertEqual(assets[0].asset_id, record["id"])
            self.assertEqual(assets[0].safe_summary, "摘要")
            reservation = repo.reserve_run(
                project["id"], "visual", "visual.v1", "fingerprint",
                context={"x": 1, "prompt_id": "visual", "prompt_version": "v1", "model": "fake"}, request_id="req"
            )
            self.assertEqual(repo.get_run(reservation.run_id).request_id, "req")
            self.assertEqual(repo.get_run(reservation.run_id).prompt_id, "visual")
            self.assertEqual(repo.get_run(reservation.run_id).model, "fake")

    def test_file_reference_store_reads_only_project_owned_text_and_checks_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = StudioRepository(root / "studio.db")
            project = repo.create_project("项目", "展示类")
            project_dir = root / "uploads" / str(project["id"])
            project_dir.mkdir(parents=True)
            payload = "产品证据".encode("utf-8")
            (project_dir / "brief.txt").write_bytes(payload)
            import hashlib
            repo.add_project_file(
                project["id"], "brief.txt", "brief.txt", len(payload),
                sha256=hashlib.sha256(payload).hexdigest(), mime_type="text/plain",
                extraction_status="complete", safe_summary="产品证据",
            )
            store = FileReferenceAssetStore(repo, root / "uploads")
            content = store.read(project["id"], 1)
            self.assertEqual(content.text, "产品证据")
            (project_dir / "brief.txt").write_text("篡改", encoding="utf-8")
            with self.assertRaises(ReferenceAssetError):
                store.read(project["id"], 1)

    def test_file_reference_store_rejects_cross_project_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = StudioRepository(root / "studio.db")
            project = repo.create_project("项目", "展示类")
            uploads = root / "uploads"
            (uploads / "other").mkdir(parents=True)
            (uploads / "other" / "secret.txt").write_text("secret", encoding="utf-8")
            repo.add_project_file(
                project["id"], "brief.txt", "../other/secret.txt", 6,
                sha256="".join(["0"] * 64), mime_type="text/plain",
                extraction_status="complete", safe_summary="摘要",
            )
            store = FileReferenceAssetStore(repo, uploads)
            with self.assertRaises(ReferenceAssetError) as raised:
                store.read(project["id"], 1)
            self.assertEqual(raised.exception.error_code, "reference_asset_path_invalid")

if __name__ == "__main__":
    unittest.main()
