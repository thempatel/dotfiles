#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "requests",
#     "pyyaml",
#     "typer",
# ]
# ///
"""
Fetch markdown docs from any site that exposes .md files at the same URL path.
Uses the site's sitemap.xml to discover pages, then downloads the markdown version.
Maintains a local cache based on lastmod timestamps from the sitemap.

Usage:
    fetch-docs https://docs.getdbt.com
    fetch-docs https://docs.getdbt.com --output dbt-docs
    fetch-docs https://docs.getdbt.com --include /best-practices --include /reference
    fetch-docs https://docs.getdbt.com --exclude /blog --exclude /changelog
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
import typer
import yaml

SKIP_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".xml",
    ".ico",
    ".webp",
    ".pdf",
    ".zip",
}
SITEMAP_NS = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})


def fetch_sitemap(url: str) -> list[dict]:
    """Fetch and parse sitemap XML. Handles sitemap index files recursively."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)

    # Check if this is a sitemap index (contains other sitemaps)
    sitemaps = root.findall("ns:sitemap", SITEMAP_NS)
    if sitemaps:
        entries = []
        for sitemap in sitemaps:
            loc = sitemap.find("ns:loc", SITEMAP_NS)
            if loc is not None and loc.text:
                entries.extend(fetch_sitemap(loc.text))
        return entries

    entries = []
    for url_elem in root.findall("ns:url", SITEMAP_NS):
        loc_elem = url_elem.find("ns:loc", SITEMAP_NS)
        lastmod_elem = url_elem.find("ns:lastmod", SITEMAP_NS)
        if loc_elem is not None and loc_elem.text:
            entries.append(
                {
                    "loc": loc_elem.text,
                    "lastmod": lastmod_elem.text if lastmod_elem is not None else None,
                }
            )
    return entries


def is_asset_url(loc: str) -> bool:
    return any(loc.lower().endswith(ext) for ext in SKIP_EXTENSIONS)


def matches_filters(path: str, include: list[str], exclude: list[str]) -> bool:
    if include and not any(path.startswith(prefix) for prefix in include):
        return False
    if exclude and any(path.startswith(prefix) for prefix in exclude):
        return False
    return True


def url_to_paths(loc: str, base_url: str) -> tuple[str, str] | tuple[None, None]:
    """Convert a sitemap URL to (markdown_url, local_path) or (None, None)."""
    if is_asset_url(loc):
        return None, None

    loc = loc.rstrip("/")
    if not loc.startswith(base_url):
        return None, None

    path_after_base = loc[len(base_url) :]
    if not path_after_base or path_after_base == "/":
        return f"{base_url}/index.md", "index.md"

    path_after_base = path_after_base.lstrip("/")
    # If the path already ends with a known extension, skip it
    if "." in path_after_base.split("/")[-1]:
        return None, None

    return f"{base_url}/{path_after_base}.md", f"{path_after_base}.md"


def read_frontmatter(filepath: Path) -> dict | None:
    if not filepath.exists():
        return None
    content = filepath.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None


def needs_update(filepath: Path, lastmod: str | None) -> bool:
    if lastmod is None:
        return not filepath.exists()
    frontmatter = read_frontmatter(filepath)
    if frontmatter is None:
        return True
    return str(frontmatter.get("lastmod", "")) != str(lastmod)


def write_markdown(
    filepath: Path, content: str, lastmod: str | None, source_url: str
) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    frontmatter = {"source": source_url}
    if lastmod:
        frontmatter["lastmod"] = lastmod
    frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False).strip()
    filepath.write_text(f"---\n{frontmatter_yaml}\n---\n\n{content}", encoding="utf-8")


@app.command()
def main(
    url: str = typer.Argument(
        help="Base URL of the docs site (e.g. https://docs.getdbt.com)"
    ),
    output: Optional[str] = typer.Option(
        None, "-o", "--output", help="Output directory (default: derived from hostname)"
    ),
    include: Optional[list[str]] = typer.Option(
        None, help="Only include URL paths starting with this prefix (repeatable)"
    ),
    exclude: Optional[list[str]] = typer.Option(
        None, help="Exclude URL paths starting with this prefix (repeatable)"
    ),
    sitemap: Optional[str] = typer.Option(
        None, help="Sitemap URL (default: {url}/sitemap.xml)"
    ),
) -> None:
    """Fetch markdown docs from a site's sitemap."""
    base_url = url.rstrip("/")
    parsed = urlparse(base_url)
    sitemap_url = sitemap or f"{base_url}/sitemap.xml"
    output_dir = Path(output) if output else Path(parsed.hostname.replace(".", "-"))

    include = include or []
    exclude = exclude or []

    print(f"Fetching sitemap from {sitemap_url}...")
    try:
        entries = fetch_sitemap(sitemap_url)
    except requests.RequestException as e:
        print(f"Error fetching sitemap: {e}", file=sys.stderr)
        raise typer.Exit(1)
    print(f"Found {len(entries)} URLs in sitemap")

    output_dir.mkdir(parents=True, exist_ok=True)
    stats = {"skipped": 0, "updated": 0, "created": 0, "not_found": 0, "errors": 0}

    for entry in entries:
        loc = entry["loc"]
        lastmod = entry.get("lastmod")

        markdown_url, local_path = url_to_paths(loc, base_url)
        if markdown_url is None:
            stats["skipped"] += 1
            continue

        path_for_filter = loc[len(base_url) :]
        if not matches_filters(path_for_filter, include, exclude):
            stats["skipped"] += 1
            continue

        filepath = output_dir / local_path
        if not needs_update(filepath, lastmod):
            stats["skipped"] += 1
            continue

        action = "Updating" if filepath.exists() else "Creating"
        print(f"  {action}: {local_path}")

        try:
            response = requests.get(markdown_url, timeout=30)
        except requests.RequestException as e:
            print(f"    -> Error: {e}")
            stats["errors"] += 1
            continue

        if response.status_code == 200:
            write_markdown(filepath, response.text, lastmod, loc)
            stats["updated" if action == "Updating" else "created"] += 1
        elif response.status_code == 404:
            stats["not_found"] += 1
        else:
            stats["errors"] += 1
            print(f"    -> HTTP {response.status_code}")

    print(f"\nSummary:")
    print(f"  Created:   {stats['created']}")
    print(f"  Updated:   {stats['updated']}")
    print(f"  Skipped:   {stats['skipped']}")
    print(f"  Not found: {stats['not_found']}")
    print(f"  Errors:    {stats['errors']}")


if __name__ == "__main__":
    app()
