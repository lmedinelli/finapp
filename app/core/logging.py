import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(level: str = "INFO", log_file_path: str = "data/logs/app.log") -> None:
    Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        filename=log_file_path,
        maxBytes=5_000_000,
        backupCount=3,
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        handlers=[stream_handler, file_handler],
        force=True,
    )
    # Avoid leaking query-string secrets (e.g., API keys) in httpx request logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
