from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .errors import ListingNotFound, PortalBlocked, RequestFailed

RequestFunction = Callable[..., Any]


def get_json(
    request: RequestFunction,
    url: str,
    *,
    headers: dict[str, str],
    timeout: float = 30,
    min_interval: float = 0,
    not_found_is_terminal: bool = False,
) -> dict[str, Any]:
    """Call a portal JSON GET endpoint through the caller's HTTP transport."""
    response = request(
        "GET", url, headers=dict(headers), json_body=None, timeout=timeout,
        min_interval=min_interval,
    )
    status = int(getattr(response, "status_code", 0) or 0)
    text = str(getattr(response, "text", "") or "")
    if status in {401, 403, 429}:
        raise PortalBlocked(f"http_{status}:{text[:200]}")
    if not_found_is_terminal and status == 404:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        message = str(payload.get("message") or payload.get("error") or text[:500]) if isinstance(payload, dict) else text[:500]
        raise ListingNotFound(message or "listing_not_found")
    if status >= 400:
        raise RequestFailed(f"http_{status}:{text[:500]}")
    try:
        payload = response.json()
    except Exception as error:
        raise RequestFailed(f"invalid_json:{error}") from error
    if not isinstance(payload, dict):
        raise RequestFailed("invalid_payload")
    return payload


def post_json(
    request: RequestFunction,
    url: str,
    body: dict[str, Any],
    *,
    headers: dict[str, str],
    timeout: float = 30,
    min_interval: float = 0,
    not_found_is_terminal: bool = False,
) -> dict[str, Any]:
    """Call a portal JSON endpoint through the caller's HTTP transport."""
    response = request(
        "POST", url, headers=dict(headers), json_body=body, timeout=timeout,
        min_interval=min_interval,
    )
    status = int(getattr(response, "status_code", 0) or 0)
    text = str(getattr(response, "text", "") or "")
    if status in {401, 403, 429}:
        raise PortalBlocked(f"http_{status}:{text[:200]}")
    if not_found_is_terminal and status in {404, 415, 422}:
        try:
            payload = response.json()
        except Exception:
            payload = {}
        message = str(payload.get("message") or payload.get("error") or text[:500]) if isinstance(payload, dict) else text[:500]
        raise ListingNotFound(message or f"listing_not_supported_http_{status}")
    if status >= 400:
        raise RequestFailed(f"http_{status}:{text[:500]}")
    try:
        payload = response.json()
    except Exception as error:
        raise RequestFailed(f"invalid_json:{error}") from error
    if not isinstance(payload, dict):
        raise RequestFailed("invalid_payload")
    return payload
