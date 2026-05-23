import json
import logging
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = {k: v for k, v in record.__dict__.items()
                 if k not in logging.LogRecord.__dict__ and not k.startswith("_")}
        payload.update(extra)
        return json.dumps(payload)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
