"""One-off fetch of a web page or PDF the user asks to analyse.

Guards: http(s) only, no private or loopback addresses (also after redirects), a size cap,
robots.txt honoured (an unreadable robots.txt counts as a refusal), and an identifying
User-Agent. This is for a single user-chosen URL, not a crawler.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "FinPulseResearchBot/0.1 (academic project; single-page fetch on user request)"
MAX_BYTES = 15 * 1024 * 1024
MAX_REDIRECTS = 3


class FetchRefused(Exception):
    """The URL was not fetched, and the reason is safe to show the user."""


@dataclass(frozen=True, slots=True)
class Fetched:
    url: str
    content_type: str
    body: bytes

    @property
    def is_pdf(self) -> bool:
        return "pdf" in self.content_type.lower() or self.body[:5] == b"%PDF-"


def _check_host(host: str | None) -> None:
    if not host:
        raise FetchRefused("the URL has no host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise FetchRefused(f"cannot resolve {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FetchRefused("only public internet addresses can be fetched")


def _robots_allows(client: httpx.Client, url: str) -> bool:
    parts = urlparse(url)
    robots = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        resp = client.get(robots)
    except httpx.HTTPError:
        return False
    if resp.status_code >= 400:
        return False  # unreadable robots.txt: treated as a refusal
    parser = RobotFileParser()
    parser.parse(resp.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)


def fetch(url: str, *, client: httpx.Client | None = None) -> Fetched:
    own = client is None
    client = client or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=False)
    try:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            parts = urlparse(current)
            if parts.scheme not in {"http", "https"}:
                raise FetchRefused("only http and https URLs can be fetched")
            _check_host(parts.hostname)
            if not _robots_allows(client, current):
                raise FetchRefused("the site's robots.txt does not allow this fetch")
            with client.stream("GET", current) as resp:
                if resp.is_redirect:
                    current = urljoin(current, resp.headers.get("location", ""))
                    continue
                if resp.status_code >= 400:
                    raise FetchRefused(f"the server answered {resp.status_code}")
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise FetchRefused("the file is larger than 15 MB")
                return Fetched(current, resp.headers.get("content-type", ""), bytes(body))
        raise FetchRefused("too many redirects")
    except httpx.HTTPError as exc:
        raise FetchRefused(f"the request failed: {type(exc).__name__}") from exc
    finally:
        if own:
            client.close()
