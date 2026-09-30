from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .errors import RequestFailed
from .transport import RequestFunction, post_json

URL = "https://apigw.prod.quintoandar.com.br/customer-facing-bff-api/v1/brand-calculator/similar-houses"
MIN_INTERVAL_SECONDS = float(os.getenv("SIMILARES_MIN_INTERVAL_SECONDS", "3.0"))
HEADERS = {
    "accept": "application/json", "content-type": "application/json",
    "origin": "https://www.quintoandar.com.br", "referer": "https://www.quintoandar.com.br/",
}
BANDA_INFERIOR = 0.2
BANDA_SUPERIOR = 5.0


def build_market_body(
    *,
    price: float,
    area_m2: float,
    latitude: float,
    longitude: float,
    bedrooms: int | None,
    bathrooms: int | None,
    property_type: str | None,
    city: str,
    address: str | None,
    condominium_per_month: float | None = None,
    street_number: str | int | None = None,
) -> dict[str, Any] | None:
    if price <= 0 or area_m2 <= 0:
        return None
    body = {
        "percentile10": int(price * BANDA_INFERIOR),
        "percentile90": int(price * BANDA_SUPERIOR),
        "latitude": float(latitude), "longitude": float(longitude),
        "bedroomCount": int(bedrooms or 2), "bathroomCount": int(bathrooms or 1),
        "totalArea": int(area_m2),
        "houseType": "HOUSE" if str(property_type or "").upper() == "CASA" else "APARTMENT",
        "city": city, "address": address, "businessContext": "SALE",
    }
    if condominium_per_month is not None:
        body["condominiumPerMonth"] = int(condominium_per_month)
    if street_number is not None and str(street_number).strip():
        body["number"] = int(float(street_number))
    return body


def fetch_similar_houses(
    body: dict[str, Any], *, request: RequestFunction, url: str = URL
) -> dict[str, Any]:
    """Fetch the portal's market context for supplied property attributes."""
    return post_json(
        request, url, body, headers=HEADERS, timeout=30,
        min_interval=MIN_INTERVAL_SECONDS,
    )


def extract_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}

    def number(value: Any) -> float | None:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if result > 0 else None

    days = number(summary.get("daysOnMarketUntilDealAverage"))
    return {
        "similares_m2_anunciado": number(summary.get("onMarketPriceBySquareMeter")),
        "similares_m2_negociado": number(summary.get("offMarketPriceBySquareMeter")),
        "similares_dias_ate_negocio": int(days) if days is not None else None,
    }


@dataclass(frozen=True)
class SimilarHome:
    listing_id: str | None
    url: str | None
    price: float | None
    price_per_square_meter: float | None
    total_area: float | None
    distance_km: float | None
    last_time_on_market: datetime | None
    days_on_market: int | None
    address: str | None
    city: str | None
    neighborhood: str | None
    street_number: str | None
    bedrooms: int | None
    bathrooms: int | None
    parking_spaces: int | None
    house_type: str | None
    same_condo: bool | None
    from_quintoandar: bool | None
    available: bool
    cover_image: str | None


@dataclass(frozen=True)
class SimilarHomesSummary:
    off_market_price_average: float | None
    off_market_rent_average: float | None
    off_market_price_per_square_meter: float | None
    on_market_price_average: float | None
    on_market_rent_average: float | None
    on_market_price_per_square_meter: float | None
    condominium_price_average: float | None
    iptu_average: float | None
    days_on_market_until_deal_average: float | None


@dataclass(frozen=True)
class SimilarHomesResult:
    summary: SimilarHomesSummary
    available: tuple[SimilarHome, ...]
    unavailable: tuple[SimilarHome, ...]


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _integer(value: Any) -> int | None:
    result = _number(value)
    return int(result) if result is not None and result.is_integer() else None


def _text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _summary(data: Any) -> SimilarHomesSummary:
    row = data if isinstance(data, dict) else {}
    return SimilarHomesSummary(
        off_market_price_average=_number(row.get("offMarketPriceAverage")),
        off_market_rent_average=_number(row.get("offMarketRentAverage")),
        off_market_price_per_square_meter=_number(row.get("offMarketPriceBySquareMeter")),
        on_market_price_average=_number(row.get("onMarketPriceAverage")),
        on_market_rent_average=_number(row.get("onMarketRentAverage")),
        on_market_price_per_square_meter=_number(row.get("onMarketPriceBySquareMeter")),
        condominium_price_average=_number(row.get("condominiumPriceAverage")),
        iptu_average=_number(row.get("iptuAverage")),
        days_on_market_until_deal_average=_number(row.get("daysOnMarketUntilDealAverage")),
    )


def _similar_home(data: Any, *, available: bool) -> SimilarHome | None:
    if not isinstance(data, dict):
        return None
    identifier = _text(data.get("houseId") or data.get("listingId"))
    per_square_meter = data.get("priceM2")
    if per_square_meter is None:
        per_square_meter = data.get("pricePerSquareMeter")
    return SimilarHome(
        listing_id=identifier,
        url=f"https://www.quintoandar.com.br/imovel/{identifier}/comprar" if identifier else None,
        price=_number(data.get("price")),
        price_per_square_meter=_number(per_square_meter),
        total_area=_number(data.get("totalArea")),
        distance_km=_number(data.get("distance")),
        last_time_on_market=_datetime(data.get("lastTimeOnMarket")),
        days_on_market=_integer(data.get("daysOnMarket")),
        address=_text(data.get("address")),
        city=_text(data.get("city")),
        neighborhood=_text(data.get("neighborhood")),
        street_number=_text(data.get("addressNumber")),
        bedrooms=_integer(data.get("bedroomCount")),
        bathrooms=_integer(data.get("bathroomCount")),
        parking_spaces=_integer(data.get("parkingSlots")),
        house_type=_text(data.get("houseType")),
        same_condo=data.get("sameCondo") if isinstance(data.get("sameCondo"), bool) else None,
        from_quintoandar=(
            data.get("isFromQuintoAndarSource")
            if isinstance(data.get("isFromQuintoAndarSource"), bool) else None
        ),
        available=available,
        cover_image=_text(data.get("coverImage")),
    )


def parse_similar_houses(payload: Any) -> SimilarHomesResult:
    """Normalize summary and available/unavailable comparable listings."""
    if not isinstance(payload, dict):
        raise RequestFailed("invalid_similar_houses_payload")
    available = payload.get("availableSimilarHouses")
    unavailable = payload.get("unavailableSimilarHouses")
    return SimilarHomesResult(
        summary=_summary(payload.get("summary")),
        available=tuple(
            home for home in (_similar_home(row, available=True) for row in (available or []))
            if home is not None
        ) if isinstance(available, list) else (),
        unavailable=tuple(
            home for home in (_similar_home(row, available=False) for row in (unavailable or []))
            if home is not None
        ) if isinstance(unavailable, list) else (),
    )
