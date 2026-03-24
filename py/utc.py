#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""Convert fuzzy local time input to UTC."""

import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import typer

# Common timezone aliases that zoneinfo doesn't know about
TZ_ALIASES: dict[str, str] = {
    "EST": "US/Eastern",
    "EDT": "US/Eastern",
    "CST": "US/Central",
    "CDT": "US/Central",
    "MST": "US/Mountain",
    "MDT": "US/Mountain",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "CET": "Europe/Paris",
    "CEST": "Europe/Paris",
    "EET": "Europe/Bucharest",
    "EEST": "Europe/Bucharest",
    "GMT": "UTC",
    "BST": "Europe/London",
    "IST": "Asia/Kolkata",
    "JST": "Asia/Tokyo",
    "KST": "Asia/Seoul",
    "AEST": "Australia/Sydney",
    "AEDT": "Australia/Sydney",
    "NZST": "Pacific/Auckland",
    "NZDT": "Pacific/Auckland",
    "SGT": "Asia/Singapore",
    "HKT": "Asia/Hong_Kong",
    "ICT": "Asia/Bangkok",
    "WET": "Europe/Lisbon",
    "WEST": "Europe/Lisbon",
    "AST": "America/Halifax",
    "NST": "America/St_Johns",
    "AKST": "America/Anchorage",
    "HST": "Pacific/Honolulu",
    "CT": "US/Central",
    "ET": "US/Eastern",
    "MT": "US/Mountain",
    "PT": "America/Los_Angeles",
}

# Time patterns
TIME_12H = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)", re.IGNORECASE)
TIME_24H = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")

# Date patterns
DATE_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?")
DATE_DASH = re.compile(r"(\d{1,2})-(\d{1,2})(?:-(\d{2,4}))?")


def resolve_tz(name: str) -> ZoneInfo:
    """Resolve a timezone name or abbreviation to a ZoneInfo."""
    upper = name.upper()
    if upper in TZ_ALIASES:
        return ZoneInfo(TZ_ALIASES[upper])
    # Try as-is (handles "America/New_York", "UTC", etc.)
    try:
        return ZoneInfo(name)
    except KeyError:
        pass
    # Try case-insensitive match against aliases
    for alias, zonename in TZ_ALIASES.items():
        if alias.lower() == name.lower():
            return ZoneInfo(zonename)
    typer.echo(f"Unknown timezone: {name}", err=True)
    raise typer.Exit(1)


def parse_input(parts: list[str]) -> tuple[datetime, ZoneInfo]:
    """Parse free-form input into a datetime and source timezone."""
    now = datetime.now()
    # Get local timezone
    local_aware = datetime.now(timezone.utc).astimezone()
    try:
        source_tz = ZoneInfo(local_aware.tzinfo.key)
    except (AttributeError, KeyError):
        # Fallback: use the tzname abbreviation
        tzname = local_aware.strftime("%Z")
        try:
            source_tz = resolve_tz(tzname) if tzname else ZoneInfo("UTC")
        except SystemExit:
            source_tz = ZoneInfo("UTC")

    raw = " ".join(parts)

    hour = minute = second = None
    month = day = year = None

    # Extract 12h time
    m = TIME_12H.search(raw)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        second = int(m.group(3)) if m.group(3) else 0
        if m.group(4).lower() == "pm" and hour != 12:
            hour += 12
        elif m.group(4).lower() == "am" and hour == 12:
            hour = 0
        raw = raw[: m.start()] + raw[m.end() :]
    else:
        # Extract 24h time
        m = TIME_24H.search(raw)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
            second = int(m.group(3)) if m.group(3) else 0
            raw = raw[: m.start()] + raw[m.end() :]

    # Extract date (slash)
    m = DATE_SLASH.search(raw)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if m.group(3):
            year = int(m.group(3))
            if year < 100:
                year += 2000
        raw = raw[: m.start()] + raw[m.end() :]
    else:
        # Extract date (dash)
        m = DATE_DASH.search(raw)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            if m.group(3):
                year = int(m.group(3))
                if year < 100:
                    year += 2000
            raw = raw[: m.start()] + raw[m.end() :]

    # Remaining tokens: look for timezone
    remaining = raw.strip().split()
    for token in remaining:
        token_clean = token.strip(",").strip()
        if not token_clean:
            continue
        try:
            source_tz = resolve_tz(token_clean)
        except SystemExit:
            typer.echo(f"Could not parse: {token_clean}", err=True)
            raise typer.Exit(1)

    # Defaults
    if hour is None:
        typer.echo("No time found in input.", err=True)
        raise typer.Exit(1)
    if year is None:
        year = now.year
    if month is None:
        month = now.month
    if day is None:
        day = now.day

    try:
        dt = datetime(year, month, day, hour, minute, second)
    except ValueError as e:
        typer.echo(f"Invalid date/time: {e}", err=True)
        raise typer.Exit(1)

    return dt, source_tz


app = typer.Typer(add_completion=False)


@app.command()
def main(
    input_parts: list[str] = typer.Argument(
        help="Fuzzy time input, e.g. '17:12', '17:12 cet', '03/23 5:12 pm'"
    ),
    fmt: str = typer.Option(
        None,
        "-f",
        help="Output format: 's' for epoch seconds, 'ms' for epoch milliseconds. Default: ISO 8601.",
    ),
) -> None:
    """Convert a fuzzy time input to UTC.

    Examples:
        utc 17:12              -> that time today in local tz -> UTC
        utc 17:12 cet          -> 17:12 CET -> UTC
        utc 03/23 17:12        -> March 23 this year, 17:12 local -> UTC
        utc 03/23 5:12 pm      -> March 23 this year, 5:12 PM local -> UTC
        utc 03/23 5:12 pm pst  -> March 23 this year, 5:12 PM PST -> UTC
        utc -f s 17:12         -> epoch seconds
        utc -f ms 17:12        -> epoch milliseconds
    """
    dt, source_tz = parse_input(input_parts)
    aware = dt.replace(tzinfo=source_tz)
    utc_dt = aware.astimezone(timezone.utc)

    if fmt == "s":
        output = str(int(utc_dt.timestamp()))
    elif fmt == "ms":
        output = str(int(utc_dt.timestamp() * 1000))
    else:
        output = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    end = "" if not sys.stdout.isatty() else "\n"
    sys.stdout.write(output + end)


if __name__ == "__main__":
    app()
