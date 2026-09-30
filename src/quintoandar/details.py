from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from .errors import RequestFailed
from .transport import RequestFunction, get_json

DETAILS_URL = "https://www.quintoandar.com.br/property/v2/{listing_id}"
HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.quintoandar.com.br",
    "Referer": "https://www.quintoandar.com.br/",
    "User-Agent": "Mozilla/5.0",
}


@dataclass(frozen=True)
class ListingDetail:
    """Selected condominium fields returned by the portal listing detail."""

    listing_id: str
    condo_id: str | None
    condo_slug: str | None
    street_number: str | None
    condominium: float | None
    iptu: float | None


def details_url(listing_id: str) -> str:
    identifier = str(listing_id or "").strip()
    if not identifier:
        raise ValueError("listing_id_is_required")
    return DETAILS_URL.format(listing_id=quote(identifier, safe="")) + (
        "?variant=0&showPartnerId=true&condoPageValidation=false"
    )


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def parse_listing_detail(payload: Any, listing_id: str) -> ListingDetail:
    if not isinstance(payload, dict):
        raise RequestFailed("invalid_listing_detail_payload")
    condo = payload.get("condominium")
    condo = condo if isinstance(condo, dict) else {}
    return ListingDetail(
        listing_id=str(listing_id).strip(),
        condo_id=_text(condo.get("hashId")),
        condo_slug=_text(condo.get("slug")),
        street_number=_text(condo.get("number")),
        condominium=_number(payload.get("condominiumValue")),
        iptu=_number(payload.get("iptuValue")),
    )


def fetch_listing_detail(
    listing_id: str, *, request: RequestFunction
) -> ListingDetail:
    identifier = str(listing_id or "").strip()
    payload = get_json(
        request,
        details_url(identifier),
        headers=HEADERS,
        timeout=30,
        not_found_is_terminal=True,
    )
    return parse_listing_detail(payload, identifier)
