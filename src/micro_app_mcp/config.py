"""配置管理"""

import os
import warnings
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


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

    # 数据存储路径
    DATA_DIR: Path = Path(
        os.getenv("DATA_DIR", "~/work_space/tmp/micro_app_mcp")
    ).expanduser()

    # 智能缓存配置
    CACHE_DURATION_HOURS: int = int(os.getenv("CACHE_DURATION_HOURS", "24"))
    DISPLAY_TIMEZONE: str = os.getenv("DISPLAY_TIMEZONE", "Asia/Shanghai")

    # 向量数据库配置
    CHROMA_DB_PATH: Path = DATA_DIR / "chroma_db"
    METADATA_PATH: Path = DATA_DIR / "metadata.json"

    # GitHub 仓库配置
    GITHUB_REPO: str = "jd-opensource/micro-app"
    GITHUB_BRANCH: str = "master"

    # 文档 URL 配置
    DOCS_URL: str = "https://jd-opensource.github.io/micro-app/docs.html#/"


# 创建配置实例
config = Config()


def _ensure_data_dirs():
    """确保数据目录可写，不可写时回退到 /tmp。"""
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        config.CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
        return
    except Exception as e:
        fallback = Path(
            os.getenv("FALLBACK_DATA_DIR", "/tmp/micro_app_mcp")
        ).expanduser()
        warnings.warn(
            f"DATA_DIR 不可写，回退到 {fallback}。原错误: {e}",
            RuntimeWarning,
            stacklevel=2,
        )
        config.DATA_DIR = fallback
        config.CHROMA_DB_PATH = fallback / "chroma_db"
        config.METADATA_PATH = fallback / "metadata.json"
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        config.CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)


_ensure_data_dirs()
