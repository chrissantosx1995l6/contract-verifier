import time
import httpx
from typing import Any, Optional


class HttpClient:
    """Thin wrapper around httpx.Client with retries and default headers."""

    def __init__(
        self,
        base_url: str = "",
        timeout: float = 10.0,
        max_retries: int = 0,
        backoff_factor: float = 0.3,
        default_headers: Optional[dict[str, str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.backoff_factor = backoff_factor
        self.default_headers = default_headers or {}
        self._client = httpx.Client(
            timeout=self.timeout,
            follow_redirects=False,
        )

    def request(
        self,
        method: str,
        path: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}" if self.base_url else path
        merged_headers = {**self.default_headers, **(headers or {})}

        attempts = 0
        while True:
            try:
                resp = self._client.request(
                    method=method,
                    url=url,
                    headers=merged_headers,
                    params=params,
                    json=json_body,
                )
                # retry on transient gateway errors or rate limits if configured
                if attempts < self.max_retries and resp.status_code in (429, 502, 503, 504):
                    attempts += 1
                    time.sleep(self.backoff_factor * (2 ** (attempts - 1)))
                    continue
                return resp
            except (httpx.ConnectError, httpx.ReadTimeout) as err:
                if attempts >= self.max_retries:
                    raise err
                attempts += 1
                time.sleep(self.backoff_factor * (2 ** (attempts - 1)))

    def close(self) -> None:
        self._client.close()
