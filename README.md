# quintoandar-client

Python client and parsers for read-only QuintoAndar property data.

The package keeps portal request formats and response parsing in one place. It
does not import Imóvel Radar, write to a database, score or price properties,
or send lead forms. It is an independent community project and is not
affiliated with QuintoAndar. The endpoints it uses are not a supported public
API and may change without notice.

## Install

```bash
pip install .
```

The package has no runtime dependencies. Applications inject their own HTTP
transport so they can apply their existing retry, timeout, proxy, and pacing
policies.

## Use

```python
from quintoandar import QuintoAndarClient, SearchQuery

client = QuintoAndarClient(request=my_http_request)
result = client.search_listings(
    SearchQuery(city="Belo Horizonte", state="MG", neighborhood="Savassi"),
    max_pages=2,
)

for listing in result.listings:
    print(listing.listing_id, listing.price, listing.area_m2)
```

`request` receives `method`, `url`, and keyword arguments `headers`,
`json_body`, `timeout`, and `min_interval`, then returns an object with
`status_code`, `text`, and `json()`. The caller owns global pacing and retry
policy. The client stops with `PortalBlocked` on 401, 403, or 429 responses.

## Client methods

- `search_listings(query, max_pages=100)` returns listings and whether the
  result set is complete. Search is capped at 1,000 results per scope by the
  portal.
- `price_suggestion(listing_id)` returns the portal's JSON estimate for a
  QuintoAndar listing. A cookie is optional and supplied when constructing the
  client.
- `estimate(EstimateInput)` returns the address-based estimate or raises
  `EstimateUnavailable` when the portal returns no price.
- `comparables(EstimateInput, Estimate)` returns the portal's similar-home
  groups.
- `similar_houses(body)` returns the portal's neighborhood summary for the
  supplied property attributes.
- `condominium_page(url)` fetches an individual public condominium page.
- `quintoandar.condominiums` provides pure parsers for sitemap XML and
  condominium page HTML.

Errors derive from `QuintoAndarError`: `PortalBlocked`, `RequestFailed`,
`ListingNotFound`, and `EstimateUnavailable` distinguish expected responses
from malformed or unsuccessful requests.

## Responsible use

Use the package for low-volume, read-only research. Respect portal responses,
rate limits, robots directives, and applicable terms. Do not retry a block by
changing identity or bypassing access controls. Do not place personal data or
session cookies in logs or source control.

## License

MIT. See `LICENSE`.
