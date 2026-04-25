import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging for the application.

    Call once at startup in main.py. All modules then use get_logger(__name__).
    Logs go to stdout so Docker captures them with `docker compose logs`.
    """
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]

    # Apply same handler/format to uvicorn loggers so all lines look identical
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False

    # Quieten noisy third-party libs
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger.  Usage: logger = get_logger(__name__)"""
    return logging.getLogger(name)
