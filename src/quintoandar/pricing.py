from __future__ import annotations

import json
import os
from typing import Any

from .errors import ListingNotFound
from .transport import RequestFunction, post_json

URL = "https://apigw.prod.quintoandar.com.br/customer-facing-bff-api/pricing-reports/v1/price-suggestion"
MIN_INTERVAL_SECONDS = float(os.getenv("QPRECO_MIN_INTERVAL_SECONDS", "3.0"))
HEADERS = {
    "accept": "application/json", "content-type": "application/json",
    "origin": "https://www.quintoandar.com.br", "referer": "https://www.quintoandar.com.br/",
}


def price_suggestion_headers(cookie: str = "") -> dict[str, str]:
    headers = dict(HEADERS)
    raw_cookie = cookie.strip()
    if raw_cookie:
        headers["cookie"] = f"5AJWT_AUTH={raw_cookie}" if "=" not in raw_cookie else raw_cookie
    return headers


def price_suggestion_body(listing_id: str) -> dict[str, str]:
    identifier = str(listing_id or "").strip()
    if not identifier:
        raise ValueError("listing_id is required")
    return {"businessContext": "sale", "id": identifier}


def fetch_price_suggestion(
    listing_id: str,
    *,
    request: RequestFunction,
    cookie: str = "",
    url: str = URL,
) -> dict[str, Any]:
    """Return the portal's price suggestion for one QuintoAndar listing id."""
    identifier = str(listing_id or "").strip()
    body = price_suggestion_body(identifier)
    try:
        return post_json(
            request, url, body, headers=price_suggestion_headers(cookie),
            timeout=30, min_interval=MIN_INTERVAL_SECONDS, not_found_is_terminal=True,
        )
    except ListingNotFound as error:
        raise ListingNotFound(f"listing {identifier}: {error}") from error


def extract_price_suggestion(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}

    def number(value: Any) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if result > 0 else None

    return {
        "price_suggestion_json": json.dumps(data, ensure_ascii=False),
        "price_suggestion_lower_bound": number(data.get("suggestedLowerBoundPrice")),
        "price_suggestion_price": number(data.get("suggestedPrice")),
        "price_suggestion_upper_bound": number(data.get("suggestedUpperBoundPrice")),
    }
