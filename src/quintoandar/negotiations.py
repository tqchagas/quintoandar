from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode

from .errors import RequestFailed
from .transport import RequestFunction, get_json

URL_BASE = "https://apigw.prod.quintoandar.com.br/customer-facing-bff-api/v1/condo/negotiations"
MIN_INTERVAL_SECONDS = float(
    os.getenv("QUINTOANDAR_CONDO_NEGOTIATIONS_MIN_INTERVAL_SECONDS", "1.0")
)
HEADERS = {
    "Accept": "application/json",
    "Origin": "https://www.quintoandar.com.br",
    "Referer": "https://www.quintoandar.com.br/",
    "User-Agent": "Mozilla/5.0",
}


@dataclass(frozen=True)
class NegotiationQuery:
    """Actual unit/building attributes required by the negotiations endpoint.

    The caller supplies these values from a known QuintoAndar listing or other
    authorized source. The client does not infer missing values.
    """

    city: str
    street: str
    street_number: str
    house_type: str
    latitude: float
    longitude: float
    condominium_value: float
    min_area: float
    max_area: float
    min_bedroom: int
    max_bedroom: int
    min_bathroom: int
    max_bathroom: int

    def __post_init__(self) -> None:
        for name in ("city", "street", "street_number", "house_type"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name}_is_required")

        for name in (
            "latitude", "longitude", "condominium_value", "min_area", "max_area"
        ):
            value = getattr(self, name)
            try:
                valid = not isinstance(value, bool) and math.isfinite(float(value))
            except (TypeError, ValueError):
                valid = False
            if not valid:
                raise ValueError(f"{name}_must_be_finite")

        if not -90 <= float(self.latitude) <= 90:
            raise ValueError("latitude_out_of_range")
        if not -180 <= float(self.longitude) <= 180:
            raise ValueError("longitude_out_of_range")
        if float(self.condominium_value) < 0:
            raise ValueError("condominium_value_must_be_non_negative")
        if float(self.min_area) <= 0 or float(self.max_area) < float(self.min_area):
            raise ValueError("invalid_area_range")

        for name in ("min_bedroom", "max_bedroom", "min_bathroom", "max_bathroom"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name}_must_be_positive_integer")
        if self.max_bedroom < self.min_bedroom:
            raise ValueError("invalid_bedroom_range")
        if self.max_bathroom < self.min_bathroom:
            raise ValueError("invalid_bathroom_range")


@dataclass(frozen=True)
class NegotiationItem:
    house_id: str | None
    total_area: float | None
    bedroom_count: int | None
    bathroom_count: int | None
    neighborhood: str | None
    address: str | None
    city: str | None
    address_number: str | None
    price: float | None
    rent_price: float | None
    price_per_square_meter: float | None
    house_type: str | None
    negotiated_at: datetime | None


@dataclass(frozen=True)
class NegotiationBucket:
    same_condo: tuple[NegotiationItem, ...]
    neighborhood: tuple[NegotiationItem, ...]


@dataclass(frozen=True)
class CondoNegotiations:
    sale: NegotiationBucket
    rent: NegotiationBucket


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


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def _datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _item(row: Any) -> NegotiationItem | None:
    if not isinstance(row, dict):
        return None
    house_id = row.get("houseId")
    return NegotiationItem(
        house_id=str(house_id).strip() if house_id is not None else None,
        total_area=_number(row.get("totalArea")),
        bedroom_count=_integer(row.get("bedroomCount")),
        bathroom_count=_integer(row.get("bathroomCount")),
        neighborhood=_text(row.get("neighborhood")),
        address=_text(row.get("address")),
        city=_text(row.get("city")),
        address_number=_text(row.get("addressNumber")),
        price=_number(row.get("price")),
        rent_price=_number(row.get("rentPrice")),
        price_per_square_meter=_number(row.get("pricePerSquareMeter")),
        house_type=_text(row.get("houseType")),
        negotiated_at=_datetime(row.get("negotiatedAt")),
    )


def _bucket(context: Any) -> NegotiationBucket:
    context = context if isinstance(context, dict) else {}
    groups: dict[str, tuple[NegotiationItem, ...]] = {}
    for key in ("sameCondo", "neighborhood"):
        rows = context.get(key)
        if not isinstance(rows, list):
            rows = []
        groups[key] = tuple(item for item in (_item(row) for row in rows) if item is not None)
    return NegotiationBucket(
        same_condo=groups["sameCondo"], neighborhood=groups["neighborhood"]
    )


def parse_condo_negotiations(payload: Any) -> CondoNegotiations:
    if not isinstance(payload, dict):
        raise RequestFailed("invalid_condo_negotiations_payload")
    return CondoNegotiations(
        sale=_bucket(payload.get("sale")),
        rent=_bucket(payload.get("rent")),
    )


def negotiations_url(query: NegotiationQuery) -> str:
    path = "/".join(
        (
            URL_BASE,
            quote(query.city.strip().title(), safe=""),
            quote(query.street.strip(), safe=""),
            quote(query.street_number.strip(), safe=""),
        )
    )
    params = (
        ("houseType", query.house_type),
        ("latitude", query.latitude),
        ("longitude", query.longitude),
        ("condominiumPerMonth", round(query.condominium_value)),
        ("minArea", round(query.min_area)),
        ("maxArea", round(query.max_area)),
        ("minBedroom", query.min_bedroom),
        ("maxBedroom", query.max_bedroom),
        ("minBathroom", query.min_bathroom),
        ("maxBathroom", query.max_bathroom),
    )
    return f"{path}?{urlencode(params)}"


def fetch_condo_negotiations(
    query: NegotiationQuery, *, request: RequestFunction
) -> CondoNegotiations:
    payload = get_json(
        request,
        negotiations_url(query),
        headers=HEADERS,
        timeout=30,
        min_interval=MIN_INTERVAL_SECONDS,
    )
    return parse_condo_negotiations(payload)
