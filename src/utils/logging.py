import json
import logging
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        _SKIP = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = {k: v for k, v in record.__dict__.items()
                 if k not in _SKIP and not k.startswith("_")}
        payload.update(extra)
        return json.dumps(payload)


class _KwLogger:
    """Thin wrapper that accepts structlog-style keyword args: log.info("msg", key=val)."""

    def __init__(self, logger: logging.Logger) -> None:
        self._log = logger

    def _emit(self, level: int, msg: str, **kwargs: object) -> None:
        self._log.log(level, msg, extra=kwargs)

    def debug(self, msg: str, **kwargs: object) -> None:
        self._emit(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs: object) -> None:
        self._emit(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs: object) -> None:
        self._emit(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs: object) -> None:
        self._emit(logging.ERROR, msg, **kwargs)

    def exception(self, msg: str, **kwargs: object) -> None:
        self._log.exception(msg, extra=kwargs)


def get_logger(name: str) -> _KwLogger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return _KwLogger(logger)
