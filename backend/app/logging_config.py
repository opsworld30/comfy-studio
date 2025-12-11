"""日志配置模块 - 滚动日志，错误日志单独输出"""
import logging
import os
from logging.handlers import RotatingFileHandler

# 日志目录
LOG_DIR = "./data/logs"

# 日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 滚动日志配置
MAX_BYTES = 10 * 1024 * 1024  # 10MB
BACKUP_COUNT = 5  # 保留5个备份


def setup_logging():
    """配置日志系统"""
    # 确保日志目录存在
    os.makedirs(LOG_DIR, exist_ok=True)
    
    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # 默认 INFO 级别
    
    # 清除已有的处理器
    root_logger.handlers.clear()
    
    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # 1. 控制台处理器 - WARNING 及以上（减少控制台输出）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 2. 应用日志文件处理器 - INFO 及以上（滚动）
    app_log_path = os.path.join(LOG_DIR, "app.log")
    app_handler = RotatingFileHandler(
        app_log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)
    root_logger.addHandler(app_handler)
    
    # 3. 错误日志文件处理器 - ERROR 及以上（滚动）
    error_log_path = os.path.join(LOG_DIR, "error.log")
    error_handler = RotatingFileHandler(
        error_log_path,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # 降低第三方库的日志级别 - 只记录 WARNING 及以上
    third_party_loggers = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "httpx",
        "httpcore",
        "websockets",
        "aiosqlite",
        "asyncio",
        "watchfiles",
    ]
    for logger_name in third_party_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # 应用内部日志 - INFO 级别（不需要太多 DEBUG）
    logging.getLogger("app").setLevel(logging.INFO)
    logging.getLogger("request").setLevel(logging.INFO)  # 请求日志记录 INFO
    
    # 自动迁移服务 - INFO 级别，方便查看迁移状态
    logging.getLogger("app.services.auto_migrate").setLevel(logging.INFO)
    logging.getLogger("app.services.image_storage").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志器"""
    return logging.getLogger(name)
