from __future__ import annotations

import os
import re
from collections.abc import Iterator
from datetime import date
from typing import Any
from urllib.parse import urlparse

from . import details, negotiations, pricing, search, similar, valuation
from . import condominiums
from .condominiums import CondoRow
from .details import ListingDetail
from .errors import PortalBlocked, RequestFailed
from .negotiations import CondoNegotiations, NegotiationQuery
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

    def similar_houses_data(self, body: dict[str, Any]) -> similar.SimilarHomesResult:
        """Fetch and normalize summary plus available/unavailable comparables."""
        payload = self.similar_houses(body)
        return similar.parse_similar_houses(payload)

    def listing_detail(self, listing_id: str) -> ListingDetail:
        """Fetch selected address and condominium fields for a listing."""
        return details.fetch_listing_detail(listing_id, request=self._request)

    def condo_negotiations(self, query: NegotiationQuery) -> CondoNegotiations:
        """Fetch sale/rent negotiation groups for a fully specified property."""
        return negotiations.fetch_condo_negotiations(query, request=self._request)

    def iter_condominiums(self, city: str, city_slug: str) -> Iterator[CondoRow]:
        """Yield the published condominium records for one city.

        Sitemap pages and condominium details are fetched lazily as the caller
        consumes the iterator. Network and portal errors stop iteration and are
        propagated so callers do not mistake a partial run for a complete one.
        """
        city_name = str(city or "").strip()
        slug = self._city_slug(city_slug)
        if not city_name:
            raise ValueError("city_is_required")
        for url, lastmod in self.iter_condominium_entries(slug):
            row = self.fetch_condominium(url, city=city_name, lastmod=lastmod)
            if row is not None:
                yield row

    def condominium_sitemaps(self) -> list[str]:
        """Fetch the sitemap index and return its condominium partitions."""
        index = self._get_text(condominiums.SITEMAP_INDEX)
        sitemap_urls = condominiums.sitemap_parts(
            self._validate_sitemap(index, "sitemapindex")
        )
        if not sitemap_urls:
            raise RequestFailed("condominium_sitemaps_not_found")
        return sitemap_urls

    def iter_condominium_entries(
        self, city_slug: str
    ) -> Iterator[tuple[str, date | None]]:
        """Yield `(page_url, lastmod)` for sitemap entries in one city.

        This lets applications select which pages to fetch and persist without
        making the library responsible for their scheduling or storage.
        """
        slug = self._city_slug(city_slug)
        for sitemap_url in self.condominium_sitemaps():
            sitemap_xml = self._validate_sitemap(
                self._get_text(sitemap_url), "urlset"
            )
            yield from condominiums.condo_entries(sitemap_xml, slug)

    def fetch_condominium(
        self, url: str, *, city: str, lastmod: date | None = None
    ) -> CondoRow | None:
        """Fetch and parse one condominium page, without controlling storage."""
        city_name = str(city or "").strip()
        if not city_name:
            raise ValueError("city_is_required")
        return condominiums.parse_condo_page(
            self.condominium_page(url), url, city=city_name, lastmod=lastmod
        )

    @staticmethod
    def _city_slug(city_slug: str) -> str:
        slug = str(city_slug or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError("city_slug_must_be_lowercase_hyphenated")
        return slug

    @staticmethod
    def _validate_sitemap(xml: str, root: str) -> str:
        opened = re.search(rf"<{root}(?:\s[^>]*)?>", xml, re.I)
        closed = re.search(rf"</{root}\s*>", xml, re.I)
        if opened is None or closed is None or opened.end() > closed.start():
            raise RequestFailed("invalid_sitemap_xml")
        return xml

    def _get_text(
        self,
        url: str,
        *,
        accept: str = "text/html,application/xhtml+xml,application/xml,text/xml",
        invalid_url_error: str = "portal_url_must_be_on_quintoandar_https_host",
        invalid_text_error: str = "invalid_text_response",
    ) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {
            "quintoandar.com.br", "www.quintoandar.com.br"
        } or parsed.port not in (None, 443) or parsed.username or parsed.password:
            raise ValueError(invalid_url_error)
        response = self._request(
            "GET", url,
            headers={
                "Accept": accept,
                "User-Agent": "Mozilla/5.0",
            },
            json_body=None,
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
            raise RequestFailed(invalid_text_error)
        return body

    def condominium_page(self, url: str) -> str:
        return self._get_text(
            url,
            accept="text/html,application/xhtml+xml",
            invalid_url_error="condominium_url_must_be_on_quintoandar_https_host",
            invalid_text_error="invalid_html_response",
        )
