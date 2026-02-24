"""元数据管理"""

import json
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterator

from micro_app_mcp.config import config

try:
    import fcntl
except ImportError:  # pragma: no cover - 非 Unix 平台兜底
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - 非 Windows 平台兜底
    msvcrt = None


# ┌─────────────────────────────────────────────────────────────┐
# │                    MetadataManager                          │
# ├─────────────────────────────────────────────────────────────┤
# │  创建阶段                                                   │
# │  __new__() → __init__() → 单例实例                          │
# ├─────────────────────────────────────────────────────────────┤
# │  读写阶段                                                   │
# │  ┌─────────────────────────────────────────────────────┐   │
# │  │  _file_lock() + _thread_lock                         │   │
# │  │       ↓                                              │   │
# │  │  _load_metadata_unlocked() / _save_metadata_unlocked()│  │
# │  └─────────────────────────────────────────────────────┘   │
# ├─────────────────────────────────────────────────────────────┤
# │  业务方法                                                   │
# │  should_skip_update() → 判断是否在缓存期内                    │
# │  get_last_updated()   → 获取最后更新时间                     │
# │  update_metadata()    → 更新 last_updated 时间              │
# │  save_update_job()    → 保存更新任务记录                     │
# │  get_update_job()     → 获取更新任务记录                     │
# │  get_status()         → 获取知识库状态                       │
# └─────────────────────────────────────────────────────────────┘
class MetadataManager:
    """元数据管理器

    存储版本信息和更新时间

    提供进程内单例、线程锁和文件锁，保障并发读写 metadata.json 的一致性。
    """

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
        self.lock_path = Path(f"{self.metadata_path}.lock")
        self._thread_lock = threading.RLock()
        self.metadata = self._load_metadata()
        self._initialized = True

    @contextmanager
    def _file_lock(self) -> Iterator[None]:
        """文件锁：用于多进程并发保护"""
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.lock_path, "a+b") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            elif msvcrt is not None:
                # Windows 锁定首字节，提供进程级互斥
                lock_file.seek(0)
                lock_file.write(b"\0")
                lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                elif msvcrt is not None:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)

    def _get_default_metadata(self) -> dict:
        """获取默认元数据"""
        return {
            "version": "1.0.0",
            "last_updated": "1970-01-01T00:00:00Z",
            "github_commit": "",
            "docs_hash": "",
            "update_jobs": {},
        }

    def _normalize_metadata(self, metadata: dict) -> dict:
        """合并默认与传入字段并修正字段类型"""
        default = self._get_default_metadata()
        normalized = {**default, **(metadata or {})}
        if not isinstance(normalized.get("update_jobs"), dict):
            normalized["update_jobs"] = {}
        return normalized

    def _load_metadata_unlocked(self) -> dict:
        """无锁读取 metadata.json（调用方负责加锁）"""
        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                try:
                    return self._normalize_metadata(json.load(f))
                except json.JSONDecodeError:
                    return self._get_default_metadata()
        return self._get_default_metadata()

    def _save_metadata_unlocked(self):
        """无锁写入 metadata.json（调用方负责加锁）"""
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)

    def _load_metadata(self) -> dict:
        """加载元数据"""
        with self._thread_lock:
            with self._file_lock():
                self.metadata = self._load_metadata_unlocked()
                return self.metadata

    def save_metadata(self):
        """保存元数据"""
        with self._thread_lock:
            with self._file_lock():
                self._save_metadata_unlocked()

    def reload_metadata(self):
        """重新加载元数据"""
        self._load_metadata()

    def _format_utc(self, value: datetime) -> str:
        """格式化 UTC 时间字符串"""
        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

    def _parse_last_updated(self, value: str) -> datetime:
        """解析最后更新时间，异常时回退为 epoch"""
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    def _parse_utc_datetime(self, value: str | None) -> datetime:
        """解析 UTC 时间字符串，异常时回退 epoch"""
        if not value:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    def update_metadata(self):
        """更新元数据中的最后更新时间"""
        with self._thread_lock:
            with self._file_lock():
                latest = self._load_metadata_unlocked()
                latest["last_updated"] = self._format_utc(datetime.now(timezone.utc))
                self.metadata = latest
                self._save_metadata_unlocked()

    def should_skip_update(self) -> bool:
        """检查是否应该跳过更新"""
        with self._thread_lock:
            with self._file_lock():
                latest = self._load_metadata_unlocked()
                self.metadata = latest

                last_updated = self._parse_last_updated(
                    latest.get("last_updated", "1970-01-01T00:00:00Z")
                )
                cache_duration = timedelta(hours=config.CACHE_DURATION_HOURS)
                return datetime.now(timezone.utc) - last_updated < cache_duration

    def get_last_updated(self) -> str:
        """获取最后更新时间"""
        with self._thread_lock:
            with self._file_lock():
                latest = self._load_metadata_unlocked()
                self.metadata = latest
                return latest.get("last_updated", "1970-01-01T00:00:00Z")

    def save_update_job(
        self,
        job: Dict[str, object],
        max_jobs: int | None = None,
        max_age_hours: int | None = None,
    ):
        """保存更新任务状态到 metadata.json"""
        if max_jobs is None:
            max_jobs = config.UPDATE_JOB_MAX_RECORDS
        if max_age_hours is None:
            max_age_hours = config.UPDATE_JOB_RETENTION_HOURS

        with self._thread_lock:
            with self._file_lock():
                latest = self._load_metadata_unlocked()
                update_jobs = latest.setdefault("update_jobs", {})
                job_id = str(job["job_id"])
                existing = update_jobs.get(job_id)

                # 内容无变化时跳过写盘，降低高频调用下的 I/O 开销。
                if isinstance(existing, dict) and existing == job:
                    self.metadata = latest
                    return

                update_jobs[job_id] = job

                # 先按保留时长清理陈旧任务，再按最大条数裁剪。
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(hours=max_age_hours)
                update_jobs = {
                    jid: item
                    for jid, item in update_jobs.items()
                    if self._parse_utc_datetime(item.get("created_at")) >= cutoff
                }
                latest["update_jobs"] = update_jobs

                if len(update_jobs) > max_jobs:
                    sorted_jobs = sorted(
                        update_jobs.items(),
                        key=lambda item: item[1].get("created_at", ""),
                        reverse=True,
                    )
                    latest["update_jobs"] = dict(sorted_jobs[:max_jobs])

                self.metadata = latest
                self._save_metadata_unlocked()

    def get_update_job(self, job_id: str) -> Dict[str, object] | None:
        """读取更新任务状态"""
        with self._thread_lock:
            with self._file_lock():
                latest = self._load_metadata_unlocked()
                self.metadata = latest
                update_jobs = latest.get("update_jobs", {})
                job = update_jobs.get(job_id)
                if isinstance(job, dict):
                    return job
                return None

    def get_status(self) -> Dict[str, object]:
        """获取知识库状态信息"""
        with self._thread_lock:
            with self._file_lock():
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
