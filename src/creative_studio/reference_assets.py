"""参考资料 port 的 SQLite + 文件系统适配器。"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .generation_models import ReferenceAsset, ReferenceAssetContent, ReferenceAssetPort, ReferenceAssetError
from .repository import StudioRepository


class FileReferenceAssetStore(ReferenceAssetPort):
    """只允许读取项目目录内、数据库登记过的参考资料。"""

    def __init__(self, repository: StudioRepository, uploads_dir: Path) -> None:
        self.repository = repository
        self.uploads_dir = Path(uploads_dir).resolve()

    def list_for_project(self, project_id: int) -> tuple[ReferenceAsset, ...]:
        return self.repository.list_reference_assets(int(project_id))

    def read(self, project_id: int, asset_id: int, *, max_bytes: int = 64_000) -> ReferenceAssetContent:
        storage_name = self.repository.reference_asset_storage_name(int(project_id), int(asset_id))
        project_root = (self.uploads_dir / str(project_id)).resolve()
        target = (project_root / storage_name).resolve()
        if target == project_root or project_root not in target.parents:
            raise ReferenceAssetError("参考文件路径越界", error_code="reference_asset_path_invalid")
        content = self.repository.reference_asset_content(
            int(project_id), int(asset_id), uploads_dir=self.uploads_dir, max_bytes=max_bytes
        )
        # A changed file is never silently treated as the original reference.
        if content.asset.sha256:
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() != content.asset.sha256:
                raise ReferenceAssetError("参考文件摘要已变化", error_code="reference_asset_changed", retryable=False)
        return content
