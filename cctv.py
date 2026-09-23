#!/usr/bin/env python3
"""Minimal CLI for interacting with home CCTV systems, including Swann cameras."""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass
from typing import Optional
from urllib import error, parse, request


DEFAULT_SNAPSHOT_PATH = "/cgi-bin/snapshot.cgi"
DEFAULT_STATUS_PATH = "/ISAPI/System/status"


def normalize_path(path: str) -> str:
    return path if path.startswith("/") else f"/{path}"


def parse_port(value: str) -> int:
    port = int(value)
    if port < 1 or port > 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def parse_timeout(value: str) -> int:
    timeout = int(value)
    if timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be a positive integer")
    return timeout


def parse_channel(value: str) -> int:
    channel = int(value)
    if channel <= 0:
        raise argparse.ArgumentTypeError("channel must be a positive integer")
    return channel


def detect_charset(content_type: str, default: str = "utf-8") -> str:
    match = re.search(r"charset=([\w.-]+)", content_type, re.IGNORECASE)
    if match:
        return match.group(1)
    return default


@dataclass(frozen=True)
class SwannConfig:
    host: str
    username: Optional[str] = None
    password: Optional[str] = None
    port: Optional[int] = None
    https: bool = False
    timeout: int = 10

    @property
    def base_url(self) -> str:
        scheme = "https" if self.https else "http"
        if self.port:
            return f"{scheme}://{self.host}:{self.port}"
        return f"{scheme}://{self.host}"


def build_basic_auth_header(username: Optional[str], password: Optional[str]) -> Optional[str]:
    if username is None:
        return None
    token = base64.b64encode(f"{username}:{password or ''}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


class SwannClient:
    def __init__(self, config: SwannConfig) -> None:
        self.config = config

    def snapshot_url(self, channel: int = 1, path: str = DEFAULT_SNAPSHOT_PATH) -> str:
        parsed_path = parse.urlsplit(normalize_path(path))
        query_pairs = parse.parse_qsl(parsed_path.query, keep_blank_values=True)
        query_pairs.append(("channel", str(channel)))
        query = parse.urlencode(query_pairs)
        query_suffix = f"?{query}" if query else ""
        fragment = f"#{parsed_path.fragment}" if parsed_path.fragment else ""
        return f"{self.config.base_url}{parsed_path.path}{query_suffix}{fragment}"

    def request_response(self, path: str, method: str = "GET", accept: str = "application/json") -> tuple[bytes, Optional[str]]:
        req = request.Request(
            url=f"{self.config.base_url}{normalize_path(path)}",
            method=method,
            headers={"Accept": accept},
        )
        auth_header = build_basic_auth_header(self.config.username, self.config.password)
        if auth_header:
            req.add_header("Authorization", auth_header)
        with request.urlopen(req, timeout=self.config.timeout) as resp:  # nosec B310
            return resp.read(), resp.headers.get("Content-Type")

    def request(self, path: str, method: str = "GET", accept: str = "application/json") -> bytes:
        content, _ = self.request_response(path=path, method=method, accept=accept)
        return content

    def get_status(self, path: str = DEFAULT_STATUS_PATH) -> str:
        content, content_type = self.request_response(
            path=path,
            accept="application/json, application/xml, text/plain",
        )
        return content.decode(detect_charset((content_type or "").lower()), "replace")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with home CCTV, including Swann cameras")
    parser.add_argument("--host", required=True, help="Camera/NVR hostname or IP")
    parser.add_argument("--username", default=None, help="Username for basic auth")
    parser.add_argument("--password", default=None, help="Password for basic auth")
    parser.add_argument("--port", type=parse_port, default=None, help="Camera/NVR port")
    parser.add_argument("--https", action="store_true", help="Use HTTPS instead of HTTP")
    parser.add_argument("--timeout", type=parse_timeout, default=10, help="HTTP timeout in seconds")

    sub = parser.add_subparsers(dest="command", required=True)

    snapshot_url = sub.add_parser("snapshot-url", help="Print snapshot URL for a channel")
    snapshot_url.add_argument("--channel", type=parse_channel, default=1, help="Channel number")
    snapshot_url.add_argument("--path", default=DEFAULT_SNAPSHOT_PATH, help="Snapshot endpoint path")

    status = sub.add_parser("status", help="Fetch camera/NVR status endpoint")
    status.add_argument("--path", default=DEFAULT_STATUS_PATH, help="Status endpoint path")

    raw_request = sub.add_parser("request", help="Perform a raw HTTP request")
    raw_request.add_argument("--path", required=True, help="Endpoint path, e.g. /api/status")
    raw_request.add_argument("--method", default="GET", help="HTTP method")
    raw_request.add_argument("--accept", default="application/json", help="Accept header value")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if (args.username is None) != (args.password is None):
        print("Both --username and --password must be provided together", file=sys.stderr)
        return 4
    client = SwannClient(
        SwannConfig(
            args.host,
            args.username,
            args.password,
            args.port,
            args.https,
            args.timeout,
        )
    )

    try:
        if args.command == "snapshot-url":
            print(client.snapshot_url(channel=args.channel, path=args.path))
            return 0
        if args.command == "status":
            print(client.get_status(path=args.path))
            return 0
        if args.command == "request":
            content, content_type = client.request_response(path=args.path, method=args.method.upper(), accept=args.accept)
            content_type = (content_type or "").lower()
            if "json" in content_type:
                try:
                    encoding = detect_charset(content_type)
                    print(json.dumps(json.loads(content.decode(encoding)), indent=2))
                    return 0
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass
            if content_type.startswith("text/") or "xml" in content_type:
                encoding = detect_charset(content_type)
                print(content.decode(encoding, "replace"))
            else:
                sys.stdout.buffer.write(content)
                if not content.endswith(b"\n"):
                    sys.stdout.buffer.write(b"\n")
            return 0
    except error.HTTPError as exc:
        print(f"HTTP error {exc.code}: {exc.reason}", file=sys.stderr)
        return 2
    except error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        return 3

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
