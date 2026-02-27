#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""
bun-extract.py - Extract the bundled JS source from a Bun standalone binary.

Bun standalone binaries embed JS in a __BUN/__bun Mach-O section.
This script extracts all significant text blocks from that section.

Examples:
    bun-extract.py $(which binary)
    bun-extract.py /path/to/binary -o /tmp/extracted
    bun-extract.py $(which binary) --all
"""

from __future__ import annotations

import mmap
import struct
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer

app = typer.Typer(
    help="Extract bundled JS from a Bun standalone binary.",
    add_completion=False,
    no_args_is_help=True,
)


def resolve_binary(path: Path) -> Path:
    """Resolve symlinks to get the actual binary."""
    resolved = path.resolve()
    if not resolved.exists():
        typer.echo(f"Error: {resolved} does not exist", err=True)
        raise typer.Exit(1)
    return resolved


def get_bun_section(binary: Path) -> tuple[int, int]:
    """Find the __BUN/__bun section offset and size using otool."""
    try:
        result = subprocess.run(
            ["otool", "-l", str(binary)],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        typer.echo("Error: otool not found (are you on macOS?)", err=True)
        raise typer.Exit(1)

    lines = result.stdout.splitlines()
    in_bun_segment = False
    in_bun_section = False
    offset = 0
    size = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if "segname __BUN" in stripped:
            in_bun_segment = True
            continue
        if in_bun_segment and "sectname __bun" in stripped:
            in_bun_section = True
            continue
        if in_bun_section:
            if stripped.startswith("size"):
                size = int(stripped.split()[-1], 16)
            elif stripped.startswith("offset"):
                offset = int(stripped.split()[-1])
            if offset and size:
                return offset, size

    typer.echo("Error: no __BUN/__bun section found. Is this a Bun binary?", err=True)
    raise typer.Exit(1)


def extract_text_blocks(
    data: bytes, min_size: int = 512
) -> list[tuple[int, int, bytes]]:
    """Find contiguous non-null text blocks in binary data."""
    blocks: list[tuple[int, int, bytes]] = []
    pos = 0
    length = len(data)

    while pos < length:
        # Skip null bytes
        while pos < length and data[pos] == 0:
            pos += 1
        if pos >= length:
            break

        start = pos
        while pos < length and data[pos] != 0:
            pos += 1

        size = pos - start
        if size >= min_size:
            blocks.append((start, size, data[start : start + size]))

    return blocks


@app.command()
def main(
    binary: Annotated[
        Path,
        typer.Argument(help="Path to the Bun standalone binary"),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "-o", "--output", help="Output directory (default: ./<name>-extracted)"
        ),
    ] = None,
    all_blocks: Annotated[
        bool,
        typer.Option(
            "--all", help="Extract all text blocks, not just the main JS bundle"
        ),
    ] = False,
    min_size: Annotated[
        int,
        typer.Option("--min-size", help="Minimum block size in bytes (with --all)"),
    ] = 512,
) -> None:
    """Extract bundled JS from a Bun standalone binary."""
    binary = resolve_binary(binary)
    name = binary.name

    if output is None:
        output = Path.cwd() / f"{name}-extracted"

    output.mkdir(parents=True, exist_ok=True)

    # Find the __BUN section
    offset, size = get_bun_section(binary)
    typer.echo(
        f"Found __BUN section: offset={offset}, size={size} ({size / 1024 / 1024:.1f} MB)"
    )

    # Memory-map the binary and extract the section
    with open(binary, "rb") as f:
        mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        section_data = mm[offset : offset + size]
        mm.close()

    if all_blocks:
        blocks = extract_text_blocks(section_data, min_size=min_size)
        typer.echo(f"Found {len(blocks)} text blocks (>= {min_size} bytes)")

        for i, (blk_offset, blk_size, data) in enumerate(blocks):
            # Detect if it looks like JS
            try:
                text = data[:200].decode("utf-8", errors="strict")
                is_text = True
            except UnicodeDecodeError:
                is_text = False

            if is_text:
                ext = (
                    ".js"
                    if any(
                        k in text[:500]
                        for k in (
                            "function",
                            "var ",
                            "const ",
                            "import ",
                            "export ",
                            "//",
                        )
                    )
                    else ".txt"
                )
            else:
                ext = ".bin"

            out_path = output / f"block-{i:04d}-{blk_size}{ext}"
            out_path.write_bytes(data)
            preview = data[:60].decode("utf-8", errors="replace").replace("\n", "\\n")
            typer.echo(f"  {out_path.name} ({blk_size / 1024:.0f} KB): {preview}...")
    else:
        # Just extract the main JS bundle (first large block starting with // or var)
        blocks = extract_text_blocks(section_data, min_size=10000)
        if not blocks:
            typer.echo("Error: no JS bundle found in __BUN section", err=True)
            raise typer.Exit(1)

        _, blk_size, data = blocks[0]
        out_path = output / f"{name}-bundle.js"
        out_path.write_bytes(data)
        lines = data.count(b"\n") + 1
        typer.echo(
            f"Extracted {blk_size / 1024 / 1024:.1f} MB ({lines} lines) -> {out_path}"
        )


if __name__ == "__main__":
    app()
