"""统一日志 — 仅输出到 stdout，由 Loki/Alloy 采集与检索。"""

from __future__ import annotations

import logging
import os


def setup_logging(name: str = "jnao", level: int | None = None) -> logging.Logger:
    """配置日志器：只打控制台（容器 stdout）。"""
    if level is None:
        level_name = (os.getenv("JNAO_LOG_LEVEL") or "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(fmt)
    logger.addHandler(console)
    logger.propagate = False
    return logger


def get_logger(name: str = "jnao") -> logging.Logger:
    """获取已配置的日志器，未配置则自动初始化。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        return setup_logging(name)
    return logger
