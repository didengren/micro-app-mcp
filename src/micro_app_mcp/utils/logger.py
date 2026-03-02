"""日志工具"""

import logging
import sys
from logging.handlers import RotatingFileHandler

from micro_app_mcp.config import config


def setup_logging():
    """配置全局日志系统"""
    # 确保日志目录存在
    log_dir = config.DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            # 使用 RotatingFileHandler 替代 FileHandler
            # maxBytes=1MB, backupCount=3 (最多保留 3 个备份文件，防止日志无限增长)
            RotatingFileHandler(
                log_dir / "micro_app_mcp.log", maxBytes=1 * 1024 * 1024, backupCount=3, encoding="utf-8"
            ),
            logging.StreamHandler(sys.stderr),  # MCP Server 必须输出到 stderr，不能污染 stdout
        ],
        force=True,
    )
