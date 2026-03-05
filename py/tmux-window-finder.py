#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
tmux-window-finder.py - Fuzzy find tmux windows by session + process label.

Two modes:
  update  — query tmux + ps, resolve labels, write cache (runs on hooks)
  lookup  — read cache, output for fzf (runs on prefix+w)

Each window is displayed as:
  {session_name} {process_label}

Process labels:
  - "claude: {topic}" if a claude descendant is found, using the pane title
    as the topic (e.g. "claude: Frame-Based Bot Detection")
  - "claude" if a claude descendant is found but no meaningful pane title
  - for shells (zsh/bash/fish): the pane title set by precmd (git branch or
    dir name), falling back to the command name
  - the pane_current_command otherwise (e.g. "vim", "python3")

When multiple windows in a session share the same label, they are suffixed:
  claude-1, claude-2, zsh-1, zsh-2, etc.
"""

from __future__ import annotations

import fcntl
import os
import subprocess
import sys

CACHE_PATH = "/tmp/tmux-wf-cache"


def tmux(*args: str) -> str:
    result = subprocess.run(["tmux", *args], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _build_children_map() -> dict[str, list[tuple[str, str]]]:
    result = subprocess.run(
        ["ps", "-e", "-o", "pid=,ppid=,comm="], capture_output=True, text=True
    )
    children: dict[str, list[tuple[str, str]]] = {}
    for line in result.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, ppid, comm = parts
        cmd_name = comm.rsplit("/", 1)[-1]
        children.setdefault(ppid, []).append((pid, cmd_name))
    return children


def has_claude_descendant(
    pid: str, children_map: dict[str, list[tuple[str, str]]]
) -> bool:
    for child_pid, cmd_name in children_map.get(pid, []):
        if cmd_name == "claude":
            return True
        if has_claude_descendant(child_pid, children_map):
            return True
    return False


def _extract_claude_topic(pane_title: str) -> str | None:
    """Extract a meaningful topic from the pane title, or None if generic."""
    if not pane_title:
        return None
    # Claude Code sets pane title to things like "✳ Frame-Based Bot Detection"
    # or "⠐ tmux-window-finder caching" (with spinner chars).
    # Strip leading unicode spinner/status chars and whitespace.
    stripped = pane_title.lstrip()
    if stripped:
        # Remove leading non-ASCII status character if present
        first = stripped[0]
        if not first.isascii():
            stripped = stripped[1:].lstrip()
    # Ignore generic titles like "Claude Code" or hostname-like strings
    if not stripped or stripped == "Claude Code" or "." in stripped:
        return None
    return stripped


SHELLS = {"zsh", "bash", "fish"}


def _extract_shell_title(pane_title: str) -> str | None:
    """Extract a meaningful title set by precmd (branch name or dir name)."""
    if not pane_title:
        return None
    stripped = pane_title.strip()
    # Ignore hostname-like titles (contain dots like "milan-host.local")
    if not stripped or "." in stripped:
        return None
    return stripped


def get_process_label(
    cmd: str,
    pane_pid: str,
    pane_title: str,
    children_map: dict[str, list[tuple[str, str]]],
) -> str:
    if has_claude_descendant(pane_pid, children_map):
        topic = _extract_claude_topic(pane_title)
        if topic:
            return f"claude: {topic}"
        return "claude"
    if cmd in SHELLS:
        title = _extract_shell_title(pane_title)
        if title:
            return title
    return cmd


# -- update mode: resolve labels and write cache ----------------------------


def cmd_update() -> None:
    """Query tmux + ps, resolve process labels, write cache atomically."""
    try:
        raw = tmux(
            "list-windows",
            "-a",
            "-F",
            "#{session_name}\t#{window_index}\t#{pane_current_command}\t#{pane_pid}\t#{pane_title}",
        )
    except subprocess.CalledProcessError:
        return
    if not raw:
        return

    children_map = _build_children_map()

    lines: list[str] = []
    for line in raw.splitlines():
        session, idx, cmd, pane_pid, pane_title = line.split("\t", 4)
        label = get_process_label(cmd, pane_pid, pane_title, children_map)
        lines.append(f"{session}\t{idx}\t{label}")

    tmp_path = CACHE_PATH + ".tmp"
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, "\n".join(lines).encode() + b"\n")
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(tmp_path, CACHE_PATH)


# -- lookup mode: read cache, output for fzf --------------------------------


def _read_cache() -> list[tuple[str, str, str]]:
    """Read cache, return list of (session, window_index, label)."""
    try:
        with open(CACHE_PATH) as f:
            data = f.read()
    except FileNotFoundError:
        cmd_update()
        with open(CACHE_PATH) as f:
            data = f.read()

    rows: list[tuple[str, str, str]] = []
    for line in data.splitlines():
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) == 3:
            rows.append((parts[0], parts[1], parts[2]))
    return rows


def cmd_lookup() -> None:
    """Read cache, output for fzf. Only subprocess call is display-message."""
    entries = _read_cache()
    if not entries:
        return

    active_session = tmux("display-message", "-p", "#{session_name}")
    active_window = tmux("display-message", "-p", "#{window_index}")

    # Sort by session, then claude windows first within each session
    entries.sort(
        key=lambda e: (
            e[0].lower(),
            0 if e[2].startswith("claude") else 1,
            e[2].lower(),
        )
    )

    # Count labels per session to determine if suffixes are needed
    label_counts: dict[tuple[str, str], int] = {}
    for session, _, label in entries:
        key = (session, label)
        label_counts[key] = label_counts.get(key, 0) + 1

    # Assign suffixed labels and track active line
    label_counters: dict[tuple[str, str], int] = {}
    lines: list[str] = []
    active_line = 1
    for session, idx, label in entries:
        key = (session, label)
        if label_counts[key] > 1:
            n = label_counters.get(key, 0) + 1
            label_counters[key] = n
            display_label = f"{label}-{n}"
        else:
            display_label = label

        lines.append(f"{session} {display_label}\t{session}:{idx}")
        if session == active_session and idx == active_window:
            active_line = len(lines)

    if not lines:
        return

    print(active_line, file=sys.stderr)
    for line in lines:
        print(line)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "lookup"
    if cmd == "update":
        try:
            cmd_update()
        except Exception:
            pass  # hooks must never return non-zero
    elif cmd == "lookup":
        cmd_lookup()
    else:
        print(f"usage: tmux-window-finder [update|lookup]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
