#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "playwright>=1.49",
#     "typer>=0.15",
# ]
# ///
"""
Opens a Chromium instance via Playwright, navigates to the given URL,
and records a HAR file.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

import typer
from playwright.sync_api import sync_playwright, Error

MIME_ALIASES: dict[str, list[str]] = {
    "js": ["application/javascript", "text/javascript", "application/x-javascript"],
    "css": ["text/css"],
    "html": ["text/html"],
    "json": ["application/json"],
    "xml": ["application/xml", "text/xml"],
    "image": ["image/"],
    "font": ["font/", "application/font"],
}


def _sanitize_filename(url: str) -> str:
    """Convert a URL into a filesystem-safe filename."""
    name = re.sub(r"[^\w.\-]", "_", url)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def _filter_har(har: dict, url_match: list[str], mime: list[str]) -> dict:
    """Filter HAR entries by URL substring and MIME type."""
    entries = har.get("log", {}).get("entries", [])

    if url_match:
        entries = [
            e for e in entries if any(pat in e["request"]["url"] for pat in url_match)
        ]

    if mime:
        mime_prefixes = []
        for m in mime:
            if m in MIME_ALIASES:
                mime_prefixes.extend(MIME_ALIASES[m])
            else:
                mime_prefixes.append(m)
        entries = [
            e
            for e in entries
            if any(
                e["response"]["content"].get("mimeType", "").startswith(prefix)
                for prefix in mime_prefixes
            )
        ]

    har["log"]["entries"] = entries
    return har


def main(
    url: str,
    output: Optional[Path] = typer.Option(
        None, "-o", "--output", help="Output HAR file path"
    ),
    headless: bool = typer.Option(False, help="Run in headless mode"),
    url_match: Optional[list[str]] = typer.Option(
        None,
        "--url-match",
        "-u",
        help="Only include entries whose URL contains this string (repeatable)",
    ),
    mime: Optional[list[str]] = typer.Option(
        None,
        "--mime",
        "-m",
        help="Only include entries matching this MIME type or alias: js, css, html, json, xml, image, font (repeatable)",
    ),
) -> None:
    har_path = output if output else Path.cwd() / f"{_sanitize_filename(url)}.har"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(record_har_path=str(har_path))
        page = context.new_page()
        page.goto(url)

        try:
            while True:
                page.title()
                time.sleep(1)
        except (Error, KeyboardInterrupt):
            pass
        finally:
            context.close()
            browser.close()

    if url_match or mime:
        har_data = json.loads(har_path.read_text())
        total = len(har_data.get("log", {}).get("entries", []))
        har_data = _filter_har(har_data, url_match or [], mime or [])
        filtered = len(har_data.get("log", {}).get("entries", []))
        har_path.write_text(json.dumps(har_data, indent=2))
        typer.echo(f"Filtered {total} → {filtered} entries in {har_path}")


if __name__ == "__main__":
    typer.run(main)
