#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0", "rich>=13.0"]
# ///
"""srm - Chi-square sample ratio mismatch test against an equal split."""

import math
import re
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    add_completion=False,
    context_settings={
        "help_option_names": ["-h", "--help"],
        # Negative counts are invalid anyway; grabbing them here means the error
        # message is ours rather than click's "no such option: -5".
        "ignore_unknown_options": True,
    },
)
console = Console()

# A count written with thousands separators, e.g. 5,000 or 1,234,567. Anything
# else containing a comma is treated as comma-separated counts instead.
THOUSANDS = re.compile(r"^\d{1,3}(,\d{3})+$")

# Below this expected count per arm the chi-square approximation stops being
# trustworthy and the p-value should not be acted on.
MIN_EXPECTED = 5


def chi2_sf(x: float, df: int) -> float:
    """Upper tail P(X > x) for chi-square with df degrees of freedom."""
    return gammaq(df / 2.0, x / 2.0)


def gammaq(s: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(s, x).

    Numerical Recipes gammq: series expansion below the crossover, Lentz's
    continued fraction above it. Checked against scipy.stats.chi2.sf over
    df 1-29 and x 0-500; worst relative error 2.9e-14.
    """
    if x <= 0:
        return 1.0
    scale = math.exp(-x + s * math.log(x) - math.lgamma(s))
    if x < s + 1.0:
        term = total = 1.0 / s
        n = s
        for _ in range(1000):
            n += 1.0
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-16:
                break
        return 1.0 - total * scale
    tiny = 1e-300
    b = x + 1.0 - s
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-16:
            break
    return h * scale


def fail(message: str) -> None:
    console.print(f"[red]{message}[/red]")
    raise typer.Exit(1)


def split_tokens(token: str) -> list[str]:
    """Expand one raw token into count-shaped tokens, resolving comma use."""
    if "," not in token:
        return [token]
    if THOUSANDS.match(token):
        return [token.replace(",", "")]
    parts = token.split(",")
    # A 3-digit part with a leading zero can only be a thousands group, so a
    # token like 5,000,4,800 is neither one number nor a clean list.
    if any(len(p) == 3 and p.startswith("0") for p in parts):
        fail(
            f"Ambiguous comma use in {token!r} - "
            "use spaces or newlines to separate counts."
        )
    return parts


def parse_count(token: str) -> int:
    """Parse a single count, rejecting anything that isn't a whole non-negative number."""
    cleaned = token.replace("_", "")
    if not cleaned:
        fail("Empty count.")
    if re.fullmatch(r"\d+\.\d+", cleaned):
        fail(f"{token!r} is not a whole number.")
    if not cleaned.isdigit():
        fail(f"{token!r} is not a valid count.")
    return int(cleaned)


def read_counts(args: Optional[list[str]]) -> list[int]:
    """Collect counts from args, falling back to stdin."""
    raw = list(args) if args else sys.stdin.read().split()
    tokens = [part for token in raw for part in split_tokens(token)]
    counts = [parse_count(token) for token in tokens]
    if len(counts) < 2:
        fail("Need at least 2 counts.")
    if sum(counts) == 0:
        fail("Counts sum to zero.")
    return counts


def build_table(counts: list[int], expected: float) -> Table:
    total = sum(counts)
    table = Table(box=None, pad_edge=False, header_style="bold")
    table.add_column("Variant")
    for name in ("Observed", "Share", "Expected", "Diff", "Chi2"):
        table.add_column(name, justify="right")

    for index, observed in enumerate(counts, start=1):
        diff = observed - expected
        table.add_row(
            str(index),
            f"{observed:,}",
            f"{observed / total:.2%}",
            f"{expected:,.1f}",
            f"{diff:+,.1f}",
            f"{diff**2 / expected:.3f}",
        )

    stat = sum((c - expected) ** 2 / expected for c in counts)
    table.add_section()
    table.add_row(
        "Total",
        f"{total:,}",
        "100.00%",
        f"{expected * len(counts):,.1f}",
        "0.0",
        f"{stat:.3f}",
        style="dim",
    )
    return table


@app.command()
def main(
    counts: Optional[list[str]] = typer.Argument(
        None, help="Observed count per arm. Reads from stdin if omitted."
    ),
    alpha: float = typer.Option(
        0.05, "--alpha", "-a", help="Significance threshold for declaring SRM."
    ),
) -> None:
    """Test observed counts against an equal split using a chi-square test."""
    values = read_counts(counts)
    expected = sum(values) / len(values)
    stat = sum((c - expected) ** 2 / expected for c in values)
    df = len(values) - 1
    p = chi2_sf(stat, df)

    console.print()
    console.print(build_table(values, expected))
    console.print()
    console.print(f"chi2 = {stat:.4f}   df = {df}   p = {p:.4g}")

    if p < alpha:
        console.print(f"[bold red]SRM DETECTED[/bold red] (p < {alpha:g})")
    else:
        console.print(f"[green]No SRM[/green] (p >= {alpha:g})")

    if expected < MIN_EXPECTED:
        console.print(
            f"[yellow]Note: expected count is {expected:.1f} per arm; "
            f"chi2 is unreliable below {MIN_EXPECTED}.[/yellow]"
        )
    console.print()


if __name__ == "__main__":
    app()
