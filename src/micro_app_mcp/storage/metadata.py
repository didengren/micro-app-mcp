"""元数据管理"""

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

from micro_app_mcp.config import config


class MetadataManager:
    """元数据管理器（单进程最小实现）。"""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.metadata_path = config.METADATA_PATH
        self._thread_lock = threading.RLock()
        self.metadata = self._load_metadata()
        self._initialized = True

    def _get_default_metadata(self) -> dict:
        """获取默认元数据。"""
        return {
            "version": "1.0.0",
            "last_updated": "1970-01-01T00:00:00Z",
            "github_commit": "",
            "docs_hash": "",
        }

    def _normalize_metadata(self, metadata: dict | None) -> dict:
        """合并默认与传入字段。"""
        default = self._get_default_metadata()
        return {**default, **(metadata or {})}

    def _load_metadata_unlocked(self) -> dict:
        """无锁读取 metadata.json（调用方负责加锁）。"""
        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                try:
                    return self._normalize_metadata(json.load(f))
                except json.JSONDecodeError:
                    return self._get_default_metadata()
        return self._get_default_metadata()

    def _save_metadata_unlocked(self):
        """无锁原子写入 metadata.json（调用方负责加锁）。"""
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = Path(f"{self.metadata_path}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        tmp_path.replace(self.metadata_path)

    def _load_metadata(self) -> dict:
        """加载元数据。"""
        with self._thread_lock:
            self.metadata = self._load_metadata_unlocked()
            return self.metadata

    def save_metadata(self):
        """保存元数据。"""
        with self._thread_lock:
            self._save_metadata_unlocked()

    def reload_metadata(self):
        """重新加载元数据。"""
        self._load_metadata()

    def _format_utc(self, value: datetime) -> str:
        """格式化 UTC 时间字符串。"""
        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

    def _parse_last_updated(self, value: str) -> datetime:
        """解析最后更新时间，异常时回退为 epoch。"""
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    def update_metadata(self):
        """更新元数据中的最后更新时间。"""
        with self._thread_lock:
            latest = self._load_metadata_unlocked()
            latest["last_updated"] = self._format_utc(datetime.now(timezone.utc))
            self.metadata = latest
            self._save_metadata_unlocked()

    def should_skip_update(self) -> bool:
        """检查是否应该跳过更新。"""
        with self._thread_lock:
            latest = self._load_metadata_unlocked()
            self.metadata = latest

            last_updated = self._parse_last_updated(
                latest.get("last_updated", "1970-01-01T00:00:00Z")
            )
            cache_duration = timedelta(hours=config.CACHE_DURATION_HOURS)
            return datetime.now(timezone.utc) - last_updated < cache_duration

    def get_last_updated(self) -> str:
        """获取最后更新时间。"""
        with self._thread_lock:
            latest = self._load_metadata_unlocked()
            self.metadata = latest
            return latest.get("last_updated", "1970-01-01T00:00:00Z")

    def get_status(self) -> Dict[str, object]:
        """获取知识库状态信息。"""
        with self._thread_lock:
            latest = self._load_metadata_unlocked()
            self.metadata = latest

            now = datetime.now(timezone.utc)
            last_updated = self._parse_last_updated(
                latest.get("last_updated", "1970-01-01T00:00:00Z")
            )
            age_delta = now - last_updated
            cache_duration = timedelta(hours=config.CACHE_DURATION_HOURS)
            next_update = last_updated + cache_duration

            return {
                "timezone": "UTC",
                "last_updated": self._format_utc(last_updated),
                "cache_duration_hours": config.CACHE_DURATION_HOURS,
                "age_seconds": int(age_delta.total_seconds()),
                "should_skip_update": age_delta < cache_duration,
                "is_stale": age_delta >= cache_duration,
                "next_recommended_update_at": self._format_utc(next_update),
            }
