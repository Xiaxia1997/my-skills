#!/usr/bin/env python3
"""Encode untrusted dictation content for safe insertion into the HTML template."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import unicodedata
from typing import Optional, Sequence
from urllib.parse import urlsplit


def html_text(value: str) -> str:
    """Escape a value for an HTML text node or quoted attribute value."""
    return html.escape(value, quote=True)


def safe_href(value: str) -> str:
    """Validate and escape an original media URL for a quoted href attribute."""
    source = value.strip()
    if not source:
        raise ValueError("source URL must not be empty")
    parsed = urlsplit(source)
    scheme = parsed.scheme.casefold()
    if scheme not in {"http", "https", "file"}:
        raise ValueError("source URL must use http, https, or file")
    if scheme in {"http", "https"} and not parsed.netloc:
        raise ValueError("web source URL must include a host")
    if scheme == "file" and not (parsed.netloc or parsed.path):
        raise ValueError("file source URL must include a path")
    return html_text(source)


def js_string(value: str) -> str:
    """Return a JSON string safe inside an HTML script element."""
    encoded = json.dumps(value, ensure_ascii=False)
    return (
        encoded.replace("&", r"\u0026")
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("\u2028", r"\u2028")
        .replace("\u2029", r"\u2029")
    )


def safe_id(value: str) -> str:
    """Create a deterministic ASCII identifier without embedding raw content."""
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").casefold()
    stem = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:48] or "item"
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    return f"{stem}-{digest}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Encode untrusted text for HTML, source URLs, JavaScript, or ASCII identifiers."
    )
    parser.add_argument(
        "--context",
        required=True,
        choices=("html", "attribute", "url", "javascript", "id"),
    )
    parser.add_argument("value", nargs="?", help="Value to encode; stdin is used when omitted")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    value = args.value if args.value is not None else sys.stdin.read()
    if args.context in ("html", "attribute"):
        result = html_text(value)
    elif args.context == "url":
        result = safe_href(value)
    elif args.context == "javascript":
        result = js_string(value)
    else:
        result = safe_id(value)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
