"""配置管理"""

import os
import tempfile
import warnings
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def _parse_csv_env(name: str, default: str) -> Tuple[str, ...]:
    """解析逗号分隔环境变量"""
    raw = os.getenv(name, default)
    return tuple(item.strip() for item in raw.split(",") if item.strip())


class Config:
    """配置类"""

    # 向量化模型配置
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "local")
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "BAAI/bge-small-zh-v1.5"
    )
    EMBEDDING_LAZY_LOAD: bool = (
        os.getenv("EMBEDDING_LAZY_LOAD", "true").lower() == "true"
    )

    # GitHub 配置
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN")
    GITHUB_HTTP_TIMEOUT_SECONDS: int = int(
        os.getenv("GITHUB_HTTP_TIMEOUT_SECONDS", "15")
    )
    GITHUB_RETRY_TOTAL: int = int(os.getenv("GITHUB_RETRY_TOTAL", "0"))

    # 数据存储路径
    DATA_DIR: Path = Path(
        os.getenv("DATA_DIR", "~/work_space/tmp/micro_app_mcp")
    ).expanduser()

    # 智能缓存配置
    CACHE_DURATION_HOURS: int = int(os.getenv("CACHE_DURATION_HOURS", "24"))
    SEARCH_TIMEOUT_SECONDS: int = int(os.getenv("SEARCH_TIMEOUT_SECONDS", "30"))
    UPDATE_MAX_DURATION_SECONDS: int = int(
        os.getenv("UPDATE_MAX_DURATION_SECONDS", "600")
    )
    CHROMA_ANONYMIZED_TELEMETRY: bool = (
        os.getenv("CHROMA_ANONYMIZED_TELEMETRY", "false").lower() == "true"
    )

    # /micro 更新意图识别规则（支持环境变量覆盖）
    UPDATE_INTENT_ACTION_KEYWORDS: Tuple[str, ...] = _parse_csv_env(
        "UPDATE_INTENT_ACTION_KEYWORDS",
        "更新,同步,重建,刷新,update,refresh,rebuild,sync",
    )
    UPDATE_INTENT_TARGET_KEYWORDS: Tuple[str, ...] = _parse_csv_env(
        "UPDATE_INTENT_TARGET_KEYWORDS",
        "知识库,向量库,索引,vector,embedding,index,db,database",
    )
    UPDATE_INTENT_SEARCH_ONLY_PATTERNS: Tuple[str, ...] = _parse_csv_env(
        "UPDATE_INTENT_SEARCH_ONLY_PATTERNS",
        "更新日志,changelog,release note,release notes,版本更新,最新更新",
    )

    # 向量数据库配置
    CHROMA_DB_PATH: Path = DATA_DIR / "chroma_db"
    METADATA_PATH: Path = DATA_DIR / "metadata.json"
    DATA_DIR_SOURCE: str = "data_dir"

    # GitHub 仓库配置
    GITHUB_REPO: str = "jd-opensource/micro-app"
    GITHUB_BRANCH: str = "master"

    # 文档 URL 配置
    DOCS_URL: str = "https://jd-opensource.github.io/micro-app/docs.html#/"


# 创建配置实例
config = Config()


def _prepare_data_dir(data_dir: Path) -> None:
    """创建数据目录及其子目录。"""
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "chroma_db").mkdir(parents=True, exist_ok=True)


def _ensure_data_dirs():
    """确保数据目录可写，按候选链依次回退。"""
    fallback = Path(os.getenv("FALLBACK_DATA_DIR", "/tmp/micro_app_mcp")).expanduser()
    system_temp = Path(tempfile.gettempdir()) / "micro_app_mcp"
    candidates = [
        ("data_dir", config.DATA_DIR),
        ("fallback_data_dir", fallback),
        ("system_temp", system_temp),
    ]

    errors: list[str] = []
    seen = set()
    for source, candidate in candidates:
        normalized = candidate.expanduser()
        dedup_key = str(normalized)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        try:
            _prepare_data_dir(normalized)
            config.DATA_DIR = normalized
            config.CHROMA_DB_PATH = normalized / "chroma_db"
            config.METADATA_PATH = normalized / "metadata.json"
            config.DATA_DIR_SOURCE = source

            if source != "data_dir":
                warnings.warn(
                    f"DATA_DIR 不可写，已回退到 {normalized}（来源: {source}）。",
                    RuntimeWarning,
                    stacklevel=2,
                )
            return
        except Exception as e:
            errors.append(f"{source}:{normalized} -> {e}")

    attempted = "; ".join(errors) if errors else "无候选目录"
    raise RuntimeError(
        f"数据目录初始化失败，尝试过的目录均不可写：{attempted}"
    )


_ensure_data_dirs()
