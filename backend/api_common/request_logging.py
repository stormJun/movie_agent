from __future__ import annotations

import logging
import time

from fastapi import Request
from fastapi.routing import APIRoute


def _extract_request_id(request: Request) -> str:
    candidates = (
        request.headers.get("x-request-id"),
        request.headers.get("x-trace-id"),
        request.query_params.get("request_id"),
    )
    for value in candidates:
        if value:
            return str(value)
    return "-"


class _RequestLoggingRoute(APIRoute):
    channel = "unknown"
    logger_name = "api.request"

    def get_route_handler(self):
        original_handler = super().get_route_handler()
        logger = logging.getLogger(self.logger_name)
        channel = self.channel

        async def custom_route_handler(request: Request):
            started = time.perf_counter()
            method = request.method
            path = request.url.path
            client = request.client.host if request.client else "-"
            request_id = _extract_request_id(request)

            try:
                response = await original_handler(request)
            except Exception:
                duration_ms = (time.perf_counter() - started) * 1000
                logger.exception(
                    "http_request_failed channel=%s method=%s path=%s duration_ms=%.2f request_id=%s client=%s",
                    channel,
                    method,
                    path,
                    duration_ms,
                    request_id,
                    client,
                )
                raise

            duration_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "http_request channel=%s method=%s path=%s status_code=%s duration_ms=%.2f request_id=%s client=%s",
                channel,
                method,
                path,
                response.status_code,
                duration_ms,
                request_id,
                client,
            )
            return response

        return custom_route_handler


class AdminRequestLoggingRoute(_RequestLoggingRoute):
    channel = "admin"
    logger_name = "api.request.admin"


class MiniProgramRequestLoggingRoute(_RequestLoggingRoute):
    channel = "miniprogram"
    logger_name = "api.request.miniprogram"

