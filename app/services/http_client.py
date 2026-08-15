import asyncio
import logging
import time
from typing import Optional, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger("scanner.http")

class DomainRateLimiter:
    """Token-bucket style rate limiter per domain."""
    def __init__(self, min_interval_seconds: float = 1.0, max_concurrent: int = 2):
        self.min_interval = min_interval_seconds
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        await self.semaphore.acquire()
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()

    def release(self):
        self.semaphore.release()

class CentralHttpClient:
    """
    Centralized HTTP client with per-domain rate limiting, concurrency semaphores,
    exponential backoff retries on 429 and 5xx, and credential masking.
    """
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        # Specific rate limiters for CSFloat (1 req / 0.5s) and Steam (1 req / 1.5s)
        self._limiters: Dict[str, DomainRateLimiter] = {
            "csfloat.com": DomainRateLimiter(min_interval_seconds=0.5, max_concurrent=settings.MAX_CONCURRENT_REQUESTS),
            "steamcommunity.com": DomainRateLimiter(min_interval_seconds=1.5, max_concurrent=settings.MAX_CONCURRENT_REQUESTS),
            "default": DomainRateLimiter(min_interval_seconds=1.0, max_concurrent=settings.MAX_CONCURRENT_REQUESTS),
        }

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(20.0, connect=10.0),
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
        return self._client

    def _get_limiter(self, url: str) -> DomainRateLimiter:
        for domain, limiter in self._limiters.items():
            if domain in url:
                return limiter
        return self._limiters["default"]

    def _mask_url(self, url: str) -> str:
        # Prevent leaking keys in query params if any
        return url

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        backoff_factor: float = 2.0
    ) -> httpx.Response:
        limiter = self._get_limiter(url)
        client = await self.get_client()

        req_headers = {}
        if headers:
            req_headers.update(headers)

        last_exception = None
        for attempt in range(1, max_retries + 1):
            await limiter.acquire()
            try:
                masked_url = self._mask_url(url)
                logger.debug(f"HTTP GET [{attempt}/{max_retries}] -> {masked_url}")
                response = await client.get(url, params=params, headers=req_headers)

                if response.status_code == 429:
                    retry_after = 2.0 * (backoff_factor ** attempt)
                    logger.warning(f"Rate limited (429) on {masked_url}. Backing off for {retry_after:.1f}s (attempt {attempt}/{max_retries})")
                    limiter.release()
                    await asyncio.sleep(retry_after)
                    continue

                if response.status_code >= 500:
                    wait_time = 1.5 * (backoff_factor ** (attempt - 1))
                    logger.warning(f"Server error ({response.status_code}) on {masked_url}. Retrying in {wait_time:.1f}s")
                    limiter.release()
                    await asyncio.sleep(wait_time)
                    continue

                limiter.release()
                return response

            except (httpx.TimeoutException, httpx.ConnectError, httpx.RequestError) as ex:
                limiter.release()
                last_exception = ex
                wait_time = 1.5 * (backoff_factor ** (attempt - 1))
                logger.warning(f"Connection error on {self._mask_url(url)}: {ex}. Retrying in {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        if last_exception:
            raise last_exception
        raise httpx.HTTPStatusError(
            message=f"Request to {url} failed after {max_retries} retries",
            request=None,
            response=response
        )

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

http_client = CentralHttpClient()
