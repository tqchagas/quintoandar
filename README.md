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
from quintoandar import CondoAddress, QuintoAndarClient, SearchQuery, match_condominiums

client = QuintoAndarClient(request=my_http_request)
result = client.search_listings(
    SearchQuery(city="Belo Horizonte", state="MG", neighborhood="Savassi"),
    max_pages=2,
)

for listing in result.listings:
    print(listing.listing_id, listing.price, listing.area_m2)

# Enriquecimento de um anúncio para resolver o condomínio e número da rua.
detail = client.listing_detail("123456789")
print(detail.condo_id, detail.street_number)

# Carregue/consulte o diretório persistido pelo consumidor.
condo_rows = list(client.iter_condominiums("Belo Horizonte", "belo-horizonte"))
for condo in condo_rows:
    print(condo.external_id, condo.street, condo.street_number)

# Compare um endereço do sistema consumidor com o diretório já coletado.
matches = match_condominiums(
    CondoAddress(
        city="Belo Horizonte",
        street="Rua dos Inconfidentes",
        street_number="100",
        postal_code="30140-120",
    ),
    condo_rows,
)
for match in matches:
    print(match.condominium.external_id, match.score, match.evidence)
```

`request` receives `method`, `url`, and keyword arguments `headers`,
`json_body`, `timeout`, and `min_interval`, then returns an object with
`status_code`, `text`, and `json()`. The caller owns global pacing and retry
policy. The client stops with `PortalBlocked` on 401, 403, or 429 responses.

## Coletar condomínios

O Makefile inclui um transporte HTTP simples e grava os registros em JSONL:

```bash
make condominiums LIMIT=1                 # busca um registro para experimentar
make condominiums                          # coleta a cidade inteira
make condominiums CITY="São Paulo" CITY_SLUG=sao-paulo OUTPUT=sp.jsonl
```

A coleta completa pode levar horas. O arquivo é atualizado a cada registro;
se a execução for interrompida, ele contém os dados coletados até então.
Uma nova execução começa do início e sobrescreve o arquivo indicado.

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
- `similar_houses_data(body)` returns a normalized `SimilarHomesResult` with the
  market summary plus available and unavailable comparable listings, including
  listing ID, prices, size, distance, availability dates, and cover image when
  supplied by the response. `similar_houses(body)` remains available for callers
  that need the original response payload.
- `quintoandar.similar.build_market_body(...)` builds a request from known unit
  attributes. It accepts optional `condominium_per_month` and `street_number`
  fields, and only sends them when supplied.
- `listing_detail(listing_id)` returns selected listing-detail fields, including
  the condominium ID/slug, street number, condominium fee, and IPTU.
- `condo_negotiations(query)` returns sale and rent groups (`same_condo` and
  `neighborhood`) from one response. `NegotiationQuery` requires city, street,
  number, property type, coordinates, condominium fee, and min/max ranges for
  area, bedrooms, and bathrooms. The caller must supply real known attributes;
  the client does not infer missing values. Results are portal negotiation
  comparables, not a complete transaction register or official deed data.
- `condominium_page(url)` fetches an individual public condominium page.
- `condominium_sitemaps()` fetches the sitemap index and returns the
  condominium sitemap partitions.
- `iter_condominium_entries(city_slug)` yields each matching page URL and its
  sitemap `lastmod`, without downloading condominium pages.
- `fetch_condominium(url, city=..., lastmod=...)` downloads and parses one page
  into a `CondoRow`; the caller owns selection and persistence.
- `match_condominiums(CondoAddress(...), condo_rows)` locally ranks condo records
  against a known address using city, normalized street, street number, postal
  code, and optional coordinates. It makes no network requests. Results include
  evidence and ranking points (not probabilities); ties are preserved so the
  consumer can apply its own review or confidence rules. A known conflicting
  street number excludes a candidate. City and street alone are not enough to
  return a match: number, postal code, or nearby coordinates must corroborate it.
- `iter_condominiums(city, city_slug)` walks the city's condominium sitemap
  entries and yields parsed records lazily. For example, use
  `iter_condominiums("Belo Horizonte", "belo-horizonte")`. Records with
  incomplete addresses are included, with unavailable address fields set to
  `None`. Network, HTTP, and portal-block errors stop iteration and are raised
  to the caller.
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
