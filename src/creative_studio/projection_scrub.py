"""Dry-run-first rebuild for legacy public result projections."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .public_projection import PRIVATE_RESULT_FIELDS, PublicResultMapper


ROOT_DIR = Path(__file__).resolve().parents[2]
LIVE_DATABASE_PATH = (ROOT_DIR / "data" / "creative_studio.db").resolve()


@dataclass(frozen=True)
class ProjectionScrubStats:
    scanned_rows: int
    changed_rows: int
    private_field_occurrences: int
    invalid_json_rows: int
    unknown_kind_rows: int
    applied: bool
    backup_path: str = ""


def _private_field_occurrences(value: Any) -> int:
    if isinstance(value, dict):
        return sum(
            (1 if str(key) in PRIVATE_RESULT_FIELDS else 0)
            + _private_field_occurrences(child)
            for key, child in value.items()
        )
    if isinstance(value, (list, tuple)):
        return sum(_private_field_occurrences(child) for child in value)
    return 0


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _projection_hash(value: Any) -> str:
    return hashlib.sha256(_json_text(value).encode("utf-8")).hexdigest()


def _scan_projection_updates(
    connection: sqlite3.Connection,
    projector: PublicResultMapper,
) -> tuple[list[tuple[str, int, str]], int, int, int, int]:
    updates: list[tuple[str, int, str]] = []
    scanned_rows = 0
    private_count = 0
    invalid_rows = 0
    unknown_kind_rows = 0
    rows_by_table = (
        (
            "generation",
            connection.execute(
                "SELECT id,recommendation_kind,items_json FROM generations ORDER BY id"
            ).fetchall(),
        ),
        (
            "adoption",
            connection.execute(
                "SELECT project_id,recommendation_kind,snapshot_json FROM adoptions ORDER BY project_id"
            ).fetchall(),
        ),
    )
    for table, rows in rows_by_table:
        for row_id, kind, raw_json in rows:
            scanned_rows += 1
            recommendation_kind = str(kind)
            if recommendation_kind not in {"narrative", "visual"}:
                unknown_kind_rows += 1
                continue
            try:
                value = json.loads(str(raw_json or ""))
            except (TypeError, ValueError, json.JSONDecodeError):
                invalid_rows += 1
                continue
            if (table == "generation" and not isinstance(value, list)) or (
                table == "adoption" and not isinstance(value, dict)
            ):
                invalid_rows += 1
                continue
            private_count += _private_field_occurrences(value)
            if table == "generation":
                projected = [
                    projector.result_item(item, recommendation_kind=recommendation_kind)
                    for item in value
                ]
            else:
                projected = projector.result_item(
                    value,
                    recommendation_kind=recommendation_kind,
                )
            if projected != value:
                updates.append((table, int(row_id), _json_text(projected)))
    return updates, scanned_rows, private_count, invalid_rows, unknown_kind_rows


def scrub_public_projections(
    database_path: Path,
    *,
    apply: bool = False,
    backup_path: Path | None = None,
    mapper: PublicResultMapper | None = None,
) -> ProjectionScrubStats:
    """Scan or rebuild legacy public JSON without touching image/task internals."""

    target = Path(database_path).resolve()
    if not target.is_file():
        raise FileNotFoundError(target)
    if apply and target == LIVE_DATABASE_PATH:
        raise ValueError("禁止直接 apply 真实 data/creative_studio.db")
    if apply and backup_path is None:
        raise ValueError("apply requires a backup path")
    resolved_backup = Path(backup_path).resolve() if backup_path is not None else None
    if resolved_backup == target:
        raise ValueError("backup path must differ from database path")
    if apply and resolved_backup is not None and resolved_backup.exists():
        raise FileExistsError(resolved_backup)

    projector = mapper or PublicResultMapper()
    connection_target: str | Path = target
    connection_options: dict[str, Any] = {}
    if not apply:
        connection_target = f"{target.as_uri()}?mode=ro"
        connection_options["uri"] = True

    with closing(sqlite3.connect(connection_target, **connection_options)) as connection:
        updates, scanned_rows, private_count, invalid_rows, unknown_kind_rows = (
            _scan_projection_updates(connection, projector)
        )

        if apply and resolved_backup is not None:
            if invalid_rows:
                raise ValueError(f"projection scrub found {invalid_rows} invalid JSON rows")
            if unknown_kind_rows:
                raise ValueError(
                    f"projection scrub found {unknown_kind_rows} unknown recommendation kind rows"
                )
            resolved_backup.parent.mkdir(parents=True, exist_ok=True)
            with closing(sqlite3.connect(resolved_backup)) as backup:
                connection.backup(backup)
            connection.execute("BEGIN IMMEDIATE")
            try:
                for table, row_id, projected_json in updates:
                    if table == "generation":
                        connection.execute(
                            "UPDATE generations SET items_json=? WHERE id=?",
                            (projected_json, row_id),
                        )
                    else:
                        connection.execute(
                            "UPDATE adoptions SET snapshot_json=? WHERE project_id=?",
                            (projected_json, row_id),
                        )
                for table, row_id, projected_json in updates:
                    column = "items_json" if table == "generation" else "snapshot_json"
                    key = "id" if table == "generation" else "project_id"
                    actual = connection.execute(
                        f"SELECT {column} FROM {'generations' if table == 'generation' else 'adoptions'} "
                        f"WHERE {key}=?",
                        (row_id,),
                    ).fetchone()
                    if actual is None or _projection_hash(json.loads(actual[0])) != _projection_hash(
                        json.loads(projected_json)
                    ):
                        raise RuntimeError("projection scrub verification failed")
                    if _private_field_occurrences(json.loads(actual[0])):
                        raise RuntimeError("projection scrub retained private fields")
                (
                    remaining_updates,
                    verified_rows,
                    _verified_private_count,
                    verified_invalid_rows,
                    verified_unknown_kind_rows,
                ) = _scan_projection_updates(connection, projector)
                if verified_rows != scanned_rows:
                    raise RuntimeError("projection scrub row-count verification failed")
                if verified_invalid_rows or verified_unknown_kind_rows:
                    raise RuntimeError("projection scrub verification found invalid rows")
                if remaining_updates:
                    raise RuntimeError("projection scrub fixed-point verification failed")
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    return ProjectionScrubStats(
        scanned_rows=scanned_rows,
        changed_rows=len(updates),
        private_field_occurrences=private_count,
        invalid_json_rows=invalid_rows,
        unknown_kind_rows=unknown_kind_rows,
        applied=bool(apply),
        backup_path=str(resolved_backup) if apply and resolved_backup is not None else "",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=LIVE_DATABASE_PATH)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    stats = scrub_public_projections(
        args.database,
        apply=bool(args.apply),
        backup_path=args.backup,
    )
    print(json.dumps(asdict(stats), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
