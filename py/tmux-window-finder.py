#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer"]
# ///
"""
tmux-window-finder - Fuzzy find tmux windows by session + process label.

Subcommands:
  update  — query tmux + ps, resolve labels, write per-window JSON (runs on hooks)
  lookup  — read state dir, output for fzf (runs on prefix+w)
  notify  — set/clear AI notification flag on a window

State lives in ~/.local/state/tmux-window-finder/{session}/{window}.json
Each file: { "label": "...", "notify": false }
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import typer

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

STATE_DIR = Path.home() / ".local" / "state" / "tmux-window-finder"

AI_TOOLS = {"claude", "codex"}
SHELLS = {"zsh", "bash", "fish"}


# -- helpers ------------------------------------------------------------------


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


def find_ai_tool(
    pid: str, children_map: dict[str, list[tuple[str, str]]]
) -> str | None:
    for child_pid, cmd_name in children_map.get(pid, []):
        if cmd_name in AI_TOOLS:
            return cmd_name
        found = find_ai_tool(child_pid, children_map)
        if found:
            return found
    return None


def _extract_claude_topic(pane_title: str) -> str | None:
    if not pane_title:
        return None
    stripped = pane_title.lstrip()
    if stripped:
        first = stripped[0]
        if not first.isascii():
            stripped = stripped[1:].lstrip()
    if not stripped or stripped == "Claude Code" or "." in stripped:
        return None
    return stripped


def _extract_shell_title(pane_title: str) -> str | None:
    if not pane_title:
        return None
    stripped = pane_title.strip()
    if not stripped or "." in stripped:
        return None
    return stripped


def get_process_label(
    cmd: str,
    pane_pid: str,
    pane_title: str,
    children_map: dict[str, list[tuple[str, str]]],
) -> str:
    ai_tool = find_ai_tool(pane_pid, children_map)
    if ai_tool:
        topic = _extract_claude_topic(pane_title)
        if topic:
            return f"{ai_tool}: {topic}"
        return ai_tool
    if cmd in SHELLS:
        title = _extract_shell_title(pane_title)
        if title:
            return title
    return cmd


def _read_window_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data) + "\n")
    tmp.rename(path)


# -- update -------------------------------------------------------------------


@app.command()
def update() -> None:
    """Query tmux + ps, resolve process labels, write per-window state."""
    try:
        _do_update()
    except Exception:
        pass  # hooks must never return non-zero


def _prune_stale_files(live_files: set[Path]) -> None:
    """Remove window files that no longer correspond to live tmux windows."""
    if not STATE_DIR.exists():
        return
    for session_dir in STATE_DIR.iterdir():
        if not session_dir.is_dir():
            continue
        _prune_session_dir(session_dir, live_files)


def _prune_session_dir(session_dir: Path, live_files: set[Path]) -> None:
    """Remove stale window files from a session dir, then remove the dir if empty."""
    for window_file in session_dir.iterdir():
        if window_file.suffix == ".json" and window_file not in live_files:
            window_file.unlink()
    if not any(session_dir.iterdir()):
        session_dir.rmdir()


def _do_update() -> None:
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
    live_files: set[Path] = set()

    for line in raw.splitlines():
        session, idx, cmd, pane_pid, pane_title = line.split("\t", 4)
        label = get_process_label(cmd, pane_pid, pane_title, children_map)

        path = STATE_DIR / session / f"{idx}.json"
        existing = _read_window_json(path)
        existing["label"] = label
        existing.setdefault("notify", False)
        _atomic_write_json(path, existing)
        live_files.add(path)

    _prune_stale_files(live_files)


# -- lookup -------------------------------------------------------------------


def _read_entries() -> list[tuple[str, str, str, bool]]:
    """Read all window entries from the state directory."""
    entries: list[tuple[str, str, str, bool]] = []
    for session_dir in sorted(STATE_DIR.iterdir()):
        if not session_dir.is_dir():
            continue
        session = session_dir.name
        for window_file in sorted(session_dir.iterdir()):
            if window_file.suffix != ".json":
                continue
            data = _read_window_json(window_file)
            entries.append(
                (
                    session,
                    window_file.stem,
                    data.get("label", "?"),
                    data.get("notify", False),
                )
            )
    return entries


def _sort_entries(entries: list[tuple[str, str, str, bool]]) -> None:
    """Sort entries by session, then AI tools first, then label."""
    entries.sort(
        key=lambda e: (
            e[0].lower(),
            0 if any(e[2].startswith(t) for t in AI_TOOLS) else 1,
            e[2].lower(),
        )
    )


def _format_lines(
    entries: list[tuple[str, str, str, bool]],
    active_session: str,
    active_window: str,
) -> tuple[list[str], int]:
    """Build display lines with deduplicated labels. Returns (lines, active_line)."""
    label_counts: dict[tuple[str, str], int] = {}
    for session, _, label, _ in entries:
        key = (session, label)
        label_counts[key] = label_counts.get(key, 0) + 1

    label_counters: dict[tuple[str, str], int] = {}
    lines: list[str] = []
    active_line = 1
    for session, idx, label, notify in entries:
        key = (session, label)
        if label_counts[key] > 1:
            n = label_counters.get(key, 0) + 1
            label_counters[key] = n
            display_label = f"{label}-{n}"
        else:
            display_label = label

        if notify:
            display_label = f"\U0001f514 {display_label}"

        lines.append(f"{session} {display_label}\t{session}:{idx}")
        if session == active_session and idx == active_window:
            active_line = len(lines)

    return lines, active_line


@app.command()
def lookup() -> None:
    """Read state dir, output for fzf."""
    if not STATE_DIR.exists():
        _do_update()

    entries = _read_entries()
    if not entries:
        return

    active_session = tmux("display-message", "-p", "#{session_name}")
    active_window = tmux("display-message", "-p", "#{window_index}")

    _sort_entries(entries)
    lines, active_line = _format_lines(entries, active_session, active_window)

    if not lines:
        return

    print(active_line, file=sys.stderr)
    for line in lines:
        print(line)


# -- notify -------------------------------------------------------------------


@app.command()
def notify(
    on: bool = typer.Option(False, "--on", help="Set notification flag"),
    off: bool = typer.Option(False, "--off", help="Clear notification flag"),
    agent: str | None = typer.Option(
        None, "--agent", "-a", help="Coding agent name (claude, codex)"
    ),
    session: str | None = typer.Option(
        None, "--session", "-s", help="Target session (auto-detected if omitted)"
    ),
    window: str | None = typer.Option(
        None, "--window", "-w", help="Target window index (auto-detected if omitted)"
    ),
) -> None:
    """Set or clear the AI notification flag on a tmux window."""
    try:
        _do_notify(on=on, off=off, agent=agent, session=session, window=window)
    except Exception:
        pass  # hooks must never return non-zero


def _read_stdin_hook_input() -> dict:
    """Read JSON hook input from stdin if available."""
    if sys.stdin.isatty():
        return {}
    try:
        data = sys.stdin.read()
        if data.strip():
            return json.loads(data)
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _do_notify(
    *,
    on: bool,
    off: bool,
    agent: str | None,
    session: str | None,
    window: str | None,
) -> None:
    if not on and not off:
        typer.echo("Specify --on or --off", err=True)
        raise typer.Exit(code=1)

    # Use $TMUX_PANE to resolve the pane where the hook is running,
    # rather than the currently focused window (which may differ).
    pane_target = os.environ.get("TMUX_PANE")
    target_args = ["-t", pane_target] if pane_target else []
    if session is None:
        session = tmux("display-message", *target_args, "-p", "#{session_name}")
    if window is None:
        window = tmux("display-message", *target_args, "-p", "#{window_index}")

    hook_input = _read_stdin_hook_input()

    path = STATE_DIR / session / f"{window}.json"
    existing = _read_window_json(path)
    existing["notify"] = on
    existing.setdefault("label", "?")

    # Store debug metadata from hook invocation
    existing["last_hook"] = {
        "event": hook_input.get("hook_event_name"),
        "action": "on" if on else "off",
        "agent": agent,
        "session_id": hook_input.get("session_id"),
        "cwd": hook_input.get("cwd"),
    }

    _atomic_write_json(path, existing)


# -- main ---------------------------------------------------------------------


if __name__ == "__main__":
    app()
