"""O diretório de condomínios do QuintoAndar: o número da rua que o anúncio não dá.

A limitação que mais custou à escada de referência é que Loft e QuintoAndar
publicam a rua e não publicam o número. Sem número o anúncio nunca alcança o
tier de endereço exato, onde o erro medido é 5-13%, e cai no de rua ou de
bairro, onde é 14-25%.

O portal publica esse número em outro lugar: uma página por prédio, indexada em
`sitemap-v3-condos-part-*.xml` e liberada pelo `robots.txt`.

    trazem o número                                   59/59
    casam com o cadastro da PBH por rua+numero        49/59  (83%)
    distancia do ponto ao lote do cadastro            p50 8 m, p90 24 m
    distancia do ponto ao anuncio do proprio portal   p50 1 m, max 27 m

O payload vem no `__NEXT_DATA__` da página, sob `condoInfo`, e responde a um GET
comum — sem sessão, sem cookie e sem navegador. Este módulo contém apenas
funções de leitura; quem chama decide como buscar as URLs e persistir os dados.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any



def _address_key(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    decomposed = unicodedata.normalize("NFKD", str(value))
    ascii_value = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_") or None


def _street_key(value: str | None) -> str | None:
    key = _address_key(value)
    if key is None:
        return None
    kind, _, rest = key.partition("_")
    canonical = {
        "ave": "avenida", "av": "avenida", "r": "rua", "pca": "praca",
        "pc": "praca", "rod": "rodovia", "ala": "alameda", "al": "alameda",
        "est": "estrada", "bec": "beco", "trv": "travessa", "tv": "travessa",
    }.get(kind)
    return f"{canonical}_{rest}" if canonical and rest else key

SOURCE = "quintoandar"
SITEMAP_INDEX = "https://www.quintoandar.com.br/sitemap-v3.xml"

_CONDO_PART = re.compile(r"sitemap-v3-condos-part-\d+\.xml$")
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
_URL_BLOCK = re.compile(r"<url\b.*?</url>", re.I | re.S)
_LASTMOD = re.compile(r"<lastmod>\s*(\d{4}-\d{2}-\d{2})", re.I)
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.I | re.S)
# O slug termina em `-{hashId}`, dez caracteres alfanuméricos.
_SLUG_TAIL = re.compile(r"-([a-z0-9]{10})$")


@dataclass(frozen=True)
class CondoRow:
    """Um prédio como o portal o publica."""

    source: str
    external_id: str
    slug: str | None
    url: str
    city: str
    street: str | None
    street_number: str | None
    street_key: str | None
    number_key: str | None
    postal_code: str | None
    neighborhood: str | None
    lat: float | None
    lon: float | None
    min_area: float | None
    max_area: float | None
    min_bedrooms: int | None
    max_bedrooms: int | None
    installations: list[str] | None
    doorman: str | None
    source_lastmod: date | None


@dataclass(frozen=True)
class CondoAddress:
    """Endereço normalizado pelo consumidor, por exemplo a partir de ITBI."""

    city: str
    street: str
    street_number: str | None = None
    postal_code: str | None = None
    lat: float | None = None
    lon: float | None = None


@dataclass(frozen=True)
class CondoMatch:
    """Candidato ordenado por evidências de endereço, não uma certeza jurídica."""

    condominium: CondoRow
    score: int
    evidence: tuple[str, ...]


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância haversine entre coordenadas em graus."""
    radius_m = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    value = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_m * math.asin(math.sqrt(min(1.0, value)))


def match_condominiums(
    address: CondoAddress, candidates: Iterable[CondoRow]
) -> list[CondoMatch]:
    """Rank candidates matching a city/street address using available evidence.

    City and normalized street must match. A known, conflicting street number
    excludes a candidate. Number, postal code, and coordinates add evidence;
    ties remain in the result so the consumer can handle ambiguity explicitly.
    Scores are ranking points, not probabilities.
    """
    city_key = _address_key(address.city)
    street_key = _street_key(address.street)
    if city_key is None or street_key is None:
        raise ValueError("city_and_street_are_required")
    number_key = _address_key(address.street_number)
    postal_key = re.sub(r"\D", "", str(address.postal_code or "")) or None
    if (address.lat is None) != (address.lon is None):
        raise ValueError("latitude_and_longitude_must_be_provided_together")
    if address.lat is not None and address.lon is not None:
        try:
            valid_coordinates = (
                math.isfinite(float(address.lat))
                and math.isfinite(float(address.lon))
                and -90 <= float(address.lat) <= 90
                and -180 <= float(address.lon) <= 180
            )
        except (TypeError, ValueError):
            valid_coordinates = False
        if not valid_coordinates:
            raise ValueError("coordinates_out_of_range")

    matches: list[CondoMatch] = []
    for condo in candidates:
        if (
            _address_key(condo.city) != city_key
            or (condo.street_key or _street_key(condo.street)) != street_key
        ):
            continue

        condo_number = condo.number_key or _address_key(condo.street_number)
        if number_key and condo_number and number_key != condo_number:
            continue

        score = 50
        evidence = ["city_and_street"]
        corroborated = False
        if number_key and condo_number and number_key == condo_number:
            score += 35
            evidence.append("street_number")
            corroborated = True

        condo_postal = re.sub(r"\D", "", str(condo.postal_code or "")) or None
        if postal_key and condo_postal and postal_key == condo_postal:
            score += 5
            evidence.append("postal_code")
            corroborated = True

        if (
            address.lat is not None
            and address.lon is not None
            and condo.lat is not None and condo.lon is not None
        ):
            distance = _distance_m(
                float(address.lat), float(address.lon), float(condo.lat), float(condo.lon)
            )
            if distance <= 25:
                score += 10
                evidence.append("coordinates_within_25m")
                corroborated = True
            elif distance <= 75:
                score += 6
                evidence.append("coordinates_within_75m")
                corroborated = True
            elif distance <= 150:
                score += 3
                evidence.append("coordinates_within_150m")
                corroborated = True

        # Rua/cidade sozinhas frequentemente apontariam para vários prédios.
        if not corroborated:
            continue
        matches.append(CondoMatch(condominium=condo, score=score, evidence=tuple(evidence)))

    return sorted(matches, key=lambda match: (-match.score, match.condominium.external_id))


def sitemap_parts(index_xml: str) -> list[str]:
    """As partições de condomínio do índice de sitemaps, na ordem em que vêm.

    O índice mistura buscas, regiões e páginas de cidade; só esta família tem
    uma página por prédio.
    """
    return [url for url in _LOC.findall(index_xml) if _CONDO_PART.search(url)]


def condo_entries(sitemap_xml: str, city_slug: str) -> list[tuple[str, date | None]]:
    """(URL, data da última alteração) das páginas daquela cidade.

    O sitemap é nacional — 179.572 páginas, das quais 19.117 são de Belo
    Horizonte. A cidade está no fim do slug, antes do hash, então filtrar por
    texto é exato e evita abrir cada página para descobrir que ela é de outro
    estado.
    """
    encontrados: list[tuple[str, date | None]] = []
    marca = f"-{city_slug}-"
    for bloco in _URL_BLOCK.findall(sitemap_xml):
        achado = _LOC.search(bloco)
        if achado is None or marca not in achado.group(1):
            continue
        quando = _LASTMOD.search(bloco)
        encontrados.append(
            (achado.group(1), date.fromisoformat(quando.group(1)) if quando else None)
        )
    return encontrados


def slug_neighborhood(url: str, city_slug: str) -> str | None:
    """O bairro que o slug declara, que é o que dá para filtrar antes de baixar.

    Metade dos slugs começa pela rua e a outra metade pelo nome do prédio, mas
    todos terminam em `-{bairro}-{cidade}-{hash}`. O bairro é o que permite
    gastar o orçamento de uma execução onde existe anúncio sem prédio
    resolvido, em vez de baixar dezessete gigabytes de páginas.
    """
    slug = _SLUG_TAIL.sub("", url.rstrip("/").rsplit("/", 1)[-1])
    marca = f"-{city_slug}"
    if not slug.endswith(marca):
        return None
    return slug[: -len(marca)].rsplit("-", 1)[-1] or None


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _int(value: Any) -> int | None:
    number = _float(value)
    return int(number) if number is not None else None


def _clean(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _condo_info(payload: Any, profundidade: int = 0) -> dict | None:
    """`condoInfo` mora sob `props.pageProps`, mas o portal já moveu a chave de
    lugar entre versões do bundle — procurar custa menos do que reagir a isso
    quando a coleta inteira começa a devolver vazio."""
    if profundidade > 8 or not isinstance(payload, dict):
        return None
    achado = payload.get("condoInfo")
    if isinstance(achado, dict):
        return achado
    for valor in payload.values():
        if isinstance(valor, dict):
            encontrado = _condo_info(valor, profundidade + 1)
            if encontrado is not None:
                return encontrado
    return None


def _installations(features: dict) -> list[str] | None:
    """Só o que o prédio tem.

    O portal publica `"NAO"` como resposta, e não como ausência. Guardar as
    duas encheria a coluna de ruído e faria a contagem de comodidades dizer o
    contrário do que diz.
    """
    itens = features.get("installations")
    if not isinstance(itens, list):
        return None
    presentes = sorted(
        chave
        for item in itens
        if isinstance(item, dict)
        and str(item.get("value", "")).strip().upper() == "SIM"
        and (chave := _clean(item.get("key")))
    )
    return presentes or None


def parse_condo_page(
    html: str, url: str, *, city: str, lastmod: date | None = None
) -> CondoRow | None:
    """Lê uma página de condomínio, ou devolve None quando ela não serve.

    Endereços incompletos continuam sendo condomínios válidos. Os campos de
    chave ficam ausentes quando a página não publica os dados necessários.
    """
    achado = _NEXT_DATA.search(html)
    if achado is None:
        return None
    try:
        payload = json.loads(achado.group(1))
    except json.JSONDecodeError:
        return None
    info = _condo_info(payload)
    if info is None:
        return None

    rua, numero = _clean(info.get("address")), _clean(info.get("number"))
    chave_rua, chave_numero = _street_key(rua), _address_key(numero)

    features = info.get("features") if isinstance(info.get("features"), dict) else {}
    lat, lon = _float(info.get("lat")), _float(info.get("lng"))
    return CondoRow(
        source=SOURCE,
        external_id=str(info.get("hashId") or "").strip(),
        slug=_clean(info.get("slug")),
        url=url,
        city=city,
        street=rua,
        street_number=numero,
        street_key=chave_rua,
        number_key=chave_numero,
        postal_code=_clean(info.get("zipCode")),
        neighborhood=_clean(info.get("neighborhood")),
        # Seis casas é a precisão que `registry_addresses` já guarda, e basta
        # para distinguir lotes vizinhos; o portal devolve o float inteiro.
        lat=round(lat, 6) if lat is not None else None,
        lon=round(lon, 6) if lon is not None else None,
        # A faixa de área das unidades que o portal conhece naquele prédio —
        # outra leitura do formato, em área anunciada, ao lado da do cadastro
        # em área construída.
        min_area=_float(info.get("minArea")),
        max_area=_float(info.get("maxArea")),
        min_bedrooms=_int(info.get("minBedrooms")),
        max_bedrooms=_int(info.get("maxBedrooms")),
        installations=_installations(features),
        doorman=_clean(features.get("doorman")),
        source_lastmod=lastmod,
    )
