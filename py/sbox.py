#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""
sbox.py - Isolate a process using macOS sandbox-exec (Seatbelt).

See https://github.com/s7ephen/OSX-Sandbox--Seatbelt--Profiles for example profiles.

Examples:
    sbox.py -- ls -la
    sbox.py -w /tmp/output -- python script.py
    sbox.py -w ~/.config/myapp -- myapp
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
    READ_WRITE = "read-write"  # Convenience for both


class Matcher(Enum):
    """Seatbelt path matcher type."""

    AUTO = "auto"  # subpath for dirs, literal for files
    PREFIX = (
        "prefix"  # matches path as a prefix (e.g. foo.json also covers foo.json.lock)
    )


@dataclass
class PathRule:
    """A rule for a specific path."""

    path: Path
    action: Action
    permission: Permission
    matcher: Matcher = Matcher.AUTO

    def is_dir(self) -> bool:
        """Check if path is a directory."""
        return self.path.is_dir()


@dataclass
class SeatbeltPolicy:
    """Builder for Seatbelt policy files."""

    rules: list[PathRule] = field(default_factory=list)
    allow_keychain: bool = False
    _home: Path = field(default_factory=Path.home)

    def _quote(self, s: str) -> str:
        """Escape a path for Seatbelt policy quoting."""
        return s.replace("\\", "\\\\").replace('"', '\\"')

    def _resolve_matcher(self, path: Path, matcher: Matcher) -> str:
        """Resolve the seatbelt matcher keyword for a path."""
        if matcher == Matcher.PREFIX:
            return "prefix"
        # AUTO: subpath for dirs, literal for files
        return "subpath" if path.is_dir() else "literal"

    def _path_rule(
        self, action: str, permission: str, path: Path, matcher: Matcher = Matcher.AUTO
    ) -> str:
        """Generate a single path rule."""
        path_str = self._quote(str(path))
        kw = self._resolve_matcher(path, matcher)
        return f'({action} {permission} ({kw} "{path_str}"))'

    def add_rule(
        self,
        path: Path,
        action: Action,
        permission: Permission,
        matcher: Matcher = Matcher.AUTO,
    ) -> "SeatbeltPolicy":
        """Add a path rule."""
        self.rules.append(
            PathRule(path=path, action=action, permission=permission, matcher=matcher)
        )
        return self

    def allow_read(self, path: Path) -> "SeatbeltPolicy":
        """Allow read access to a path."""
        return self.add_rule(path, Action.ALLOW, Permission.READ)

    def allow_write(self, path: Path) -> "SeatbeltPolicy":
        """Allow write access to a path."""
        return self.add_rule(path, Action.ALLOW, Permission.WRITE)

    def allow_write_prefix(self, path: Path) -> "SeatbeltPolicy":
        """Allow write access to a path and any path sharing its prefix.

        Useful for files that use atomic writes with .lock/.tmp sidecars.
        """
        return self.add_rule(path, Action.ALLOW, Permission.WRITE, Matcher.PREFIX)

    def allow_read_write(self, path: Path) -> "SeatbeltPolicy":
        """Allow read and write access to a path."""
        return self.add_rule(path, Action.ALLOW, Permission.READ_WRITE)

    def deny_read(self, path: Path) -> "SeatbeltPolicy":
        """Deny read access to a path."""
        return self.add_rule(path, Action.DENY, Permission.READ)

    def deny_write(self, path: Path) -> "SeatbeltPolicy":
        """Deny write access to a path."""
        return self.add_rule(path, Action.DENY, Permission.WRITE)

    def deny_all(self, path: Path) -> "SeatbeltPolicy":
        """Deny all access to a path."""
        return self.add_rule(path, Action.DENY, Permission.READ_WRITE)

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
            if rule.permission == Permission.READ_WRITE:
                # Expand to both read and write
                lines.append(
                    self._path_rule(
                        rule.action.value, "file-read*", rule.path, rule.matcher
                    )
                )
                lines.append(
                    self._path_rule(
                        rule.action.value, "file-write*", rule.path, rule.matcher
                    )
                )
            else:
                lines.append(
                    self._path_rule(
                        rule.action.value,
                        rule.permission.value,
                        rule.path,
                        rule.matcher,
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
        """Add Keychain access rules.

        Reads already work via (allow default). Writes only need the
        file-write* permission on the Keychains directory.
        """
        home_str = self._quote(str(self._home))
        lines.append(f'(allow file-write* (subpath "{home_str}/Library/Keychains"))')


def seatbelt_policy(
    *,
    pwd: Optional[Path] = None,
    write_paths: Optional[list[Path]] = None,
    write_prefix_paths: Optional[list[Path]] = None,
    deny_paths: Optional[list[Path]] = None,
    allow_keychain: bool = False,
) -> str:
    """
    Generate a Seatbelt policy string.

    Args:
        pwd: Working directory to allow writes (defaults to cwd)
        write_paths: Paths to allow write access
        write_prefix_paths: Paths to allow write access via prefix matching
            (also covers .lock, .tmp, and similar sidecars)
        deny_paths: Paths to deny all access
        allow_keychain: If True, allow Keychain access

    Returns:
        Seatbelt policy as a string
    """
    if pwd is None:
        pwd = Path.cwd().resolve()

    policy = SeatbeltPolicy(allow_keychain=allow_keychain)

    # Always allow PWD writes
    policy.allow_write(pwd)

    # Add write paths
    for p in write_paths or []:
        policy.allow_write(p)

    # Add write prefix paths
    for p in write_prefix_paths or []:
        policy.allow_write_prefix(p)

    # Add deny paths
    for p in deny_paths or []:
        policy.deny_all(p)

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


def abs_path(p: str) -> Path:
    """
    Expand ~ and return absolute, symlink-resolved path.
    For non-existent files, ensure parent exists and return absolute would-be path.
    """
    if p.startswith("~"):
        p = os.path.expanduser(p)

    path = Path(p)

    if path.exists():
        return path.resolve()
    else:
        parent = path.parent
        if not parent.exists():
            typer.echo(f"sbox: parent directory does not exist: {parent}", err=True)
            raise typer.Exit(2)
        return parent.resolve() / path.name


def ensure_paths_exist(paths: list[Path]) -> None:
    """Ensure files exist so Seatbelt can reference them."""
    for p in paths:
        if not p.is_dir() and not p.exists():
            p.touch()


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
    write: Annotated[
        Optional[list[str]],
        typer.Option("-w", "--write", help="Allow write access to PATH (repeatable)"),
    ] = None,
    write_prefix: Annotated[
        Optional[list[str]],
        typer.Option(
            "-W",
            "--write-prefix",
            help="Allow write access to PATH and any path sharing its prefix (repeatable)",
        ),
    ] = None,
    deny: Annotated[
        Optional[list[str]],
        typer.Option("--deny", help="Deny all access to PATH (repeatable)"),
    ] = None,
    allow_keychain: Annotated[
        bool,
        typer.Option(
            "--allow-keychain", help="Allow macOS Keychain access (DANGEROUS)"
        ),
    ] = False,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug", help="Print the generated policy and keep the policy file"
        ),
    ] = False,
) -> None:
    """Run a command in a sandboxed environment."""
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

    # Resolve paths
    pwd = Path.cwd().resolve()
    write_paths = [abs_path(p) for p in (write or [])]
    write_prefix_paths = [abs_path(p) for p in (write_prefix or [])]
    deny_paths_resolved = [abs_path(p) for p in (deny or [])]

    # Ensure files exist for Seatbelt
    ensure_paths_exist(write_paths)
    ensure_paths_exist(write_prefix_paths)
    ensure_paths_exist(deny_paths_resolved)

    # Generate policy
    policy = seatbelt_policy(
        pwd=pwd,
        write_paths=write_paths,
        write_prefix_paths=write_prefix_paths,
        deny_paths=deny_paths_resolved,
        allow_keychain=allow_keychain,
    )

    if debug:
        typer.echo("DEBUG: Generated Seatbelt policy:", err=True)
        typer.echo(policy, err=True)
        typer.echo("---", err=True)

    # Exec sandbox-exec with inline policy
    os.execvp("sandbox-exec", ["sandbox-exec", "-p", policy] + command)


if __name__ == "__main__":
    app()
