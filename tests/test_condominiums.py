import json
import unittest

from quintoandar import PortalBlocked, QuintoAndarClient, RequestFailed
from quintoandar.condominiums import parse_condo_page


def condo_html(*, number=None, identifier="abc1234567"):
    info = {
        "hashId": identifier,
        "slug": "edificio-centro-belo-horizonte-abc1234567",
        "address": "Rua da Bahia",
        "number": number,
        "neighborhood": "Centro",
        "lat": -19.92,
        "lng": -43.94,
        "features": {"installations": [{"key": "pool", "value": "SIM"}]},
    }
    payload = {"props": {"pageProps": {"condoInfo": info}}}
    return '<script id="__NEXT_DATA__">' + json.dumps(payload) + "</script>"


class Response:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code


class CondominiumCollectionTests(unittest.TestCase):
    def test_parser_keeps_record_without_street_number(self):
        row = parse_condo_page(
            condo_html(),
            "https://www.quintoandar.com.br/condominio/teste-abc1234567",
            city="Belo Horizonte",
        )

        self.assertIsNotNone(row)
        self.assertEqual(row.street, "Rua da Bahia")
        self.assertIsNone(row.street_number)
        self.assertIsNone(row.number_key)
        self.assertIsNotNone(row.street_key)

    def test_iterator_walks_city_pages_lazily_and_includes_incomplete_address(self):
        sitemap_url = "https://www.quintoandar.com.br/sitemap-v3-condos-part-1.xml"
        condo_url = "https://www.quintoandar.com.br/condominio/teste-belo-horizonte-abc1234567"
        responses = {
            "https://www.quintoandar.com.br/sitemap-v3.xml": Response(
                f"<sitemapindex><sitemap><loc>{sitemap_url}</loc></sitemap></sitemapindex>"
            ),
            sitemap_url: Response(
                f"<urlset><url><loc>{condo_url}</loc><lastmod>2026-09-01</lastmod></url>"
                "<url><loc>https://www.quintoandar.com.br/condominio/outra-cidade-sao-paulo-1234567890</loc></url></urlset>"
            ),
            condo_url: Response(condo_html()),
        }
        calls = []

        def request(method, url, **kwargs):
            calls.append(url)
            return responses[url]

        rows = QuintoAndarClient(request).iter_condominiums(
            "Belo Horizonte", "belo-horizonte"
        )
        self.assertEqual(calls, [])
        row = next(rows)
        self.assertEqual(row.external_id, "abc1234567")
        self.assertIsNone(row.street_number)
        self.assertEqual(str(row.source_lastmod), "2026-09-01")
        self.assertEqual(calls, [
            "https://www.quintoandar.com.br/sitemap-v3.xml",
            sitemap_url,
            condo_url,
        ])

    def test_block_stops_collection(self):
        def request(method, url, **kwargs):
            return Response("blocked", status_code=429)

        with self.assertRaises(PortalBlocked):
            next(QuintoAndarClient(request).iter_condominiums(
                "Belo Horizonte", "belo-horizonte"
            ))

    def test_rejects_non_portal_sitemap_url(self):
        def request(method, url, **kwargs):
            return Response(
                "<sitemapindex><sitemap><loc>https://example.com/"
                "sitemap-v3-condos-part-1.xml</loc>"
                "</sitemap></sitemapindex>"
            )

        rows = QuintoAndarClient(request).iter_condominiums(
            "Belo Horizonte", "belo-horizonte"
        )
        with self.assertRaises(ValueError):
            next(rows)

    def test_invalid_sitemap_fails_instead_of_ending_as_empty_collection(self):
        def request(method, url, **kwargs):
            return Response("<sitemapindex>")

        rows = QuintoAndarClient(request).iter_condominiums(
            "Belo Horizonte", "belo-horizonte"
        )
        with self.assertRaises(RequestFailed):
            next(rows)


if __name__ == "__main__":
    unittest.main()
