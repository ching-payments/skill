#!/usr/bin/env python3
"""
Verify a CHING webhook signature against a raw payload.

Useful for one-off debugging when a webhook handler is rejecting events,
or as a reference HMAC-SHA256 implementation to port into your own server.

Examples:
  # Verify a signature you captured from logs
  python3 verify-webhook.py \\
    --secret whsec_abc123 \\
    --signature 0123abcd... \\
    --payload-file ./event.json

  # Verify against payload from stdin (e.g. from curl logs)
  cat event.json | python3 verify-webhook.py \\
    --secret whsec_abc123 \\
    --signature 0123abcd...

  # Compute the expected signature for a payload (no comparison)
  python3 verify-webhook.py --secret whsec_abc123 --payload-file ./event.json --compute
"""

import argparse
import hashlib
import hmac
import sys
from pathlib import Path


def compute(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify(secret: str, payload: bytes, signature: str) -> bool:
    expected = compute(secret, payload)
    return hmac.compare_digest(expected, signature.strip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify or compute a CHING webhook HMAC-SHA256 signature.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--secret",
        required=True,
        help="The whsec_* webhook secret from the CHING dashboard.",
    )
    parser.add_argument(
        "--payload-file",
        type=Path,
        help="Path to the raw payload bytes. If omitted, reads stdin.",
    )
    parser.add_argument(
        "--signature",
        help="The Ching-Signature header value (hex). Required unless --compute.",
    )
    parser.add_argument(
        "--compute",
        action="store_true",
        help="Just print the expected signature and exit.",
    )
    args = parser.parse_args()

    if args.payload_file:
        payload = args.payload_file.read_bytes()
    else:
        payload = sys.stdin.buffer.read()

    if not payload:
        print("error: empty payload", file=sys.stderr)
        return 2

    if args.compute:
        print(compute(args.secret, payload))
        return 0

    if not args.signature:
        print("error: --signature is required (or pass --compute)", file=sys.stderr)
        return 2

    if verify(args.secret, payload, args.signature):
        print("OK: signature matches")
        return 0

    print("FAIL: signature does not match", file=sys.stderr)
    print(f"  expected: {compute(args.secret, payload)}", file=sys.stderr)
    print(f"  got:      {args.signature.strip()}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
