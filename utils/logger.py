import sys
from pathlib import Path
from loguru import logger

def setup_logger(log_level: str = "INFO", log_dir: str = "storage/logs") -> None:
    """Configures the Loguru logger for console and rotating file output with UTF-8 encoding."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    logger.remove()

    logger.add(
        sys.stdout,
        level=log_level,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    logger.add(
        log_path / "bot_{time:YYYY-MM-DD}.log",
        level=log_level,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
    )

__all__ = ["setup_logger", "logger"]
