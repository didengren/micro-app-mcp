"""元数据管理"""

import json
from datetime import datetime, timedelta, timezone
from typing import Dict
from zoneinfo import ZoneInfo

from micro_app_mcp.config import config


class MetadataManager:
    """元数据管理器
    
    存储版本信息和更新时间
    """
    
    def __init__(self):
        """初始化"""
        self.metadata_path = config.METADATA_PATH
        self.metadata = self._load_metadata()
        self.display_tz = self._resolve_display_timezone()
    
    def _load_metadata(self) -> dict:
        """加载元数据
        
        Returns:
            元数据字典
        """
        if self.metadata_path.exists():
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    return self._get_default_metadata()
        else:
            return self._get_default_metadata()
    
    def _get_default_metadata(self) -> dict:
        """获取默认元数据
        
        Returns:
            默认元数据字典
        """
        return {
            "version": "1.0.0",
            "last_updated": "1970-01-01T00:00:00Z",
            "github_commit": "",
            "docs_hash": ""
        }
    
    def save_metadata(self):
        """保存元数据"""
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def update_metadata(self):
        """更新元数据"""
        self.metadata["last_updated"] = self._format_utc(datetime.now(timezone.utc))
        self.save_metadata()
    
    def should_skip_update(self) -> bool:
        """检查是否应该跳过更新
        
        Returns:
            是否应该跳过更新
        """
        last_updated = self._parse_last_updated()
        
        # 检查是否在缓存时间内
        cache_duration = timedelta(hours=config.CACHE_DURATION_HOURS)
        return datetime.now(timezone.utc) - last_updated < cache_duration
    
    def get_last_updated(self) -> str:
        """获取最后更新时间
        
        Returns:
            最后更新时间
        """
        return self.metadata.get("last_updated", "1970-01-01T00:00:00Z")

    def _parse_last_updated(self) -> datetime:
        """解析最后更新时间，异常时回退为 epoch"""
        last_updated_str = self.metadata.get("last_updated", "1970-01-01T00:00:00Z")
        try:
            normalized = last_updated_str.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    def _resolve_display_timezone(self):
        """解析展示时区，异常时回退到 UTC"""
        try:
            return ZoneInfo(config.DISPLAY_TIMEZONE)
        except Exception:
            return timezone.utc

    def _format_utc(self, value: datetime) -> str:
        """格式化 UTC 时间字符串"""
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )

    def _format_local(self, value: datetime) -> str:
        """格式化本地展示时间字符串"""
        return value.astimezone(self.display_tz).isoformat(timespec="seconds")

    def get_status(self) -> Dict[str, object]:
        """获取知识库状态信息"""
        now = datetime.now(timezone.utc)
        last_updated = self._parse_last_updated()
        age_delta = now - last_updated
        cache_duration = timedelta(hours=config.CACHE_DURATION_HOURS)
        next_update = last_updated + cache_duration

        return {
            "timezone": getattr(self.display_tz, "key", str(self.display_tz)),
            "last_updated": self._format_local(last_updated),
            "last_updated_utc": self._format_utc(last_updated),
            "cache_duration_hours": config.CACHE_DURATION_HOURS,
            "age_seconds": int(age_delta.total_seconds()),
            "should_skip_update": age_delta < cache_duration,
            "is_stale": age_delta >= cache_duration,
            "next_recommended_update_at": self._format_local(next_update),
            "next_recommended_update_at_utc": self._format_utc(next_update),
        }
