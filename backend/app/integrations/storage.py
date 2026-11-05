"""存储适配层。

v1.1 只实现 LocalStorage：文件写磁盘，库里存相对路径。
将来要上 OSS，新增一个 OSSStorage 实现同一套方法即可，业务代码不动。
"""
from __future__ import annotations

import hashlib
import shutil
import uuid
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import BinaryIO

from app.core.config import settings


class Storage(ABC):
    @abstractmethod
    def save(self, src: BinaryIO, biz_type: str, filename: str) -> tuple[str, int, str]:
        """写入并返回 (rel_path, size_bytes, sha256)。"""

    @abstractmethod
    def path(self, rel_path: str) -> Path:
        """解析出磁盘绝对路径，并保证不逃出数据根目录。"""

    @abstractmethod
    def delete(self, rel_path: str) -> None: ...


class LocalStorage(Storage):
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or settings.upload_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _subdir(self, biz_type: str) -> Path:
        if biz_type == "book":
            sub = Path("books")
        elif biz_type in {"shot", "avatar"}:
            sub = Path(biz_type + "s") / f"{date.today():%Y}" / f"{date.today():%m}"
        else:
            raise ValueError(f"未知的 biz_type: {biz_type}")
        d = self.root / sub
        d.mkdir(parents=True, exist_ok=True)
        return sub

    def save(self, src: BinaryIO, biz_type: str, filename: str) -> tuple[str, int, str]:
        sub = self._subdir(biz_type)
        suffix = Path(filename or "").suffix.lower()[:10]
        name = f"{uuid.uuid4().hex}{suffix}"
        dst = self.root / sub / name

        digest = hashlib.sha256()
        size = 0
        # 边读边写：40MB 的教材不进内存
        with dst.open("wb") as out:
            while chunk := src.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)

        return str((sub / name).as_posix()), size, digest.hexdigest()

    def path(self, rel_path: str) -> Path:
        p = (self.root / rel_path).resolve()
        if p != self.root and self.root not in p.parents:
            raise PermissionError("路径越界")
        return p

    def delete(self, rel_path: str) -> None:
        try:
            self.path(rel_path).unlink(missing_ok=True)
        except (PermissionError, OSError):
            pass

    def stats(self) -> dict[str, int]:
        files = [p for p in self.root.rglob("*") if p.is_file()]
        return {"files": len(files), "bytes": sum(p.stat().st_size for p in files)}


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = LocalStorage()
    return _storage


def copy_tree(src: Path, dst: Path) -> None:
    """备份脚本用：整目录同步。"""
    shutil.copytree(src, dst, dirs_exist_ok=True)
