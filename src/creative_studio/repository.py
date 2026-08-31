"""独立创意工作台的 SQLite 持久化。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_FIELDS = {
    "name",
    "script_type",
    "task_type",
    "task_description",
    "creative_tags",
    "aspect_ratio",
    "product_evidence_summary",
}


class StudioDataError(RuntimeError):
    """可安全展示给本地用户的业务错误。"""


def now_text() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _loads(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


class StudioRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    script_type TEXT NOT NULL DEFAULT '展示类',
                    task_type TEXT NOT NULL DEFAULT '',
                    task_description TEXT NOT NULL DEFAULT '',
                    creative_tags_json TEXT NOT NULL DEFAULT '{}',
                    aspect_ratio TEXT NOT NULL DEFAULT '16:9',
                    product_evidence_summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    recommendation_kind TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    input_fingerprint TEXT NOT NULL,
                    batch_index INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    items_json TEXT NOT NULL DEFAULT '[]',
                    usage_json TEXT NOT NULL DEFAULT '{}',
                    conversation_id TEXT NOT NULL DEFAULT '',
                    assistant_message_id TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(project_id, recommendation_kind, input_fingerprint, batch_index)
                );
                CREATE TABLE IF NOT EXISTS visual_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation_id INTEGER NOT NULL REFERENCES generations(id) ON DELETE CASCADE,
                    item_index INTEGER NOT NULL,
                    content_json TEXT NOT NULL,
                    image_prompt TEXT NOT NULL,
                    aspect_ratio TEXT NOT NULL,
                    image_status TEXT NOT NULL DEFAULT 'queued',
                    image_path TEXT NOT NULL DEFAULT '',
                    image_error TEXT NOT NULL DEFAULT '',
                    gateway_job_id TEXT NOT NULL DEFAULT '',
                    image_attempt INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(generation_id, item_index)
                );
                CREATE TABLE IF NOT EXISTS adoptions (
                    project_id INTEGER PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
                    recommendation_kind TEXT NOT NULL,
                    reference_id TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_generations_history
                    ON generations(project_id, recommendation_kind, input_fingerprint, batch_index);
                CREATE INDEX IF NOT EXISTS idx_visual_items_status ON visual_items(image_status, updated_at);
                """
            )

    def create_project(self, name: str = "未命名创意", script_type: str = "展示类") -> dict[str, Any]:
        timestamp = now_text()
        normalized_type = "叙事类" if str(script_type).strip() == "叙事类" else "展示类"
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO projects(name, script_type, created_at, updated_at) VALUES(?,?,?,?)",
                (str(name or "").strip()[:120] or "未命名创意", normalized_type, timestamp, timestamp),
            )
            project_id = int(cursor.lastrowid)
        project = self.get_project(project_id)
        if project is None:
            raise StudioDataError("项目创建失败")
        return project

    def list_projects(self, keyword: str = "") -> list[dict[str, Any]]:
        value = str(keyword or "").strip()
        where = "WHERE p.name LIKE ?" if value else ""
        params: tuple[Any, ...] = (f"%{value}%",) if value else ()
        query = f"""
            SELECT p.*, a.recommendation_kind AS adopted_kind,
                   a.snapshot_json AS adopted_snapshot_json
            FROM projects p
            LEFT JOIN adoptions a ON a.project_id = p.id
            {where}
            ORDER BY p.updated_at DESC, p.id DESC
        """
        with closing(self._connect()) as connection:
            rows = connection.execute(query, params).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            snapshot = _loads(row["adopted_snapshot_json"], {})
            title = str(snapshot.get("title") or snapshot.get("story") or "") if isinstance(snapshot, dict) else ""
            result.append({
                "id": int(row["id"]),
                "name": row["name"],
                "script_type": row["script_type"],
                "updated_at": row["updated_at"],
                "adopted_kind": str(row["adopted_kind"] or ""),
                "adopted_title": title,
            })
        return result

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (int(project_id),)).fetchone()
            if row is None:
                return None
            files = connection.execute(
                "SELECT id, original_name, size_bytes, created_at FROM project_files WHERE project_id=? ORDER BY id",
                (int(project_id),),
            ).fetchall()
            adoption = connection.execute(
                "SELECT recommendation_kind, reference_id, snapshot_json, updated_at FROM adoptions WHERE project_id=?",
                (int(project_id),),
            ).fetchone()
        result = {
            "id": int(row["id"]),
            "name": row["name"],
            "script_type": row["script_type"],
            "task_type": row["task_type"],
            "task_description": row["task_description"],
            "creative_tags": _loads(row["creative_tags_json"], {}),
            "aspect_ratio": row["aspect_ratio"],
            "product_evidence_summary": row["product_evidence_summary"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "reference_files": [dict(item) for item in files],
            "adoption": None,
        }
        if adoption is not None:
            result["adoption"] = {
                "recommendation_kind": adoption["recommendation_kind"],
                "reference_id": adoption["reference_id"],
                "snapshot": _loads(adoption["snapshot_json"], {}),
                "updated_at": adoption["updated_at"],
            }
        return result

    def update_project(self, project_id: int, values: dict[str, Any]) -> dict[str, Any]:
        current = self.get_project(project_id)
        if current is None:
            raise StudioDataError("项目不存在")
        merged = {key: current[key] for key in PROJECT_FIELDS}
        for key in PROJECT_FIELDS:
            if key in values:
                merged[key] = values[key]
        name = str(merged["name"] or "").strip()[:120] or "未命名创意"
        script_type = "叙事类" if str(merged["script_type"]).strip() == "叙事类" else "展示类"
        aspect_ratio = "9:16" if str(merged["aspect_ratio"]).strip() == "9:16" else "16:9"
        tags = merged["creative_tags"] if isinstance(merged["creative_tags"], dict) else {}
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                UPDATE projects
                SET name=?, script_type=?, task_type=?, task_description=?, creative_tags_json=?,
                    aspect_ratio=?, product_evidence_summary=?, updated_at=?
                WHERE id=?
                """,
                (
                    name,
                    script_type,
                    str(merged["task_type"] or "").strip()[:100],
                    str(merged["task_description"] or "").strip()[:4000],
                    _json(tags),
                    aspect_ratio,
                    str(merged["product_evidence_summary"] or "").strip()[:4000],
                    timestamp,
                    int(project_id),
                ),
            )
        updated = self.get_project(project_id)
        if updated is None:
            raise StudioDataError("项目保存失败")
        return updated

    def delete_project(self, project_id: int) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute("DELETE FROM projects WHERE id=?", (int(project_id),))
        return cursor.rowcount > 0

    def add_project_file(self, project_id: int, original_name: str, stored_name: str, size_bytes: int) -> dict[str, Any]:
        if self.get_project(project_id) is None:
            raise StudioDataError("项目不存在")
        timestamp = now_text()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "INSERT INTO project_files(project_id,original_name,stored_name,size_bytes,created_at) VALUES(?,?,?,?,?)",
                (int(project_id), str(original_name)[:255], str(stored_name), int(size_bytes), timestamp),
            )
            file_id = int(cursor.lastrowid)
        return {"id": file_id, "original_name": str(original_name)[:255], "size_bytes": int(size_bytes), "created_at": timestamp}

    def reference_file_names(self, project_id: int) -> list[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT original_name FROM project_files WHERE project_id=? ORDER BY id", (int(project_id),)
            ).fetchall()
        return [str(row["original_name"]) for row in rows]

    def reserve_generation(self, project_id: int, kind: str, schema_version: str, fingerprint: str) -> dict[str, Any]:
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            project = connection.execute("SELECT id FROM projects WHERE id=?", (int(project_id),)).fetchone()
            if project is None:
                connection.rollback()
                raise StudioDataError("项目不存在")
            connection.execute(
                "DELETE FROM generations WHERE project_id=? AND recommendation_kind=? AND input_fingerprint=? AND status='failed'",
                (int(project_id), kind, fingerprint),
            )
            rows = connection.execute(
                """
                SELECT id,batch_index,status,conversation_id,assistant_message_id
                FROM generations
                WHERE project_id=? AND recommendation_kind=? AND input_fingerprint=?
                  AND status IN ('pending','success')
                ORDER BY batch_index
                """,
                (int(project_id), kind, fingerprint),
            ).fetchall()
            if len(rows) >= 2:
                connection.rollback()
                raise StudioDataError("当前定位已生成2批，请修改输入后再生成")
            if any(row["status"] == "pending" for row in rows):
                connection.rollback()
                raise StudioDataError("当前项目已有一批正在生成")
            batch_index = len(rows) + 1
            previous = rows[-1] if rows else None
            cursor = connection.execute(
                """
                INSERT INTO generations(project_id,recommendation_kind,schema_version,input_fingerprint,
                                        batch_index,status,created_at,updated_at)
                VALUES(?,?,?,?,?,'pending',?,?)
                """,
                (int(project_id), kind, schema_version, fingerprint, batch_index, timestamp, timestamp),
            )
            connection.commit()
        return {
            "id": int(cursor.lastrowid),
            "batch_index": batch_index,
            "conversation_id": str(previous["conversation_id"] or "") if previous else "",
            "parent_message_id": str(previous["assistant_message_id"] or "") if previous else "",
        }

    def complete_narrative_generation(self, generation_id: int, result: Any) -> None:
        self._complete_generation(generation_id, result, visual_items=None)

    def complete_visual_generation(self, generation_id: int, result: Any, aspect_ratio: str) -> list[int]:
        return self._complete_generation(generation_id, result, visual_items=(result.items, aspect_ratio))

    def _complete_generation(self, generation_id: int, result: Any, visual_items: tuple[Any, str] | None) -> list[int]:
        timestamp = now_text()
        usage = {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
            "usage_source": result.usage_source,
            "latency_ms": result.latency_ms,
        }
        item_ids: list[int] = []
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE generations
                SET status='success', items_json=?, usage_json=?, conversation_id=?,
                    assistant_message_id=?, error='', updated_at=?
                WHERE id=? AND status='pending'
                """,
                (
                    _json(result.items),
                    _json(usage),
                    str(result.conversation_id or ""),
                    str(result.assistant_message_id or ""),
                    timestamp,
                    int(generation_id),
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise StudioDataError("生成记录状态已经变化")
            if visual_items is not None:
                items, aspect_ratio = visual_items
                for index, source in enumerate(items, start=1):
                    content = dict(source)
                    image_prompt = str(content.pop("image_prompt", ""))
                    child = connection.execute(
                        """
                        INSERT INTO visual_items(generation_id,item_index,content_json,image_prompt,aspect_ratio,
                                                 image_status,created_at,updated_at)
                        VALUES(?,?,?,?,?,'queued',?,?)
                        """,
                        (int(generation_id), index, _json(content), image_prompt, aspect_ratio, timestamp, timestamp),
                    )
                    item_ids.append(int(child.lastrowid))
            connection.execute(
                "UPDATE projects SET updated_at=? WHERE id=(SELECT project_id FROM generations WHERE id=?)",
                (timestamp, int(generation_id)),
            )
            connection.commit()
        return item_ids

    def fail_generation(self, generation_id: int, error: str) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE generations SET status='failed',error=?,updated_at=? WHERE id=? AND status='pending'",
                (" ".join(str(error or "").split())[:500], now_text(), int(generation_id)),
            )

    def generation_history(self, project_id: int, kind: str, fingerprint: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT * FROM generations
                WHERE project_id=? AND recommendation_kind=? AND status='success'
                ORDER BY created_at,id
                """,
                (int(project_id), kind),
            ).fetchall()
            visual_rows = connection.execute(
                """
                SELECT v.* FROM visual_items v JOIN generations g ON g.id=v.generation_id
                WHERE g.project_id=? AND g.recommendation_kind=? ORDER BY v.generation_id,v.item_index
                """,
                (int(project_id), kind),
            ).fetchall()
        visuals: dict[int, list[dict[str, Any]]] = {}
        for row in visual_rows:
            item = _loads(row["content_json"], {})
            item.update({
                "id": int(row["id"]),
                "item_index": int(row["item_index"]),
                "aspect_ratio": row["aspect_ratio"],
                "image_status": row["image_status"],
                "image_url": f"/api/visual-items/{int(row['id'])}/image" if row["image_status"] == "success" else "",
                "image_error": row["image_error"],
            })
            visuals.setdefault(int(row["generation_id"]), []).append(item)
        current: list[dict[str, Any]] = []
        stale: list[dict[str, Any]] = []
        for row in rows:
            entry = {
                "id": int(row["id"]),
                "batch_index": int(row["batch_index"]),
                "input_fingerprint": row["input_fingerprint"],
                "items": visuals.get(int(row["id"]), _loads(row["items_json"], [])),
                "usage": _loads(row["usage_json"], {}),
                "created_at": row["created_at"],
            }
            (current if row["input_fingerprint"] == fingerprint else stale).append(entry)
        return {
            "batches": current,
            "stale_batches": stale,
            "remaining_generations": max(0, 2 - len(current)),
        }

    def visual_item(self, item_id: int) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT v.*,g.project_id FROM visual_items v
                JOIN generations g ON g.id=v.generation_id WHERE v.id=?
                """,
                (int(item_id),),
            ).fetchone()
        return dict(row) if row is not None else None

    def recover_visual_items(self) -> list[int]:
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE visual_items SET image_status='queued',updated_at=? WHERE image_status='generating'",
                (timestamp,),
            )
            rows = connection.execute("SELECT id FROM visual_items WHERE image_status='queued' ORDER BY id").fetchall()
        return [int(row["id"]) for row in rows]

    def claim_visual_item(self, item_id: int) -> dict[str, Any] | None:
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE visual_items SET image_status='generating',image_error='',image_attempt=image_attempt+1,updated_at=?
                WHERE id=? AND image_status='queued'
                """,
                (timestamp, int(item_id)),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                return None
            row = connection.execute("SELECT * FROM visual_items WHERE id=?", (int(item_id),)).fetchone()
            connection.commit()
        return dict(row) if row is not None else None

    def set_gateway_job(self, item_id: int, attempt: int, job_id: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE visual_items SET gateway_job_id=?,updated_at=?
                WHERE id=? AND image_status='generating' AND image_attempt=?
                """,
                (str(job_id), now_text(), int(item_id), int(attempt)),
            )
        return cursor.rowcount == 1

    def complete_visual_item(self, item_id: int, attempt: int, image_path: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE visual_items
                SET image_status='success',image_path=?,image_error='',updated_at=?
                WHERE id=? AND image_status='generating' AND image_attempt=?
                """,
                (str(image_path), now_text(), int(item_id), int(attempt)),
            )
        return cursor.rowcount == 1

    def fail_visual_item(self, item_id: int, attempt: int, error: str) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE visual_items SET image_status='failed',image_error=?,updated_at=?
                WHERE id=? AND image_status='generating' AND image_attempt=?
                """,
                (" ".join(str(error or "").split())[:500], now_text(), int(item_id), int(attempt)),
            )
        return cursor.rowcount == 1

    def retry_visual_item(self, item_id: int) -> bool:
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                UPDATE visual_items
                SET image_status='queued',image_error='',gateway_job_id='',image_path='',updated_at=?
                WHERE id=? AND image_status='failed'
                """,
                (now_text(), int(item_id)),
            )
        return cursor.rowcount == 1

    def adopt_visual(self, project_id: int, item_id: int) -> dict[str, Any]:
        item = self.visual_item(item_id)
        if item is None or int(item["project_id"]) != int(project_id):
            raise StudioDataError("视觉方案不属于当前项目")
        snapshot = _loads(item["content_json"], {})
        self._save_adoption(project_id, "visual", str(item_id), snapshot)
        return snapshot

    def adopt_narrative(self, project_id: int, generation_id: int, item_index: int) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT items_json FROM generations WHERE id=? AND project_id=? AND recommendation_kind='narrative' AND status='success'",
                (int(generation_id), int(project_id)),
            ).fetchone()
        items = _loads(row["items_json"], []) if row is not None else []
        if not isinstance(items, list) or item_index < 0 or item_index >= len(items):
            raise StudioDataError("叙事方案不存在")
        snapshot = items[item_index]
        self._save_adoption(project_id, "narrative", f"{generation_id}:{item_index}", snapshot)
        return snapshot

    def _save_adoption(self, project_id: int, kind: str, reference_id: str, snapshot: Any) -> None:
        timestamp = now_text()
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO adoptions(project_id,recommendation_kind,reference_id,snapshot_json,updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(project_id) DO UPDATE SET
                    recommendation_kind=excluded.recommendation_kind,
                    reference_id=excluded.reference_id,
                    snapshot_json=excluded.snapshot_json,
                    updated_at=excluded.updated_at
                """,
                (int(project_id), kind, reference_id, _json(snapshot), timestamp),
            )
            connection.execute("UPDATE projects SET updated_at=? WHERE id=?", (timestamp, int(project_id)))

    def image_path_for_item(self, item_id: int) -> Path | None:
        item = self.visual_item(item_id)
        if item is None or item["image_status"] != "success" or not item["image_path"]:
            return None
        return Path(str(item["image_path"]))
