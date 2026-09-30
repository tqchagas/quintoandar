"""Read-only client and parsers for QuintoAndar property data."""

from .client import QuintoAndarClient
from .condominiums import (
    CondoRow,
    condo_entries,
    parse_condo_page,
    sitemap_parts,
    slug_neighborhood,
)
from .errors import (
    EstimateUnavailable,
    ListingNotFound,
    PortalBlocked,
    QuintoAndarError,
    RequestFailed,
)
from .search import Listing, SearchQuery, SearchResult
from .valuation import Comparables, Estimate, EstimateInput, SoldComparable

__all__ = [
    "Comparables",
    "CondoRow",
    "Estimate",
    "EstimateInput",
    "EstimateUnavailable",
    "Listing",
    "ListingNotFound",
    "PortalBlocked",
    "QuintoAndarClient",
    "QuintoAndarError",
    "RequestFailed",
    "SearchQuery",
    "SearchResult",
    "SoldComparable",
    "condo_entries",
    "parse_condo_page",
    "sitemap_parts",
    "slug_neighborhood",
]
