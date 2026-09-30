from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .errors import RequestFailed
from .transport import RequestFunction, post_json

API_URL = "https://apigw.prod.quintoandar.com.br/house-listing-search/v3/search/list"
PAGE_SIZE = 500
RESULT_CAP = 1000
MIN_INTERVAL_SECONDS = float(os.getenv("QUINTOANDAR_SEARCH_MIN_INTERVAL_SECONDS", "0.35"))
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.quintoandar.com.br",
    "User-Agent": "Mozilla/5.0",
}
FIELDS = (
    "id", "salePrice", "totalCost", "iptuPlusCondominium", "area", "address",
    "regionName", "city", "neighbourhood", "type", "forSale", "location",
    "bedrooms", "bathrooms", "suites", "parkingSpaces", "isPrimaryMarket",
    "condoId", "condoName", "iptu", "condominium",
)
HOUSE_TYPE = {"CASA": "Casa", "APARTAMENTO": "Apartamento"}


@dataclass(frozen=True)
class SearchQuery:
    city: str
    state: str
    neighborhood: str | None = None
    property_type: str | None = None
    bedrooms: int | None = None
    area_m2: float | None = None


@dataclass(frozen=True)
class Listing:
    listing_id: str
    url: str
    state: str
    city: str
    neighborhood: str | None
    street: str | None
    property_type: str | None
    bedrooms: int | None
    bathrooms: int | None
    suites: int | None
    parking_spaces: int | None
    area_m2: float | None
    price: float
    latitude: float | None
    longitude: float | None
    condo_id: str | None
    condo_name: str | None
    condominium: float | None
    iptu: float | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class SearchResult:
    listings: list[Listing]
    success: bool
    partial: bool
    pages: int
    total: int | None
    error: str | None = None


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", normalized.lower())).strip("-")


def _number(value: Any, *, positive: bool = False, negative: bool = False) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number if (negative or number >= 0) and (not positive or number > 0) else None


def _text(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def _property_type(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if "CASA" in text or "HOUSE" in text or text == "HOME":
        return "CASA"
    if any(token in text for token in ("APART", "STUDIO", "KITNET", "COBERTURA", "FLAT", "LOFT")):
        return "APARTAMENTO"
    return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if not any(token in str(key).lower() for token in ("contact", "phone", "whatsapp", "email", "advertiser"))
            and not _looks_sensitive(item)
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value if not _looks_sensitive(item)]
    return value


def _looks_sensitive(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", text):
        return True
    digits = re.sub(r"\D", "", text)
    return len(digits) in range(10, 14) and len(digits) == len(re.sub(r"[+().\-\s]", "", text))


def _house_specs(query: SearchQuery, requested_type: str | None) -> dict[str, Any]:
    specs: dict[str, Any] = {
        "area": {"range": {}},
        "houseTypes": [HOUSE_TYPE[requested_type]] if requested_type else [],
        "amenities": [], "installations": [], "bathrooms": {"range": {}},
        "bedrooms": {"range": {}}, "parkingSpace": {"range": {}}, "suites": {"range": {}},
    }
    if query.bedrooms is not None:
        specs["bedrooms"] = {"range": {"min": query.bedrooms, "max": query.bedrooms}}
    if query.area_m2 is not None:
        specs["area"] = {"range": {"min": query.area_m2, "max": query.area_m2}}
    return specs


def _payload(query: SearchQuery, page_size: int, offset: int) -> dict[str, Any]:
    place = f"{_slug(query.neighborhood)}-" if query.neighborhood else ""
    description = f"{place}{_slug(query.city)}-{query.state.lower()}-brasil"
    requested_type = _property_type(query.property_type)
    if query.property_type and not requested_type:
        raise ValueError("unsupported_property_type")
    return {
        "slug": description, "topics": [], "fields": list(FIELDS),
        "sorting": {"criteria": "RELEVANCE", "order": "DESC"},
        "pagination": {"pageSize": page_size, "offset": offset},
        "context": {"listShowing": True, "mapShowing": False, "numPhotos": 0, "isSSR": False},
        "filters": {
            "unknownSlugs": [], "enableFlexibleSearch": True, "businessContext": "SALE",
            "priceRange": [], "availability": "ANY", "occupancy": "ANY", "partnerIds": [],
            "specialConditions": [], "excludedSpecialConditions": [], "blocklist": [],
            "selectedHouses": [], "categories": [], "houseSpecs": _house_specs(query, requested_type),
            "origin": "HYBRID",
        },
        "locationDescriptions": [{"description": description}],
    }


def _total(value: Any) -> int | None:
    if isinstance(value, dict):
        if str(value.get("relation", "")).lower() == "gte":
            return None
        value = value.get("value")
    return _integer(value)


def _rows(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int | None]:
    hits = payload.get("hits")
    rows = hits.get("hits") if isinstance(hits, dict) else None
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise RequestFailed("invalid_payload_structure")
    values = [row.get("_source", row) for row in rows]
    if any(not isinstance(row, dict) for row in values):
        raise RequestFailed("invalid_payload_structure")
    return values, _total(hits.get("total"))


def _listing(row: dict[str, Any], query: SearchQuery) -> Listing | None:
    identifier = _text(row.get("id"))
    price = _number(row.get("salePrice"), positive=True)
    if not identifier or price is None:
        return None
    location = row.get("location") if isinstance(row.get("location"), dict) else {}
    return Listing(
        listing_id=identifier,
        url=f"https://www.quintoandar.com.br/imovel/{identifier}/comprar",
        state=_text(row.get("state")) or query.state,
        city=_text(row.get("city")) or query.city,
        neighborhood=_text(row.get("neighbourhood") or row.get("regionName")),
        street=_text(row.get("address")),
        property_type=_property_type(row.get("type")),
        bedrooms=_integer(row.get("bedrooms")),
        bathrooms=_integer(row.get("bathrooms")),
        suites=_integer(row.get("suites")),
        parking_spaces=_integer(row.get("parkingSpaces")),
        area_m2=_number(row.get("area"), positive=True),
        price=price,
        latitude=_number(location.get("lat"), negative=True),
        longitude=_number(location.get("lon"), negative=True),
        condo_id=_text(row.get("condoId")), condo_name=_text(row.get("condoName")),
        condominium=_number(row.get("condominium"), positive=True),
        iptu=_number(row.get("iptu"), positive=True), raw=_sanitize(row),
    ) if _property_type(row.get("type")) else None


def parse_record(row: dict[str, Any], query: SearchQuery) -> Listing | None:
    """Parse one raw search record, returning None when it is not a listing."""
    if not isinstance(row, dict):
        return None
    return _listing(row, query)


def search_listings(
    query: SearchQuery,
    *,
    request: RequestFunction,
    max_pages: int = 100,
    api_url: str = API_URL,
) -> SearchResult:
    """Search a location and return normalized listings plus completeness."""
    limit = max(1, max_pages or 100)
    listings: list[Listing] = []
    seen: set[str] = set()
    pages = 0
    attempted = False
    total: int | None = None
    try:
        for page in range(limit):
            offset = page * PAGE_SIZE
            page_size = min(PAGE_SIZE, RESULT_CAP - offset)
            if page_size <= 0:
                return SearchResult(listings, False, True, pages, total, "result_cap_reached")
            attempted = True
            payload = post_json(
                request, api_url, _payload(query, page_size, offset), headers=HEADERS,
                timeout=25, min_interval=MIN_INTERVAL_SECONDS,
            )
            rows, reported_total = _rows(payload)
            pages += 1
            if reported_total is not None:
                total = reported_total if total is None else max(total, reported_total)
            for row in rows:
                item = _listing(row, query)
                if item and item.listing_id not in seen:
                    seen.add(item.listing_id)
                    listings.append(item)
            if not rows or len(rows) < page_size or (total is not None and offset + len(rows) >= total):
                return SearchResult(listings, True, False, pages, total)
            if offset + page_size >= RESULT_CAP:
                return SearchResult(listings, False, True, pages, total, "result_cap_reached")
        return SearchResult(listings, False, True, pages, total, "max_pages_reached")
    except Exception as error:
        return SearchResult(listings, False, attempted, pages, total, str(error))
