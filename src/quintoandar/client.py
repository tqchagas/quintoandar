from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from . import pricing, search, similar, valuation
from .errors import PortalBlocked, RequestFailed
from .transport import RequestFunction


class QuintoAndarClient:
    """Read-only QuintoAndar client. The caller owns HTTP pacing and retries.

    `request` is a callable accepting `(method, url, *, headers, json_body,
    timeout, min_interval)` and returning a response with `status_code`,
    `text`, and `json()`. Injecting it lets applications share their own
    transport policies without giving this package application dependencies.
    """

    def __init__(self, request: RequestFunction, *, price_suggestion_cookie: str = "") -> None:
        self._request = request
        self._price_suggestion_cookie = price_suggestion_cookie

    def search_listings(
        self, query: search.SearchQuery, *, max_pages: int = 100, api_url: str = search.API_URL
    ) -> search.SearchResult:
        return search.search_listings(query, request=self._request, max_pages=max_pages, api_url=api_url)

    def price_suggestion(self, listing_id: str) -> dict[str, Any]:
        return pricing.fetch_price_suggestion(
            listing_id, request=self._request, cookie=self._price_suggestion_cookie
        )

    def estimate(self, value: valuation.EstimateInput) -> valuation.Estimate:
        return valuation.fetch_estimate(value, request=self._request)

    def comparables(
        self, value: valuation.EstimateInput, estimate: valuation.Estimate
    ) -> valuation.Comparables:
        return valuation.fetch_comparables(value, estimate, request=self._request)

    def similar_houses(self, body: dict[str, Any]) -> dict[str, Any]:
        return similar.fetch_similar_houses(body, request=self._request)

    def condominium_page(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "quintoandar.com.br", "www.quintoandar.com.br"
        } or parsed.port not in (None, 443) or parsed.username or parsed.password:
            raise ValueError("condominium_url_must_be_on_quintoandar_https_host")
        response = self._request(
            "GET", url,
            headers={"Accept": "text/html,application/xhtml+xml", "User-Agent": "Mozilla/5.0"},
            timeout=(15, 60),
            min_interval=float(os.getenv("CONDO_MIN_INTERVAL_SECONDS", "1.0")),
        )
        status = int(getattr(response, "status_code", 0) or 0)
        if status in {401, 403, 429}:
            raise PortalBlocked(f"http_{status}")
        if status >= 400:
            raise RequestFailed(f"http_{status}")
        body = getattr(response, "text", None)
        if not isinstance(body, str):
            raise RequestFailed("invalid_html_response")
        return body
