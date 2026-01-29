#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
sandbox.py - Isolate a process using macOS sandbox-exec (Seatbelt).

Usage:
    sandbox.py [OPTIONS] -- <command> [args...]

Options:
    -w, --write PATH      Allow read-write access to PATH (repeatable)
    --read-only PATH      Allow read-only access to PATH (repeatable)
    --deny PATH           Deny all access to PATH (repeatable)
    --safe                Hide home directory by default (re-expose with --write/--read-only)
    --allow-keychain      Allow macOS Keychain access (DANGEROUS)
    -h, --help            Show this help message

Examples:
    sandbox.py -- ls -la
    sandbox.py -w /tmp/output -- python script.py
    sandbox.py --safe -w ~/.config/myapp -- myapp
"""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path


def check_macos() -> None:
    """Ensure we're running on macOS."""
    if platform.system() != "Darwin":
        print("sandbox: This script only works on macOS", file=sys.stderr)
        sys.exit(1)


def check_sandbox_exec() -> None:
    """Ensure sandbox-exec is available."""
    result = subprocess.run(
        ["which", "sandbox-exec"],
        capture_output=True,
    )
    if result.returncode != 0:
        print("sandbox: sandbox-exec not found on this macOS", file=sys.stderr)
        sys.exit(127)


def abs_path(p: str) -> Path:
    """
    Expand ~ and return absolute, symlink-resolved path.
    For non-existent files, ensure parent exists and return absolute would-be path.
    """
    # Expand ~ manually (handles quoted tildes)
    if p.startswith("~"):
        p = os.path.expanduser(p)

    path = Path(p)

    if path.exists():
        return path.resolve()
    else:
        # For non-existent paths, resolve parent and append basename
        parent = path.parent
        if not parent.exists():
            print(
                f"sandbox: parent directory does not exist: {parent}", file=sys.stderr
            )
            sys.exit(2)
        return parent.resolve() / path.name


def policy_quote(s: str) -> str:
    """Escape a path for Seatbelt policy quoting: escape \\ and \"."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def generate_seatbelt_policy(
    pwd: Path,
    write_paths: list[Path],
    ro_paths: list[Path],
    deny_paths: list[Path],
    safe_mode: bool,
    allow_keychain: bool,
) -> str:
    """Generate a Seatbelt policy string."""
    home = Path.home()
    lines: list[str] = []

    # Version declaration
    lines.append("(version 1)")
    lines.append("(allow default)")

    # Deny ALL file writes first
    lines.append("(deny file-write*)")

    # Optional safe mode: deny reads under $HOME by default
    if safe_mode:
        lines.append(f'(deny file-read* (subpath "{policy_quote(str(home))}"))')

    # Allow current working directory
    lines.append(f'(allow file-write* (subpath "{policy_quote(str(pwd))}"))')
    if safe_mode:
        lines.append(f'(allow file-read* (subpath "{policy_quote(str(pwd))}"))')

    # Allow additional write paths
    for p in write_paths:
        p_str = policy_quote(str(p))
        if p.is_dir():
            lines.append(f'(allow file-write* (subpath "{p_str}"))')
            if safe_mode:
                lines.append(f'(allow file-read* (subpath "{p_str}"))')
        else:
            lines.append(f'(allow file-write* (literal "{p_str}"))')
            if safe_mode:
                lines.append(f'(allow file-read* (literal "{p_str}"))')

    # Allow read-only paths (reads allowed, writes still denied)
    for p in ro_paths:
        p_str = policy_quote(str(p))
        if p.is_dir():
            lines.append(f'(allow file-read* (subpath "{p_str}"))')
        else:
            lines.append(f'(allow file-read* (literal "{p_str}"))')

    # Deny specific paths explicitly
    for p in deny_paths:
        p_str = policy_quote(str(p))
        if p.is_dir():
            lines.append(f'(deny file-read* (subpath "{p_str}"))')
            lines.append(f'(deny file-write* (subpath "{p_str}"))')
        else:
            lines.append(f'(deny file-read* (literal "{p_str}"))')
            lines.append(f'(deny file-write* (literal "{p_str}"))')

    # Temp directories (needed for various operations)
    lines.append('(allow file-write* (subpath "/tmp"))')
    lines.append('(allow file-write* (subpath "/var/tmp"))')
    lines.append('(allow file-write* (subpath "/var/folders"))')
    lines.append('(allow file-write* (subpath "/private/var/folders"))')
    lines.append('(allow file-write* (subpath "/private/tmp"))')

    # Common device files and pipes
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

    # User's Library folders that apps commonly need
    home_str = policy_quote(str(home))
    lines.append(f'(allow file-write* (subpath "{home_str}/Library/Caches"))')
    lines.append(f'(allow file-write* (subpath "{home_str}/Library/Logs"))')
    lines.append(
        f'(allow file-write* (subpath "{home_str}/Library/Application Support"))'
    )

    # Keychain access (only if explicitly allowed)
    if allow_keychain:
        lines.append(f'(allow file-read* (subpath "{home_str}/Library/Keychains"))')
        lines.append('(allow file-read* (subpath "/Library/Keychains"))')
        lines.append(f'(allow file-write* (subpath "{home_str}/Library/Keychains"))')
        # Security framework and keychain services
        lines.append("(allow system-mac-syscall (syscall-number 73))")
        lines.append('(allow mach-lookup (global-name "com.apple.securityd"))')
        lines.append(
            '(allow mach-lookup (global-name "com.apple.security.othersigning"))'
        )
        lines.append(
            '(allow mach-lookup (global-name "com.apple.security.credentialstore"))'
        )

    return "\n".join(lines)


def ensure_paths_exist(paths: list[Path]) -> None:
    """Ensure files exist so Seatbelt can reference them."""
    for p in paths:
        if not p.is_dir() and not p.exists():
            p.touch()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Isolate a process using macOS sandbox-exec (Seatbelt)",
        usage="%(prog)s [OPTIONS] -- <command> [args...]",
    )
    parser.add_argument(
        "-w",
        "--write",
        action="append",
        default=[],
        metavar="PATH",
        help="Allow read-write access to PATH (repeatable)",
    )
    parser.add_argument(
        "--read-only",
        action="append",
        default=[],
        metavar="PATH",
        help="Allow read-only access to PATH (repeatable)",
    )
    parser.add_argument(
        "--deny",
        action="append",
        default=[],
        metavar="PATH",
        help="Deny all access to PATH (repeatable)",
    )
    parser.add_argument(
        "--safe",
        action="store_true",
        help="Hide home directory by default",
    )
    parser.add_argument(
        "--allow-keychain",
        action="store_true",
        help="Allow macOS Keychain access (DANGEROUS)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print the generated policy and keep the policy file",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command to run (after --)",
    )

    args = parser.parse_args()

    # Handle the -- separator
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]

    if not args.command:
        parser.print_help()
        sys.exit(1)

    return args


def main() -> int:
    """Main entry point."""
    check_macos()
    check_sandbox_exec()

    args = parse_args()

    # Resolve all paths
    pwd = Path.cwd().resolve()
    write_paths = [abs_path(p) for p in args.write]
    ro_paths = [abs_path(p) for p in args.read_only]
    deny_paths = [abs_path(p) for p in args.deny]

    # Ensure files exist for Seatbelt
    ensure_paths_exist(write_paths)
    ensure_paths_exist(ro_paths)
    ensure_paths_exist(deny_paths)

    # Generate policy
    policy = generate_seatbelt_policy(
        pwd=pwd,
        write_paths=write_paths,
        ro_paths=ro_paths,
        deny_paths=deny_paths,
        safe_mode=args.safe,
        allow_keychain=args.allow_keychain,
    )

    if args.debug:
        print("DEBUG: Generated Seatbelt policy:", file=sys.stderr)
        print(policy, file=sys.stderr)
        print("---", file=sys.stderr)

    # Write policy to temp file
    with tempfile.NamedTemporaryFile(
        mode="w",
        prefix="sandbox.seatbelt.",
        suffix=".sb",
        delete=not args.debug,
    ) as f:
        f.write(policy)
        f.flush()

        if args.debug:
            print(f"DEBUG: Policy file: {f.name}", file=sys.stderr)

        # Run command in sandbox
        result = subprocess.run(
            ["sandbox-exec", "-f", f.name] + args.command,
        )

        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
