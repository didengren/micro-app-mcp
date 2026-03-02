"""日志工具"""

import logging

from micro_app_mcp.config import config

# 确保日志目录存在
log_dir = config.DATA_DIR / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "micro_app_mcp.log"),
        logging.StreamHandler()
    ]
)


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        日志记录器实例
    """
    return logging.getLogger(name)


# 默认日志记录器
logger = get_logger("micro_app_mcp")
