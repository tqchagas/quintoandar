from __future__ import annotations

import os
from typing import Any

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
) -> dict[str, Any] | None:
    if price <= 0 or area_m2 <= 0:
        return None
    return {
        "percentile10": int(price * BANDA_INFERIOR),
        "percentile90": int(price * BANDA_SUPERIOR),
        "latitude": float(latitude), "longitude": float(longitude),
        "bedroomCount": int(bedrooms or 2), "bathroomCount": int(bathrooms or 1),
        "totalArea": int(area_m2),
        "houseType": "HOUSE" if str(property_type or "").upper() == "CASA" else "APARTMENT",
        "city": city, "address": address, "businessContext": "SALE",
    }


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
