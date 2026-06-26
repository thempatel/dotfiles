#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0", "rich>=13.0"]
# ///
"""jwt - Decode and pretty-print the parts of a JWT (no signature verification)."""

import base64
import binascii
import json
import sys
from datetime import datetime, timezone
from typing import Optional

import typer
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)
console = Console()

# Claims whose values are Unix timestamps worth rendering as a readable date.
TIMESTAMP_CLAIMS = ("exp", "iat", "nbf", "auth_time", "updated_at")


def b64url_decode(segment: str) -> bytes:
    """Decode a base64url segment, restoring stripped padding."""
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def humanize_timestamps(claims: dict) -> list[str]:
    """Return readable lines for any timestamp claims present."""
    lines = []
    for key in TIMESTAMP_CLAIMS:
        value = claims.get(key)
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
            lines.append(f"{key}: {dt.isoformat()} ({value})")
    return lines


@app.command()
def main(
    token: Optional[str] = typer.Argument(
        None, help="The JWT to decode. Reads from stdin if omitted."
    ),
) -> None:
    """Decode and pretty-print a JWT's header, payload, and signature."""
    if token is None:
        token = sys.stdin.read()
    token = token.strip()

    parts = token.split(".")
    if len(parts) != 3:
        console.print(
            f"[red]Expected a JWT with 3 dot-separated parts, got {len(parts)}.[/red]"
        )
        raise typer.Exit(1)

    header_seg, payload_seg, signature_seg = parts

    for label, segment in (("Header", header_seg), ("Payload", payload_seg)):
        try:
            data = json.loads(b64url_decode(segment))
        except (binascii.Error, json.JSONDecodeError, UnicodeDecodeError) as exc:
            console.print(f"[red]Failed to decode {label}: {exc}[/red]")
            raise typer.Exit(1)

        console.print(Panel(JSON(json.dumps(data)), title=label, title_align="left"))

        if label == "Payload":
            times = humanize_timestamps(data)
            if times:
                console.print(
                    Panel("\n".join(times), title="Timestamps", title_align="left")
                )

    console.print(
        Panel(
            signature_seg,
            title="Signature (base64url, not verified)",
            title_align="left",
        )
    )


if __name__ == "__main__":
    app()
