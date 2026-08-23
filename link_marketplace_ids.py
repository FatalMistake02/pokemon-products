"""Link TCGplayer, Cardmarket, and CardTrader IDs in a product JSON file.

TCG Tracking uses the TCGplayer product ID as its product identifier. For every
product in the input file, this script calls ``/v1/products/{tcgplayer_id}``
and copies the returned Cardmarket and CardTrader IDs into the local record.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API_BASE = "https://openapi.tcgtracking.com/v1"
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


class ApiError(RuntimeError):
    """Raised when a TCG Tracking request cannot be completed."""


def fetch_links(
    tcgplayer_id: str,
    api_base: str,
    timeout: float,
    retries: int,
) -> tuple[int | None, int | None]:
    """Return ``(cardmarket_id, cardtrader_id)`` for a TCGplayer product."""
    url = f"{api_base.rstrip('/')}/products/{tcgplayer_id}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "pokemon-products-id-linker/1.0",
        },
    )

    for attempt in range(retries + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)

            if not isinstance(payload, dict):
                raise ApiError(f"Unexpected API response for TCGplayer ID {tcgplayer_id}")
            product = payload.get("product")
            if not payload.get("success") or not isinstance(product, dict):
                raise ApiError(f"Unexpected API response for TCGplayer ID {tcgplayer_id}")

            response_id = str(product.get("product_id", payload.get("product_id", "")))
            if response_id != tcgplayer_id:
                raise ApiError(
                    f"API returned product {response_id!r} for TCGplayer ID {tcgplayer_id}"
                )

            return product.get("cardmarket_id"), product.get("cardtrader_id")
        except HTTPError as error:
            if error.code == 404:
                raise ApiError(f"TCGplayer ID {tcgplayer_id} was not found") from error
            if error.code not in RETRYABLE_STATUS_CODES or attempt == retries:
                raise ApiError(
                    f"TCG Tracking returned HTTP {error.code} for ID {tcgplayer_id}"
                ) from error
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            if attempt == retries:
                raise ApiError(f"Request failed for TCGplayer ID {tcgplayer_id}: {error}") from error

        time.sleep(0.5 * (2**attempt))

    raise AssertionError("retry loop exited unexpectedly")


def add_link_fields(
    product: dict[str, Any],
    cardmarket_id: int | None,
    cardtrader_id: int | None,
) -> dict[str, Any]:
    """Place marketplace IDs directly after ``tcgplayer_id`` in a record."""
    linked: dict[str, Any] = {}
    for key, value in product.items():
        if key not in {"cardmarket_id", "cardtrader_id"}:
            linked[key] = value
        if key == "tcgplayer_id":
            linked["cardmarket_id"] = cardmarket_id
            linked["cardtrader_id"] = cardtrader_id
    return linked


def normalize_tcgplayer_id(raw_id: Any) -> str | None:
    """Normalize an ID, treating common string placeholders as missing."""
    if raw_id is None:
        return None
    tcgplayer_id = str(raw_id).strip()
    if not tcgplayer_id or tcgplayer_id.lower() in {"none", "null", "n/a"}:
        return None
    if not tcgplayer_id.isdecimal():
        raise ValueError(f"invalid TCGplayer ID {raw_id!r}")
    return tcgplayer_id


def atomic_json_dump(data: Any, output_path: Path) -> None:
    """Write JSON without exposing a partially written destination file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary_name, output_path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add Cardmarket and CardTrader IDs to products by looking up each "
            "TCGplayer ID with the TCG Tracking API."
        )
    )
    parser.add_argument("--input", type=Path, default=Path("products.json"))
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON path (default: update the input file)",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=argparse.SUPPRESS)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and report mappings without writing a file",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.workers < 1:
        print("error: --workers must be at least 1", file=sys.stderr)
        return 2
    if args.timeout <= 0 or args.retries < 0:
        print("error: --timeout must be positive and --retries cannot be negative", file=sys.stderr)
        return 2

    try:
        with args.input.open(encoding="utf-8") as handle:
            products = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: could not read {args.input}: {error}", file=sys.stderr)
        return 1

    if not isinstance(products, list) or not all(isinstance(item, dict) for item in products):
        print("error: input JSON must be an array of product objects", file=sys.stderr)
        return 1

    products_by_tcgplayer_id: dict[str, list[int]] = {}
    invalid_ids: list[str] = []
    missing_id_count = 0
    for index, product in enumerate(products):
        try:
            tcgplayer_id = normalize_tcgplayer_id(product.get("tcgplayer_id"))
        except ValueError as error:
            invalid_ids.append(f"product at index {index}: {error}")
            continue
        if tcgplayer_id is None:
            missing_id_count += 1
            continue
        products_by_tcgplayer_id.setdefault(tcgplayer_id, []).append(index)

    if invalid_ids:
        for error in invalid_ids:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(
        f"Looking up {len(products_by_tcgplayer_id)} unique TCGplayer IDs "
        f"for {len(products) - missing_id_count} products "
        f"({missing_id_count} without an ID will be skipped)..."
    )

    links: dict[str, tuple[int | None, int | None]] = {}
    errors: list[str] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                fetch_links,
                tcgplayer_id,
                args.api_base,
                args.timeout,
                args.retries,
            ): tcgplayer_id
            for tcgplayer_id in products_by_tcgplayer_id
        }
        for future in as_completed(futures):
            tcgplayer_id = futures[future]
            try:
                links[tcgplayer_id] = future.result()
            except ApiError as error:
                errors.append(str(error))

    for tcgplayer_id, indexes in products_by_tcgplayer_id.items():
        if tcgplayer_id not in links:
            continue
        cardmarket_id, cardtrader_id = links[tcgplayer_id]
        for index in indexes:
            products[index] = add_link_fields(
                products[index], cardmarket_id, cardtrader_id
            )

    mapped = sum(1 for cardmarket_id, cardtrader_id in links.values() if cardmarket_id or cardtrader_id)
    unmapped = len(links) - mapped
    print(f"Mapped: {mapped}; no marketplace mapping: {unmapped}; errors: {len(errors)}")
    for error in sorted(errors):
        print(f"warning: {error}", file=sys.stderr)

    if errors:
        print("No file was written because one or more lookups failed.", file=sys.stderr)
        return 1

    if not args.dry_run:
        output_path = args.output or args.input
        try:
            atomic_json_dump(products, output_path)
        except OSError as error:
            print(f"error: could not write {output_path}: {error}", file=sys.stderr)
            return 1
        print(f"Wrote {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
