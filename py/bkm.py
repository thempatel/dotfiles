#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer"]
# ///
"""bkm - Fuzzy find Chrome bookmarks and history across every profile, then open.

  enter   open in the profile the row belongs to
  ctrl-o  open in the frontmost Chrome window instead
  ctrl-y  copy the url
  tab     mark several

Rows are "type  profile  url  name". The url column is shortened so the name
stays on screen; the full url rides along in a hidden field, so what gets opened
is always the real one.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import urllib.parse
from pathlib import Path

import typer

CHROME = Path.home() / "Library/Application Support/Google/Chrome"
# Routing to a profile only works when the binary is invoked directly. Going
# through `open -na ... --args --profile-directory=X` silently opens nothing.
CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
URL_WIDTH = 45

# Chrome counts microseconds from 1601 in both date_added and last_visit_time,
# so the two are directly comparable without converting either.
NOISE_HOSTS = ("login.", "accounts.", "auth.", "sso.")
NOISE_PATHS = ("/oauth", "/login", "/signin", "/callback")

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def profiles() -> dict[str, str]:
    """Map each profile directory to the name Chrome itself displays for it."""
    state = json.loads((CHROME / "Local State").read_text())
    return {
        d: info.get("name", d) for d, info in state["profile"]["info_cache"].items()
    }


def shorten(url: str) -> str:
    bare = url.split("://", 1)[-1]
    return bare if len(bare) <= URL_WIDTH else bare[: URL_WIDTH - 1] + "…"


def clean(text: str) -> str:
    """Tabs delimit our fields and newlines delimit our rows, so neither can
    survive inside one."""
    return text.replace("\t", " ").replace("\n", " ")


def is_noise(url: str, title: str) -> bool:
    """Pages that exist only because you passed through them — search results,
    auth hops, extension and file URLs — plus anything with no title to search."""
    if not title.strip():
        return True
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return True
    if (parts.hostname or "").startswith(NOISE_HOSTS):
        return True
    if parts.path.startswith("/search"):
        return True
    return any(p in parts.path for p in NOISE_PATHS)


def visits(directory: str) -> dict[str, tuple[str, int]]:
    """Every url Chrome remembers for a profile, unfiltered, as url -> (title, ts)."""
    path = CHROME / directory / "History"
    if not path.exists():
        return {}
    # Chrome holds a lock on the live database; immutable=1 reads straight past
    # it, which beats copying a 260MB file on every launch.
    uri = "file:" + urllib.parse.quote(str(path)) + "?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    try:
        return {
            url: (title or "", ts)
            for url, title, ts in con.execute(
                "SELECT url, title, last_visit_time FROM urls"
            )
        }
    finally:
        con.close()


def bookmarks(directory: str) -> list[tuple[str, str, int]]:
    """Every bookmark in a profile as (url, name, date_added)."""
    path = CHROME / directory / "Bookmarks"
    if not path.exists():
        return []

    found: list[tuple[str, str, int]] = []

    def walk(node: dict) -> None:
        if node.get("type") == "url":
            found.append(
                (
                    node["url"],
                    clean(node.get("name", "")),
                    int(node.get("date_added", 0)),
                )
            )
            return
        for child in node.get("children", []):
            walk(child)

    for root in json.loads(path.read_text())["roots"].values():
        if isinstance(root, dict):
            walk(root)
    return found


def collect(directory: str, label: str) -> list[tuple]:
    seen = visits(directory)
    rows: list[tuple] = []

    saved = set()
    for url, name, added in bookmarks(directory):
        saved.add(url)
        # A bookmark stands in for its history entry too, so it sorts by whichever
        # contact was more recent — saving it or last opening it.
        rows.append(
            (max(added, seen.get(url, ("", 0))[1]), "bookmark", label, url, name)
        )

    for url, (title, ts) in seen.items():
        if url not in saved and not is_noise(url, title):
            rows.append((ts, "history", label, url, clean(title)))

    return rows


def launch(url: str, directory: str | None) -> None:
    if directory:
        args = [CHROME_BIN, f"--profile-directory={directory}", url]
    else:
        args = ["open", "-a", "Google Chrome", url]
    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


@app.command()
def main(
    query: list[str] = typer.Argument(None, help="Initial fzf query"),
) -> None:
    rows: list[tuple] = []
    directories = profiles()
    for directory, label in directories.items():
        rows += [(*r, directory) for r in collect(directory, label)]

    if not rows:
        typer.secho("no bookmarks or history found", fg="red", err=True)
        raise typer.Exit(1)

    rows.sort(key=lambda r: r[0], reverse=True)

    wt = max(len(r[1]) for r in rows)
    wp = max(len(r[2]) for r in rows)
    lines = "".join(
        f"{kind:<{wt}}\t{label:<{wp}}\t{shorten(url):<{URL_WIDTH}}\t{name}\t{d}\t{url}\n"
        for _, kind, label, url, name, d in rows
    )

    # fzf can't search text it doesn't display, so fields 5 and 6 are invisible
    # and unmatchable — but --accept-nth still reads them, which is how the real
    # url and the profile to route to come back out.
    result = subprocess.run(
        [
            "fzf",
            "--delimiter=\t",
            "--with-nth={1} {2} {3} {4}",
            "--accept-nth={5}\t{6}",
            "--multi",
            "--layout=reverse",
            "--expect=ctrl-o",
            "--query=" + " ".join(query or []),
            "--header=enter: open · ctrl-o: frontmost · ctrl-y: copy url · tab: mark",
            "--bind=ctrl-y:execute-silent(printf '%s\\n' {+6} | pbcopy)",
        ],
        input=lines,
        capture_output=True,
        text=True,
    )

    out = result.stdout.splitlines()
    if not out:
        raise typer.Exit(0)

    key, selections = out[0], out[1:]
    for line in selections:
        directory, url = line.split("\t", 1)
        launch(url, None if key == "ctrl-o" else directory)


if __name__ == "__main__":
    app()
