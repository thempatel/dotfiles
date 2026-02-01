#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""
sbox.py - Isolate a process using macOS sandbox-exec (Seatbelt).

See https://github.com/s7ephen/OSX-Sandbox--Seatbelt--Profiles for example profiles.

Reads seatbelt policies from stdin or a file (one per line):
    +/path/to/dir      Allow read access (subpath for dirs, literal for files)
    ++/path/to/dir     Allow write access (subpath for dirs, literal for files)
    +/path/to/dir/     Trailing slash forces subpath (directory) even if path doesn't exist
    +~regex_pattern    Allow read using regex match
    ++~regex_pattern   Allow write using regex match
    -/path/to/dir      Deny all access
    -~regex_pattern    Deny all access using regex match
    keychain           Allow keychain access

Examples:
    echo "+/tmp/output" | sbox.py -- python script.py
    sbox.py -f policies.txt -- myapp
    sbox.py -- ls -la
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer


# --- Seatbelt Policy Builder ---


class Action(Enum):
    """Seatbelt action type."""

    ALLOW = "allow"
    DENY = "deny"


class Permission(Enum):
    """Seatbelt permission type."""

    READ = "file-read*"
    WRITE = "file-write*"


class MatchType(Enum):
    """Seatbelt path matching type."""

    LITERAL = "literal"
    SUBPATH = "subpath"
    REGEX = "regex"


@dataclass
class PathRule:
    """A rule for a specific path."""

    path: str  # Can be a path or regex pattern
    action: Action
    permission: Permission
    match_type: Optional[MatchType] = None  # None = auto-detect from path

    def get_match_type(self) -> MatchType:
        """Get the match type, auto-detecting if not specified."""
        if self.match_type is not None:
            return self.match_type
        # Auto-detect: if it's a directory, use subpath; otherwise literal
        p = Path(self.path)
        return MatchType.SUBPATH if p.is_dir() else MatchType.LITERAL


@dataclass
class SeatbeltPolicy:
    """Builder for Seatbelt policy files."""

    rules: list[PathRule] = field(default_factory=list)
    allow_keychain: bool = False
    _home: Path = field(default_factory=Path.home)

    def _quote(self, s: str) -> str:
        """Escape a path for Seatbelt policy quoting."""
        return s.replace("\\", "\\\\").replace('"', '\\"')

    def _path_rule(
        self, action: str, permission: str, path_str: str, match_type: MatchType
    ) -> str:
        """Generate a single path rule."""
        if match_type == MatchType.REGEX:
            # Only escape quotes for regex, preserve backslashes for regex escapes
            quoted = path_str.replace('"', '\\"')
            return f'({action} {permission} ({match_type.value} #"{quoted}"))'
        quoted = self._quote(path_str)
        return f'({action} {permission} ({match_type.value} "{quoted}"))'

    def add_rule(
        self,
        path: str,
        action: Action,
        permission: Permission,
        match_type: Optional[MatchType] = None,
    ) -> None:
        """Add a path rule."""
        self.rules.append(
            PathRule(
                path=path, action=action, permission=permission, match_type=match_type
            )
        )

    def allow_read(self, path: str, match_type: Optional[MatchType] = None) -> None:
        """Allow read access to a path."""
        self.add_rule(path, Action.ALLOW, Permission.READ, match_type)

    def allow_write(self, path: str, match_type: Optional[MatchType] = None) -> None:
        """Allow write access to a path."""
        self.add_rule(path, Action.ALLOW, Permission.WRITE, match_type)

    def deny_read(self, path: str, match_type: Optional[MatchType] = None) -> None:
        """Deny read access to a path."""
        self.add_rule(path, Action.DENY, Permission.READ, match_type)

    def deny_write(self, path: str, match_type: Optional[MatchType] = None) -> None:
        """Deny write access to a path."""
        self.add_rule(path, Action.DENY, Permission.WRITE, match_type)

    def deny_read_write(
        self, path: str, match_type: Optional[MatchType] = None
    ) -> None:
        """Deny read and write access to a path."""
        self.add_rule(path, Action.DENY, Permission.READ, match_type)
        self.add_rule(path, Action.DENY, Permission.WRITE, match_type)

    def render(self) -> str:
        """Render the complete Seatbelt policy."""
        lines: list[str] = []

        # Version and defaults
        lines.append("(version 1)")
        lines.append("(allow default)")

        # Deny ALL file writes first (global default)
        lines.append("(deny file-write*)")

        # Process rules in order
        for rule in self.rules:
            match_type = rule.get_match_type()
            lines.append(
                self._path_rule(
                    rule.action.value, rule.permission.value, rule.path, match_type
                )
            )

        # System paths that are always needed
        self._add_system_paths(lines)

        # Keychain access if enabled
        if self.allow_keychain:
            self._add_keychain_rules(lines)

        return "\n".join(lines)

    def _add_system_paths(self, lines: list[str]) -> None:
        """Add system paths that are always needed."""
        # Allow execution of specific setuid binaries that are commonly needed.
        # Without this, sandbox blocks them with "forbidden-exec-sugid".
        # The "(with no-sandbox)" modifier allows executing setuid binaries.
        for binary in [
            "/bin/ps",
            "/usr/bin/top",
        ]:
            lines.append(f'(allow process-exec (with no-sandbox) (literal "{binary}"))')

        # Temp directories
        for tmp in [
            "/tmp",
            "/var/tmp",
            "/var/folders",
            "/private/var/folders",
            "/private/tmp",
        ]:
            lines.append(f'(allow file-write* (subpath "{tmp}"))')

        # Device files
        for dev in [
            "/dev/null",
            "/dev/zero",
            "/dev/random",
            "/dev/urandom",
            "/dev/tty",
            "/dev/stdin",
            "/dev/stdout",
            "/dev/stderr",
            "/dev/fd",
            "/dev/dtracehelper",
        ]:
            lines.append(f'(allow file-write* (literal "{dev}"))')

        # User's Library folders
        home_str = self._quote(str(self._home))
        lines.append(f'(allow file-write* (subpath "{home_str}/Library/Caches"))')
        lines.append(f'(allow file-write* (subpath "{home_str}/Library/Logs"))')
        lines.append(
            f'(allow file-write* (subpath "{home_str}/Library/Application Support"))'
        )

    def _add_keychain_rules(self, lines: list[str]) -> None:
        """Add Keychain access rules."""
        home_str = self._quote(str(self._home))
        lines.append(f'(allow file-read* (subpath "{home_str}/Library/Keychains"))')
        lines.append('(allow file-read* (subpath "/Library/Keychains"))')
        lines.append(f'(allow file-write* (subpath "{home_str}/Library/Keychains"))')
        lines.append("(allow system-mac-syscall (syscall-number 73))")
        lines.append('(allow mach-lookup (global-name "com.apple.securityd"))')
        lines.append(
            '(allow mach-lookup (global-name "com.apple.security.othersigning"))'
        )
        lines.append(
            '(allow mach-lookup (global-name "com.apple.security.credentialstore"))'
        )


def parse_path_suffix(path: str) -> tuple[str, Optional[MatchType]]:
    """
    Parse path suffix to determine explicit match type.

    Trailing '/' forces subpath (directory) even if path doesn't exist.

    Returns:
        Tuple of (cleaned_path, match_type) where match_type is None for auto-detect.
    """
    if path.endswith("/"):
        return (path[:-1], MatchType.SUBPATH)
    return (path, None)


def parse_policy_line(line: str) -> Optional[tuple[str, str, Optional[MatchType]]]:
    """
    Parse a single policy line.

    Format:
        +/path/to/dir      Allow read (auto-detect literal/subpath)
        ++/path/to/dir     Allow write (auto-detect literal/subpath)
        +/path/to/dir/     Trailing slash forces subpath (directory)
        ++/path/to/file:   Trailing colon forces literal (file)
        +~regex_pattern    Allow read using regex match
        ++~regex_pattern   Allow write using regex match
        -/path/to/dir      Deny all access
        -~regex_pattern    Deny all access using regex match
        keychain           Allow keychain access (returns special marker)
        # comment          Ignored

    Returns:
        Tuple of (action, path, match_type) or None for empty/comment lines.
        For 'keychain', returns ('keychain', '', None).
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    if line == "keychain":
        return ("keychain", "", None)

    if len(line) < 2:
        return None

    prefix = line[0]
    rest = line[1:]

    if prefix == "+":
        # Check for ++ (allow write) vs + (allow read)
        if rest.startswith("+"):
            # Check for ++~ (allow write regex)
            if rest.startswith("+~"):
                return ("++", rest[2:], MatchType.REGEX)
            path, match_type = parse_path_suffix(rest[1:])
            return ("++", path, match_type)
        # Check for +~ (allow read regex)
        if rest.startswith("~"):
            return ("+", rest[1:], MatchType.REGEX)
        path, match_type = parse_path_suffix(rest)
        return ("+", path, match_type)
    elif prefix == "-":
        # Deny all access - check for regex with -~
        if rest.startswith("~"):
            return ("-", rest[1:], MatchType.REGEX)
        path, match_type = parse_path_suffix(rest)
        return ("-", path, match_type)

    return None


def build_policy_from_lines(lines: list[str]) -> str:
    """
    Build a Seatbelt policy from policy lines.

    Args:
        lines: List of policy lines to parse
        pwd: Working directory to allow writes (defaults to cwd)

    Returns:
        Seatbelt policy as a string
    """
    allow_keychain = False
    policy = SeatbeltPolicy()

    for line in lines:
        parsed = parse_policy_line(line)
        if parsed is None:
            continue

        action, path_or_pattern, match_type = parsed

        if action == "keychain":
            allow_keychain = True
            continue

        # Expand ~ in paths (but not for regex patterns)
        if match_type != MatchType.REGEX and path_or_pattern.startswith("~"):
            path_or_pattern = os.path.expanduser(path_or_pattern)

        # Resolve to absolute path for non-regex
        if match_type != MatchType.REGEX:
            p = Path(path_or_pattern)
            if p.exists():
                path_or_pattern = str(p.resolve())
            elif p.parent.exists():
                path_or_pattern = str(p.parent.resolve() / p.name)

        if action == "++":
            policy.allow_write(path_or_pattern, match_type)
        elif action == "+":
            policy.allow_read(path_or_pattern, match_type)
        elif action == "-":
            policy.deny_read_write(path_or_pattern, match_type)

    policy.allow_keychain = allow_keychain
    return policy.render()


# --- CLI ---


def check_macos() -> None:
    """Ensure we're running on macOS."""
    if platform.system() != "Darwin":
        typer.echo("sbox: This script only works on macOS", err=True)
        raise typer.Exit(1)


def check_sandbox_exec() -> None:
    """Ensure sandbox-exec is available."""
    if shutil.which("sandbox-exec") is None:
        typer.echo("sbox: sandbox-exec not found on this macOS", err=True)
        raise typer.Exit(127)


def read_policy_lines(file_path: Optional[Path]) -> list[str]:
    """
    Read policy lines from a file or stdin.

    Args:
        file_path: Path to policy file, or None to read from stdin

    Returns:
        List of policy lines
    """
    if file_path is not None:
        if not file_path.exists():
            typer.echo(f"sbox: policy file not found: {file_path}", err=True)
            raise typer.Exit(2)
        return file_path.read_text().splitlines()

    # Read from stdin if available
    if not sys.stdin.isatty():
        return sys.stdin.read().splitlines()

    return []


app = typer.Typer(
    help="Isolate a process using macOS sandbox-exec (Seatbelt).",
    add_completion=False,
    no_args_is_help=True,
)


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def main(
    ctx: typer.Context,
    policy_file: Annotated[
        Optional[Path],
        typer.Option("-f", "--file", help="Read policies from FILE instead of stdin"),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug", help="Print the generated policy and keep the policy file"
        ),
    ] = False,
) -> None:
    """
    Run a command in a sandboxed environment.

    Reads policies from stdin or a file (-f). Each line specifies a rule:
    +/path/to/dir      Allow read access (auto-detect subpath/literal)
    ++/path/to/dir     Allow write access (auto-detect subpath/literal)
    +/path/to/dir/     Trailing slash forces subpath (directory)
    +~regex_pattern    Allow read using regex match
    ++~regex_pattern   Allow write using regex match
    -/path/to/dir      Deny all access
    -~regex_pattern    Deny all access using regex match
    keychain           Allow keychain access
    # comment          Ignored
    """
    check_macos()
    check_sandbox_exec()

    # Get command from extra args (everything after --)
    command = ctx.args
    if not command:
        typer.echo("Error: No command specified. Use -- <command> [args...]", err=True)
        raise typer.Exit(1)

    # Strip leading -- if present
    if command[0] == "--":
        command = command[1:]

    if not command:
        typer.echo("Error: No command specified after --", err=True)
        raise typer.Exit(1)

    # Read policy lines from file or stdin
    policy_lines = read_policy_lines(policy_file)

    # Generate policy
    policy = build_policy_from_lines(policy_lines)

    if debug:
        typer.echo("DEBUG: Generated Seatbelt policy:", err=True)
        typer.echo(policy, err=True)
        typer.echo("---", err=True)

    # Exec sandbox-exec with inline policy
    os.execvp("sandbox-exec", ["sandbox-exec", "-p", policy] + command)


if __name__ == "__main__":
    app()
