#!/usr/bin/env python3
"""
Convert between shekels (₪) and agorot (the minor unit used by the CHING API).

CHING amount fields are integers in agorot. ₪49.90 is 4990. Off-by-100 bugs
are the most common integration mistake. Use this script when in doubt.

Examples:
  # Shekels to agorot
  python3 agorot-converter.py to-agorot 49.90
  python3 agorot-converter.py to-agorot 199

  # Agorot to shekels (for display)
  python3 agorot-converter.py to-shekels 4990
  python3 agorot-converter.py to-shekels 49900

  # Sanity-check an API request body
  python3 agorot-converter.py audit '{"amount": 4990, "unit_amount": 100}'
"""

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


AMOUNT_KEYS = {
    "amount",
    "amount_agorot",
    "unit_amount",
    "unit_amount_agorot",
    "amount_off",
    "subtotal",
    "total",
}


def shekels_to_agorot(shekels: str) -> int:
    try:
        d = Decimal(shekels)
    except InvalidOperation as e:
        raise ValueError(f"not a number: {shekels!r}") from e
    cents = (d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(cents)


def agorot_to_shekels(agorot: str) -> Decimal:
    try:
        n = int(agorot)
    except ValueError as e:
        raise ValueError(f"not an integer: {agorot!r}") from e
    return (Decimal(n) / Decimal(100)).quantize(Decimal("0.01"))


def audit_payload(raw: str) -> int:
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"error: payload is not valid JSON: {e}", file=sys.stderr)
        return 2
    findings: list[str] = []
    walk(body, "", findings)
    if not findings:
        print("no amount-like fields detected. Nothing to audit.")
        return 0
    for line in findings:
        print(line)
    return 0


def walk(value, path: str, findings: list[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            sub = f"{path}.{k}" if path else k
            if k in AMOUNT_KEYS and isinstance(v, (int, float)):
                shekels = agorot_to_shekels(str(int(v)))
                hint = ""
                if isinstance(v, float):
                    hint = "  (! float; CHING expects integer agorot)"
                findings.append(
                    f"{sub} = {v}  ->  ₪{shekels}{hint}"
                )
            walk(v, sub, findings)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            walk(v, f"{path}[{i}]", findings)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert between shekels and agorot, or audit an API request body.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_to_a = sub.add_parser("to-agorot", help="Convert shekels to agorot.")
    p_to_a.add_argument("shekels", help="Amount in shekels, e.g. 49.90")

    p_to_s = sub.add_parser("to-shekels", help="Convert agorot to shekels.")
    p_to_s.add_argument("agorot", help="Amount in agorot, e.g. 4990")

    p_audit = sub.add_parser(
        "audit",
        help="Audit a JSON payload for amount fields and confirm units.",
    )
    p_audit.add_argument("payload", help="JSON string to audit.")

    args = parser.parse_args()

    if args.cmd == "to-agorot":
        try:
            print(shekels_to_agorot(args.shekels))
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        return 0

    if args.cmd == "to-shekels":
        try:
            print(f"₪{agorot_to_shekels(args.agorot)}")
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        return 0

    if args.cmd == "audit":
        return audit_payload(args.payload)

    return 1


if __name__ == "__main__":
    sys.exit(main())
