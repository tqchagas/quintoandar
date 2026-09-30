# Changelog

## Unreleased

- Normalize QuintoAndar similar-home results into summary and available/unavailable comparables.
- Allow similar-home request bodies to include known condominium fee and street number.
- Add lazy, city-scoped condominium collection from the public sitemap.
- Expose sitemap partitions, city page entries, and single-page parsing for
  consumers that own target selection and persistence.
- Add normalized listing details and condominium sale/rent negotiation results.
- Preserve condominium pages with incomplete street addresses.

## 0.1.0

- Initial read-only client for listing search, price suggestions, address
  estimates, similar homes, and condominium pages.
- Add standalone parsers for condominium sitemap and detail pages.
- Support injected HTTP transport and package-owned response errors.
