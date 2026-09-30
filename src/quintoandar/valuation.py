from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

from .errors import EstimateUnavailable
from .transport import RequestFunction, post_json

BASE_URL = "https://apigw.prod.quintoandar.com.br/customer-facing-bff-api/v1/brand-calculator"
URL_ESTIMATE = f"{BASE_URL}/estimate"
URL_COMPARABLES = f"{BASE_URL}/similar-houses"
MIN_INTERVAL_SECONDS = float(os.getenv("QPRECO_CALC_MIN_INTERVAL_SECONDS", "3.0"))
HEADERS = {
    "accept": "application/json", "content-type": "application/json",
    "origin": "https://proprietario.quintoandar.com.br",
    "referer": "https://proprietario.quintoandar.com.br/",
}


@dataclass(frozen=True)
class EstimateInput:
    address: str
    city: str
    latitude: float
    longitude: float
    total_area: float
    address_number: int | None = None
    neighborhood: str | None = None
    state: str | None = None
    country: str = "Brasil"
    house_type: str = "APARTMENT"
    bedroom_count: int = 2
    bathroom_count: int = 1
    suites_count: int = 0
    parking_slots: int = 0
    floor: int | None = None
    condominium_per_month: float = 0
    iptu_per_year: float = 0


@dataclass(frozen=True)
class Estimate:
    suggested_price: float
    lower_bound: float | None
    upper_bound: float | None
    limit_lower: float | None
    limit_upper: float | None
    certainty: str | None
    percentiles: dict[int, float]


@dataclass(frozen=True)
class SoldComparable:
    house_id: int | None
    price: float
    price_m2: float | None
    total_area: float | None
    bedroom_count: int | None
    parking_slots: int | None
    distance_km: float | None
    sold_at: date | None
    address: str | None
    neighborhood: str | None
    city: str | None
    same_condo: bool


@dataclass(frozen=True)
class Comparables:
    sold: tuple[SoldComparable, ...]
    available: tuple[SoldComparable, ...]
    same_condo: tuple[SoldComparable, ...]
    on_market_m2: float | None
    off_market_m2: float | None
    days_until_deal: int | None


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _estimate_body(value: EstimateInput) -> dict[str, Any]:
    return {
        "bathroomCount": value.bathroom_count, "bedroomCount": value.bedroom_count,
        "condominiumPerMonth": value.condominium_per_month, "iptuPerYear": value.iptu_per_year,
        "suitesCount": value.suites_count, "parkingSlots": value.parking_slots,
        "address": value.address, "neighborhood": value.neighborhood, "city": value.city,
        "state": value.state, "country": value.country, "latitude": value.latitude,
        "longitude": value.longitude, "businessContext": "SALE", "houseType": value.house_type,
        "floor": value.floor, "totalArea": value.total_area, "addressNumber": value.address_number,
    }


def _percentiles(raw: Any) -> dict[int, float]:
    if not isinstance(raw, dict):
        return {}
    result = {}
    for key, value in raw.items():
        percentile, price = _integer(key), _number(value)
        if percentile is not None and price is not None:
            result[percentile] = price
    return result


def fetch_estimate(value: EstimateInput, *, request: RequestFunction) -> Estimate:
    payload = post_json(
        request, URL_ESTIMATE, _estimate_body(value), headers=HEADERS,
        timeout=30, min_interval=MIN_INTERVAL_SECONDS,
    )
    price = _number(payload.get("suggestedPrice"))
    if price is None:
        raise EstimateUnavailable(
            "o portal não calculou preço — confira a coordenada antes de "
            "concluir que o imóvel é atípico"
        )
    return Estimate(
        suggested_price=price,
        lower_bound=_number(payload.get("suggestedLowerBoundPrice")),
        upper_bound=_number(payload.get("suggestedUpperBoundPrice")),
        limit_lower=_number(payload.get("lowerBoundLimit")),
        limit_upper=_number(payload.get("upperBoundLimit")),
        certainty=payload.get("predictionCertainty") or None,
        percentiles=_percentiles(payload.get("percentiles")),
    )


def _comparable(row: Any) -> SoldComparable | None:
    if not isinstance(row, dict):
        return None
    price = _number(row.get("price"))
    if price is None:
        return None
    raw_date = str(row.get("lastTimeOnMarket") or "")[:10]
    try:
        sold_at = date.fromisoformat(raw_date) if raw_date else None
    except ValueError:
        sold_at = None
    return SoldComparable(
        house_id=_integer(row.get("houseId")), price=price,
        price_m2=_number(row.get("priceM2")), total_area=_number(row.get("totalArea")),
        bedroom_count=_integer(row.get("bedroomCount")), parking_slots=_integer(row.get("parkingSlots")),
        distance_km=_number(row.get("distance")), sold_at=sold_at,
        address=row.get("address"), neighborhood=row.get("neighborhood"), city=row.get("city"),
        same_condo=bool(row.get("sameCondo")),
    )


def _items(payload: dict[str, Any], key: str) -> tuple[SoldComparable, ...]:
    rows = payload.get(key)
    return tuple(item for item in (_comparable(row) for row in rows) if item is not None) if isinstance(rows, list) else ()


def fetch_comparables(
    value: EstimateInput, estimate: Estimate, *, request: RequestFunction
) -> Comparables:
    body = {
        "percentile10": estimate.limit_lower or estimate.suggested_price * 0.5,
        "percentile90": estimate.limit_upper or estimate.suggested_price * 1.5,
        "latitude": value.latitude, "longitude": value.longitude,
        "condominiumPerMonth": value.condominium_per_month, "bathroomCount": value.bathroom_count,
        "bedroomCount": value.bedroom_count, "totalArea": value.total_area,
        "houseType": value.house_type, "city": value.city, "address": value.address,
        "number": value.address_number, "businessContext": "SALE",
    }
    payload = post_json(
        request, URL_COMPARABLES, body, headers=HEADERS, timeout=30,
        min_interval=MIN_INTERVAL_SECONDS,
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    days = _number(summary.get("daysOnMarketUntilDealAverage"))
    return Comparables(
        sold=_items(payload, "unavailableSimilarHouses"),
        available=_items(payload, "availableSimilarHouses"),
        same_condo=_items(payload, "negotiatedInTheSameCondo"),
        on_market_m2=_number(summary.get("onMarketPriceBySquareMeter")),
        off_market_m2=_number(summary.get("offMarketPriceBySquareMeter")),
        days_until_deal=int(days) if days is not None else None,
    )
