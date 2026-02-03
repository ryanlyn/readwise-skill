"""HTTP utilities with retry/backoff and rate-limit reporting."""

from __future__ import annotations

import random
import sys
import time
from dataclasses import dataclass
from typing import Iterable, Optional

import requests

RETRY_STATUSES = {429, 500, 502, 503, 504}
DEFAULT_TIMEOUT = 30
MAX_ATTEMPTS = 5
BACKOFF_BASE = 1.5
JITTER = 0.25


@dataclass
class RateLimitInfo:
    limit: Optional[int]
    remaining: Optional[int]
    reset: Optional[int]

    @classmethod
    def from_headers(cls, headers: requests.structures.CaseInsensitiveDict[str]) -> "RateLimitInfo":
        def _to_int(value: Optional[str]) -> Optional[int]:
            if value is None:
                return None
            try:
                return int(value)
            except ValueError:
                return None

        return cls(
            limit=_to_int(headers.get("X-RateLimit-Limit")),
            remaining=_to_int(headers.get("X-RateLimit-Remaining")),
            reset=_to_int(headers.get("X-RateLimit-Reset")),
        )


class APIRequestError(RuntimeError):
    pass


def _format_rate_limit_notice(headers: requests.structures.CaseInsensitiveDict[str]) -> str:
    info = RateLimitInfo.from_headers(headers)
    parts = []
    if info.limit is not None:
        parts.append(f"limit={info.limit}")
    if info.remaining is not None:
        parts.append(f"remaining={info.remaining}")
    if info.reset is not None:
        parts.append(f"reset={info.reset}")
    retry_after = headers.get("Retry-After")
    if retry_after:
        parts.append(f"retry_after={retry_after}")
    if not parts:
        return ""
    return "Rate limit headers: " + ", ".join(parts)


def request_with_backoff(
    session: requests.Session,
    method: str,
    url: str,
    *,
    max_attempts: int = MAX_ATTEMPTS,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs,
) -> requests.Response:
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.request(method.upper(), url, timeout=timeout, **kwargs)
            if response.status_code not in RETRY_STATUSES:
                response.raise_for_status()
                return response

            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    sleep_for = float(retry_after)
                except ValueError:
                    sleep_for = BACKOFF_BASE ** attempt
            else:
                sleep_for = BACKOFF_BASE ** attempt
            sleep_for += random.uniform(0, JITTER)
            rate_notice = _format_rate_limit_notice(response.headers)
            if rate_notice:
                print(
                    f"Throttled (HTTP {response.status_code}); backing off for {sleep_for:.2f}s. {rate_notice}",
                    file=sys.stderr,
                )
            time.sleep(sleep_for)
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            time.sleep(BACKOFF_BASE ** attempt + random.uniform(0, JITTER))
    if last_error is not None:
        raise APIRequestError(str(last_error))
    raise APIRequestError("Request failed after retries")
