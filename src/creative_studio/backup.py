"""数据库、图片和上传目录的可验证备份与恢复工具。

默认命令只做 dry-run；恢复永远写入显式指定的新目录，不覆盖运行目录。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


MANIFEST_NAME = "manifest.json"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file()) if root.is_dir() else []


def _inventory(path: Path, relative_root: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    if path.is_file():
        return [{"path": relative_root, "size": path.stat().st_size, "sha256": _sha256(path)}]
    return [
        {
            "path": str(Path(relative_root) / file.relative_to(path)).replace("\\", "/"),
            "size": file.stat().st_size,
            "sha256": _sha256(file),
        }
        for file in _files(path)
    ]


def inspect_sources(database: Path, images: Path, uploads: Path) -> dict[str, Any]:
    database = Path(database).resolve()
    images = Path(images).resolve()
    uploads = Path(uploads).resolve()
    if not database.is_file():
        raise FileNotFoundError(f"database not found: {database}")
    with closing(sqlite3.connect(database)) as connection:
        connection.execute("PRAGMA query_only = ON")
        connection.execute("SELECT 1").fetchone()
    entries = _inventory(database, "database/creative_studio.db")
    entries.extend(_inventory(images, "images"))
    entries.extend(_inventory(uploads, "uploads"))
    return {
        "schema_version": "backup-manifest.v1",
        "sources": {"database": "database/creative_studio.db", "images": "images", "uploads": "uploads"},
        "entries": entries,
    }


def _validated_manifest_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate manifest paths and digests before any restore write occurs."""

    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("backup manifest entries are invalid")
    validated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_entries:
        if not isinstance(raw, dict):
            raise ValueError("backup manifest entry is invalid")
        path_text = str(raw.get("path") or "").replace("\\", "/")
        path = PurePosixPath(path_text)
        if not path_text or path.is_absolute() or re.match(r"^[A-Za-z]:/", path_text) or ".." in path.parts:
            raise ValueError("backup manifest path is invalid")
        if path_text in seen:
            raise ValueError("backup manifest contains duplicate paths")
        seen.add(path_text)
        size = raw.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError("backup manifest size is invalid")
        sha256 = str(raw.get("sha256") or "").lower()
        if not _SHA256_PATTERN.fullmatch(sha256):
            raise ValueError("backup manifest sha256 is invalid")
        validated.append({"path": path_text, "size": size, "sha256": sha256})
    return validated


def validate_reference_integrity(database: Path, images: Path, uploads: Path) -> bool:
    """Verify DB references resolve inside the restored images/uploads roots."""

    database = Path(database).resolve()
    images_root = Path(images).resolve()
    uploads_root = Path(uploads).resolve()
    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        table_names = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "project_files" in table_names:
            columns = {
                str(row[1]) for row in connection.execute("PRAGMA table_info(project_files)").fetchall()
            }
            if {"project_id", "stored_name"} <= columns:
                rows = connection.execute(
                    "SELECT project_id, stored_name FROM project_files"
                ).fetchall()
                for row in rows:
                    project_root = (uploads_root / str(row["project_id"])).resolve()
                    target = (project_root / str(row["stored_name"] or "")).resolve()
                    if target == project_root or project_root not in target.parents:
                        raise ValueError("reference upload path is outside project directory")
                    if not target.is_file():
                        raise ValueError("reference upload is missing")

        for table_name in ("visual_items", "display_frames"):
            if table_name not in table_names:
                continue
            columns = {
                str(row[1]) for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            if "image_path" not in columns:
                continue
            status_clause = " AND image_status='success'" if "image_status" in columns else ""
            rows = connection.execute(
                f"SELECT image_path FROM {table_name} WHERE image_path IS NOT NULL AND image_path != ''{status_clause}"
            ).fetchall()
            for row in rows:
                raw_path = Path(str(row["image_path"]))
                candidates: list[Path] = []
                parts = tuple(str(part) for part in raw_path.parts)
                image_marker = next(
                    (index for index, part in enumerate(parts) if part.lower() == "images"),
                    None,
                )
                if image_marker is not None and image_marker + 1 < len(parts):
                    candidates.append(images_root.joinpath(*parts[image_marker + 1 :]))
                elif not raw_path.is_absolute():
                    candidates.append(images_root / raw_path)
                candidates.append(images_root / raw_path.name)
                if not any(candidate.resolve().is_file() and images_root in candidate.resolve().parents for candidate in candidates):
                    raise ValueError("referenced image is missing")
    return True


def create_backup(
    database: Path,
    images: Path,
    uploads: Path,
    output: Path,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    manifest = inspect_sources(database, images, uploads)
    output = Path(output).resolve()
    source_paths = [Path(database).resolve(), Path(images).resolve(), Path(uploads).resolve()]
    if any(output == source or source.is_dir() and source in output.parents for source in source_paths):
        raise ValueError("backup output must be outside source paths")
    if dry_run:
        return manifest | {"output": "dry-run", "dry_run": True}
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"backup output must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    database_copy = output / "database" / "creative_studio.db"
    database_copy.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(Path(database).resolve())) as source, closing(sqlite3.connect(database_copy)) as target:
        source.backup(target)
    if Path(images).is_dir():
        shutil.copytree(Path(images), output / "images", dirs_exist_ok=True)
    if Path(uploads).is_dir():
        shutil.copytree(Path(uploads), output / "uploads", dirs_exist_ok=True)
    final_manifest = inspect_sources(database_copy, output / "images", output / "uploads")
    final_manifest["output"] = "backup"
    final_manifest["dry_run"] = False
    (output / MANIFEST_NAME).write_text(json.dumps(final_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return final_manifest


def plan_backup_retention(root: Path, *, keep_latest: int = 7) -> dict[str, Any]:
    """List retention candidates without deleting any backup directory."""

    root = Path(root).resolve()
    keep_latest = int(keep_latest)
    if keep_latest < 1:
        raise ValueError("keep_latest must be at least 1")
    if not root.exists():
        return {
            "root": str(root),
            "policy": "keep_latest",
            "keep_latest": keep_latest,
            "keep": [],
            "eligible_for_removal": [],
            "invalid": [],
            "dry_run": True,
        }
    if not root.is_dir():
        raise ValueError("retention root must be a directory")
    valid: list[tuple[float, str, Path]] = []
    invalid: list[str] = []
    for child in sorted(root.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or child.resolve().parent != root:
            continue
        manifest_path = child / MANIFEST_NAME
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or manifest.get("schema_version") != "backup-manifest.v1":
                raise ValueError("unsupported backup manifest")
            _validated_manifest_entries(manifest)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            invalid.append(str(child))
            continue
        valid.append((manifest_path.stat().st_mtime, child.name, child))
    valid.sort(key=lambda item: (item[0], item[1]), reverse=True)
    keep = [str(item[2]) for item in valid[:keep_latest]]
    eligible = [str(item[2]) for item in valid[keep_latest:]]
    return {
        "root": str(root),
        "policy": "keep_latest",
        "keep_latest": keep_latest,
        "keep": keep,
        "eligible_for_removal": eligible,
        "invalid": sorted(invalid),
        "dry_run": True,
    }


def restore_backup(backup_dir: Path, target_dir: Path) -> dict[str, Any]:
    backup_dir = Path(backup_dir).resolve()
    target_dir = Path(target_dir).resolve()
    manifest_path = backup_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValueError("backup manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "backup-manifest.v1":
        raise ValueError("unsupported backup manifest")
    expected_entries = _validated_manifest_entries(manifest)
    if target_dir.exists() and any(target_dir.iterdir()):
        raise FileExistsError("restore target must be a new or empty directory")
    if target_dir == backup_dir or target_dir in backup_dir.parents:
        raise ValueError("restore target must be outside backup directory")
    source_db = backup_dir / "database" / "creative_studio.db"
    if not source_db.is_file():
        raise ValueError("backup database is missing")
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{target_dir.name}.restore-", dir=str(target_dir.parent)))
    try:
        shutil.copy2(source_db, staging_dir / "creative_studio.db")
        with closing(sqlite3.connect(staging_dir / "creative_studio.db")) as connection:
            connection.execute("PRAGMA query_only = ON")
            connection.execute("SELECT 1").fetchone()
        for name in ("images", "uploads"):
            source = backup_dir / name
            if source.is_dir():
                shutil.copytree(source, staging_dir / name, dirs_exist_ok=True)
        restored_manifest = inspect_sources(staging_dir / "creative_studio.db", staging_dir / "images", staging_dir / "uploads")
        actual_entries = {
            str(item.get("path")): (int(item.get("size") or 0), str(item.get("sha256") or ""))
            for item in restored_manifest["entries"]
        }
        expected_pairs = {item["path"]: (item["size"], item["sha256"]) for item in expected_entries}
        if expected_pairs != actual_entries:
            raise ValueError("backup manifest verification failed")
        references_verified = validate_reference_integrity(
            staging_dir / "creative_studio.db", staging_dir / "images", staging_dir / "uploads"
        )
        if target_dir.exists():
            target_dir.rmdir()
        os.replace(staging_dir, target_dir)
        return {
            "target": str(target_dir),
            "database": str(target_dir / "creative_studio.db"),
            "verified": True,
            "references_verified": references_verified,
        }
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or inspect a Creative Studio backup")
    parser.add_argument("--database", type=Path, default=Path("data/creative_studio.db"))
    parser.add_argument("--images", type=Path, default=Path("data/images"))
    parser.add_argument("--uploads", type=Path, default=Path("data/uploads"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--restore-from", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--retention-root", type=Path)
    parser.add_argument("--keep-latest", type=int, default=7)
    args = parser.parse_args(argv)
    if args.retention_root is not None:
        if args.restore_from is not None or args.output is not None:
            parser.error("--retention-root cannot be combined with backup or restore arguments")
        print(json.dumps(plan_backup_retention(args.retention_root, keep_latest=args.keep_latest), ensure_ascii=False, sort_keys=True))
        return 0
    if args.restore_from is not None:
        if args.target is None:
            parser.error("--target is required with --restore-from")
        print(json.dumps(restore_backup(args.restore_from, args.target), ensure_ascii=False, sort_keys=True))
        return 0
    if args.output is None:
        parser.error("--output is required when creating a backup")
    print(json.dumps(create_backup(args.database, args.images, args.uploads, args.output, dry_run=args.dry_run), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
