#!/usr/bin/env python3
"""Collect public QuintoAndar condominium pages into a JSONL file."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from quintoandar import QuintoAndarClient


def build_transport():
    last_request_started = 0.0

    def request(method, url, *, headers, json_body, timeout, min_interval):
        nonlocal last_request_started
        now = time.monotonic()
        delay = min_interval - (now - last_request_started)
        if last_request_started and delay > 0:
            time.sleep(delay)

        body = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
        http_request = Request(url, data=body, headers=headers, method=method)
        last_request_started = time.monotonic()
        try:
            response = urlopen(http_request, timeout=_timeout_seconds(timeout))
        except HTTPError as error:
            response = error

        with response:
            return SimpleNamespace(
                status_code=getattr(response, "status", response.code),
                text=response.read().decode("utf-8", errors="replace"),
            )

    return request


def _timeout_seconds(timeout) -> float:
    if isinstance(timeout, (tuple, list)):
        return float(timeout[-1])
    return float(timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="Belo Horizonte")
    parser.add_argument("--city-slug", default="belo-horizonte")
    parser.add_argument(
        "--limit", type=int, default=0,
        help="maximum records to write; 0 collects all records (default)",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("condominios-belo-horizonte.jsonl")
    )
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be zero or greater")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    client = QuintoAndarClient(build_transport())
    written = 0
    try:
        with args.output.open("w", encoding="utf-8") as output:
            for condo in client.iter_condominiums(args.city, args.city_slug):
                output.write(json.dumps(asdict(condo), ensure_ascii=False, default=str) + "\n")
                output.flush()
                written += 1
                if written % 100 == 0:
                    print(f"{written} condomínios gravados em {args.output}", flush=True)
                if args.limit and written >= args.limit:
                    break
    except KeyboardInterrupt:
        print(f"Interrompido; {written} condomínios foram gravados em {args.output}")
        return 130
    except Exception as error:
        print(
            f"Coleta interrompida após {written} registros: {error}. "
            f"Dados parciais: {args.output}"
        )
        return 1

    print(f"Concluído: {written} condomínios em {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
