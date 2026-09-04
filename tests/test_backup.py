import json
import tempfile
import unittest
from pathlib import Path
import sqlite3

from creative_studio.backup import (
    create_backup,
    plan_backup_retention,
    restore_backup,
    validate_reference_integrity,
)


class BackupTests(unittest.TestCase):
    def test_backup_restore_round_trip_to_new_directory(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            database = root / "creative.db"
            images = root / "images"
            uploads = root / "uploads"
            images.mkdir()
            uploads.mkdir()
            images.joinpath("one.png").write_bytes(b"image")
            uploads.joinpath("brief.txt").write_text("brief", encoding="utf-8")
            import sqlite3
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE projects(id INTEGER PRIMARY KEY, name TEXT)")
                connection.execute("INSERT INTO projects(name) VALUES ('demo')")
                connection.commit()
            finally:
                connection.close()
            backup = root / "backup"
            manifest = create_backup(database, images, uploads, backup, dry_run=False)
            self.assertEqual(manifest["schema_version"], "backup-manifest.v1")
            restored = root / "restored"
            result = restore_backup(backup, restored)
            self.assertTrue(result["verified"])
            self.assertEqual((restored / "images/one.png").read_bytes(), b"image")
            self.assertEqual((restored / "uploads/brief.txt").read_text(encoding="utf-8"), "brief")

    def test_dry_run_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            database = root / "creative.db"
            import sqlite3
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE projects(id INTEGER PRIMARY KEY)")
                connection.commit()
            finally:
                connection.close()
            output = root / "dry-run"
            create_backup(database, root / "images", root / "uploads", output, dry_run=True)
            self.assertFalse(output.exists())

    def test_restore_rejects_tampered_manifest_without_leaving_partial_target(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            database = root / "creative.db"
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE projects(id INTEGER PRIMARY KEY)")
                connection.commit()
            finally:
                connection.close()
            backup = root / "backup"
            create_backup(database, root / "images", root / "uploads", backup, dry_run=False)
            manifest_path = backup / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entries"][0]["sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            target = root / "restored"
            with self.assertRaisesRegex(ValueError, "manifest verification"):
                restore_backup(backup, target)
            self.assertFalse(target.exists())

    def test_restore_rejects_path_escape_in_manifest_before_copy(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            database = root / "creative.db"
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE projects(id INTEGER PRIMARY KEY)")
                connection.commit()
            finally:
                connection.close()
            backup = root / "backup"
            create_backup(database, root / "images", root / "uploads", backup, dry_run=False)
            manifest_path = backup / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entries"].append({"path": "../outside", "size": 0, "sha256": "0" * 64})
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "manifest"):
                restore_backup(backup, root / "restored")

    def test_restore_checks_project_file_reference_integrity(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            database = root / "creative.db"
            uploads = root / "uploads"
            (uploads / "7").mkdir(parents=True)
            (uploads / "7" / "brief.txt").write_text("brief", encoding="utf-8")
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE projects(id INTEGER PRIMARY KEY)")
                connection.execute(
                    "CREATE TABLE project_files(project_id INTEGER, stored_name TEXT)"
                )
                connection.execute("INSERT INTO projects(id) VALUES (7)")
                connection.execute("INSERT INTO project_files(project_id,stored_name) VALUES (7,'brief.txt')")
                connection.commit()
            finally:
                connection.close()
            backup = root / "backup"
            create_backup(database, root / "images", uploads, backup, dry_run=False)
            result = restore_backup(backup, root / "restored")
            self.assertTrue(result["references_verified"])

            # The manifest can be internally valid while a referenced upload is missing.
            (backup / "uploads" / "7" / "brief.txt").unlink()
            manifest_path = backup / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["entries"] = [
                entry for entry in manifest["entries"] if entry["path"] != "uploads/7/brief.txt"
            ]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reference"):
                restore_backup(backup, root / "restored-missing")

    def test_reference_integrity_accepts_nested_absolute_image_paths(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            database = root / "creative.db"
            images = root / "images"
            (images / "17" / "7").mkdir(parents=True)
            image = images / "17" / "7" / "attempt-1.png"
            image.write_bytes(b"png")
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE visual_items(image_status TEXT, image_path TEXT)")
                connection.execute(
                    "INSERT INTO visual_items(image_status,image_path) VALUES ('success',?)",
                    (str(image),),
                )
                connection.commit()
            finally:
                connection.close()
            self.assertTrue(validate_reference_integrity(database, images, root / "uploads"))

    def test_retention_plan_is_read_only_and_fail_closed_for_invalid_manifests(self):
        with tempfile.TemporaryDirectory() as root_text:
            root = Path(root_text)
            database = root / "creative.db"
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE projects(id INTEGER PRIMARY KEY)")
                connection.commit()
            finally:
                connection.close()
            backup_root = root / "backups"
            outputs = []
            for index in range(3):
                output = backup_root / f"backup-{index}"
                create_backup(database, root / "images", root / "uploads", output, dry_run=False)
                outputs.append(output)
            import os
            for index, output in enumerate(outputs):
                os.utime(output / "manifest.json", (100 + index, 100 + index))
            invalid = backup_root / "invalid"
            invalid.mkdir(parents=True)
            (invalid / "manifest.json").write_text("{}", encoding="utf-8")

            plan = plan_backup_retention(backup_root, keep_latest=1)
            self.assertEqual(plan["keep"], [str(outputs[-1].resolve())])
            self.assertEqual(
                plan["eligible_for_removal"],
                [str(outputs[1].resolve()), str(outputs[0].resolve())],
            )
            self.assertEqual(plan["invalid"], [str(invalid.resolve())])
            self.assertTrue(invalid.exists())


if __name__ == "__main__":
    unittest.main()
