from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

from app.config import HTTP_CONCURRENCY, HTTP_MAX_RETRIES, HTTP_TIMEOUT_SECONDS


class RetryHttpClient:
    def __init__(
        self,
        *,
        timeout: float = HTTP_TIMEOUT_SECONDS,
        max_retries: int = HTTP_MAX_RETRIES,
        concurrency: int = HTTP_CONCURRENCY,
    ) -> None:
        self._timeout = timeout
        self._max_retries = max_retries
        self._semaphore = asyncio.Semaphore(concurrency)
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def close(self) -> None:
        await self._client.aclose()

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        async with self._semaphore:
            return await self._request_json("GET", url, params=params, headers=headers)

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await self._client.request(method, url, params=params, headers=headers)
                if response.status_code in {429, 500, 502, 503, 504} and attempt < self._max_retries:
                    retry_after = response.headers.get("Retry-After")
                    sleep_seconds = _retry_sleep_seconds(attempt, retry_after=retry_after)
                    await asyncio.sleep(sleep_seconds)
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt >= self._max_retries:
                    break
                await asyncio.sleep(_retry_sleep_seconds(attempt))
        assert last_error is not None
        raise last_error


def _retry_sleep_seconds(attempt: int, retry_after: str | None = None) -> float:
    if retry_after:
        try:
            return max(0.5, min(10.0, float(retry_after)))
        except ValueError:
            pass
    base = 0.5 * (2**attempt)
    jitter = random.uniform(0.0, 0.2)
    return min(10.0, base + jitter)

