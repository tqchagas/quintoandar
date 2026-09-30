"""Read-only client and parsers for QuintoAndar property data."""

from .client import QuintoAndarClient
from .condominiums import (
    CondoAddress,
    CondoMatch,
    CondoRow,
    condo_entries,
    match_condominiums,
    parse_condo_page,
    sitemap_parts,
    slug_neighborhood,
)
from .details import ListingDetail
from .errors import (
    EstimateUnavailable,
    ListingNotFound,
    PortalBlocked,
    QuintoAndarError,
    RequestFailed,
)
from .search import Listing, SearchQuery, SearchResult
from .negotiations import CondoNegotiations, NegotiationBucket, NegotiationItem, NegotiationQuery
from .similar import SimilarHome, SimilarHomesResult, SimilarHomesSummary, parse_similar_houses
from .valuation import Comparables, Estimate, EstimateInput, SoldComparable

__all__ = [
    "Comparables",
    "CondoAddress",
    "CondoMatch",
    "CondoRow",
    "CondoNegotiations",
    "Estimate",
    "EstimateInput",
    "EstimateUnavailable",
    "Listing",
    "ListingDetail",
    "ListingNotFound",
    "PortalBlocked",
    "QuintoAndarClient",
    "QuintoAndarError",
    "RequestFailed",
    "SearchQuery",
    "SearchResult",
    "SimilarHome",
    "SimilarHomesResult",
    "SimilarHomesSummary",
    "SoldComparable",
    "NegotiationBucket",
    "NegotiationItem",
    "NegotiationQuery",
    "condo_entries",
    "match_condominiums",
    "parse_condo_page",
    "parse_similar_houses",
    "sitemap_parts",
    "slug_neighborhood",
]
