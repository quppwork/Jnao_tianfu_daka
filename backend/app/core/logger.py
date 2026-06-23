"""统一日志系统 — 控制台 + 文件，自动轮转"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "app.log"
MAX_BYTES = 5 * 1024 * 1024  # 5MB per file
BACKUP_COUNT = 3

def setup_logging(name: str = "jnao", level: int = logging.INFO) -> logging.Logger:
    """配置日志器：控制台输出 + 文件轮转"""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # 已经配置过

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 文件轮转
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger

def get_logger(name: str = "jnao") -> logging.Logger:
    """获取已配置的日志器，未配置则自动初始化"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logging(name)
    return logger
