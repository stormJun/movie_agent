import logging
import time
from typing import Any, Dict, Optional

from infrastructure.utils import format_kv


class EventLogger:
    """
    Small helper to emit compact, structured single-line logs with shared context.

    It keeps a per-request sequence counter and elapsed time to make flow logs easy
    to follow without repeating a large JSON payload for every event.
    """

    def __init__(
        self,
        logger: logging.Logger,
        prefix: str,
        *,
        base_fields: Optional[Dict[str, Any]] = None,
        include_seq: bool = True,
        include_elapsed: bool = True,
        started_at: Optional[float] = None,
        stacklevel: int = 3,
    ) -> None:
        self._logger = logger
        self._prefix = prefix
        self._base_fields: Dict[str, Any] = dict(base_fields or {})
        self._include_seq = include_seq
        self._include_elapsed = include_elapsed
        self._started_at = started_at if started_at is not None else time.time()
        self._seq = 0
        self._stacklevel = stacklevel

    def set(self, **fields: Any) -> None:
        self._base_fields.update({k: v for k, v in fields.items() if v is not None})

    def info(self, event: str, **fields: Any) -> None:
        self._log(logging.INFO, event, **fields)

    def debug(self, event: str, **fields: Any) -> None:
        self._log(logging.DEBUG, event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self._log(logging.WARNING, event, **fields)

    def exception(self, event: str, **fields: Any) -> None:
        """
        Log an ERROR level message and include the current exception traceback.
        """
        self._log(logging.ERROR, event, exc_info=True, **fields)

    def _log(self, level: int, event: str, exc_info: bool = False, **fields: Any) -> None:
        self._seq += 1
        payload: Dict[str, Any] = {}
        if self._include_seq:
            payload["seq"] = self._seq
        payload["event"] = event
        if self._include_elapsed:
            payload["total_elapsed_seconds"] = round(time.time() - self._started_at, 4)
        payload.update(self._base_fields)
        payload.update({k: v for k, v in fields.items() if v is not None})

        self._logger.log(
            level,
            "%s %s",
            self._prefix,
            format_kv(**payload),
            exc_info=exc_info,
            stacklevel=self._stacklevel,
        )
