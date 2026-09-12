"""Allowlisted public-source retrieval. Source text is evidence, never agent instructions."""

import hashlib
import ipaddress
import json
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pymupdf

REGISTRY = Path(__file__).resolve().parents[1] / "data" / "source_registry.json"
MAX_BYTES = 2 * 1024 * 1024


def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def validate_url(url: str, host: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != host or parsed.port not in (None, 443):
        raise ValueError("Source URL is outside the approved HTTPS host.")
    if parsed.username or parsed.password:
        raise ValueError("Source URL cannot contain credentials.")
    for answer in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(answer[4][0])
        if not address.is_global:
            raise ValueError("Source host resolved to a non-public address.")


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def retrieve(entry: dict):
    """Fetch one fixed registry entry; never send personal data or follow redirects."""
    url = entry["url"]
    validate_url(url, entry["host"])
    with httpx.Client(timeout=12, follow_redirects=False, trust_env=False) as client:
        with client.stream("GET", url, headers={"Accept": "text/html,application/pdf"}) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError("Source redirect requires administrator review.")
            mime = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if mime not in {"text/html", "application/pdf"}:
                raise ValueError("Unsupported source content type.")
            content = bytearray()
            for chunk in response.iter_bytes():
                content.extend(chunk)
                if len(content) > MAX_BYTES:
                    raise ValueError("Source exceeds the retrieval limit.")
    raw = bytes(content)
    if mime == "application/pdf":
        with pymupdf.open(stream=raw, filetype="pdf") as document:
            if document.is_encrypted or len(document) > 20:
                raise ValueError("Source PDF cannot be processed automatically.")
            extracted = "\n".join(page.get_text() for page in document)
    else:
        parser = VisibleText()
        parser.feed(raw.decode("utf-8", errors="replace"))
        extracted = " ".join(parser.parts)
    return {
        "source_id": entry["id"],
        "url": url,
        "mime": mime,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "fetched_at": datetime.now(timezone.utc),
        "excerpt": " ".join(extracted.split())[:12000],
        "verification": "unreviewed",
    }
