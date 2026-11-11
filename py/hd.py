#!/usr/bin/env -S uv run --no-config --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""hd - switch to the herdr workspace for a directory, or create one.

A new workspace is labelled with the directory's basename and gets three tabs:
agent (runs sbox-agent), term (a shell) and nvim. An open workspace is found by
the path hash hd tags it with, or by label for an untagged workspace (which
then gets tagged, its first tab renamed to agent, and the tabs it lacks added).
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from typing import Annotated

import typer

app = typer.Typer(
    add_completion=False,
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)

TAG_SOURCE = "hd"
TAG_NAME = "path_sha1"


def herdr(*args: str) -> dict:
    out = subprocess.run(
        ["herdr", *args], check=True, stdout=subprocess.PIPE, text=True
    ).stdout
    return json.loads(out) if out.strip() else {}


def server_running() -> bool:
    try:
        return bool(herdr("status", "server", "--json").get("running"))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return False


def ensure_herdr_server() -> None:
    if server_running():
        return
    subprocess.Popen(
        ["herdr", "server"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    for _ in range(50):
        if server_running():
            return
        time.sleep(0.1)
    sys.exit("Error: herdr server did not start")


# herdr cuts metadata token values at 80 characters, so tag with a fixed-length
# hash of the path rather than the path itself.
def path_hash(path: str) -> str:
    return hashlib.sha1(path.encode()).hexdigest()


def tag_path(ws_id: str, path: str) -> None:
    herdr(
        "workspace",
        "report-metadata",
        ws_id,
        "--source",
        TAG_SOURCE,
        "--token",
        f"{TAG_NAME}={path_hash(path)}",
    )


# (label, command run in the tab's pane, or None for a plain shell)
TABS = [("agent", "clear && sbox-agent"), ("term", None), ("nvim", "nvim")]


def find_workspace(path: str, label: str) -> tuple[str, bool] | None:
    """Return (workspace_id, tagged), or None if no workspace matches."""
    workspaces = herdr("workspace", "list")["result"]["workspaces"]
    want = path_hash(path)
    for ws in workspaces:
        if (ws.get("tokens") or {}).get(TAG_NAME) == want:
            return ws["workspace_id"], True
    # A workspace tagged with another path is a different directory with the same
    # basename, so the label fallback only considers untagged workspaces.
    for ws in workspaces:
        if ws["label"] == label and TAG_NAME not in (ws.get("tokens") or {}):
            return ws["workspace_id"], False
    return None


def add_tab(ws_id: str, path: str, label: str, cmd: str | None) -> str:
    result = herdr(
        "tab",
        "create",
        "--workspace",
        ws_id,
        "--cwd",
        path,
        "--label",
        label,
        "--no-focus",
    )["result"]
    if cmd:
        herdr("pane", "run", result["root_pane"]["pane_id"], cmd)
    return result["tab"]["tab_id"]


def create_workspace(path: str, label: str) -> str:
    result = herdr("workspace", "create", "--cwd", path, "--label", label, "--focus")[
        "result"
    ]
    ws_id = result["workspace"]["workspace_id"]
    agent_tab = result["tab"]["tab_id"]

    (agent_label, agent_cmd), *rest = TABS
    herdr("tab", "rename", agent_tab, agent_label)
    herdr("pane", "run", result["root_pane"]["pane_id"], agent_cmd)
    for tab_label, cmd in rest:
        add_tab(ws_id, path, tab_label, cmd)

    herdr("tab", "focus", agent_tab)
    return ws_id


def shell_is_idle(pane_id: str) -> bool:
    info = herdr("pane", "process-info", "--pane", pane_id)["result"]["process_info"]
    return info["foreground_process_group_id"] == info["shell_pid"]


# An untagged workspace wasn't made by hd (e.g. the one herdr creates when its
# server starts). Its first tab that isn't one of hd's becomes the agent tab, and
# the other hd tabs it lacks are added.
def add_missing_tabs(ws_id: str, path: str) -> None:
    tabs = herdr("tab", "list", "--workspace", ws_id)["result"]["tabs"]
    by_label = {t["label"]: t["tab_id"] for t in tabs}
    (agent_label, agent_cmd), *rest = TABS

    if agent_label not in by_label:
        hd_labels = {tab_label for tab_label, _ in TABS}
        other = next((t for t in tabs if t["label"] not in hd_labels), None)
        if other:
            herdr("tab", "rename", other["tab_id"], agent_label)
            by_label[agent_label] = other["tab_id"]
            panes = herdr("pane", "list", "--workspace", ws_id)["result"]["panes"]
            pane = max(
                (p for p in panes if p["tab_id"] == other["tab_id"]),
                key=lambda p: p["focused"],
            )
            # The tab may already be running an agent or editor; typing the
            # command into it would feed it keystrokes.
            if shell_is_idle(pane["pane_id"]):
                herdr("pane", "run", pane["pane_id"], agent_cmd)
        else:
            by_label[agent_label] = add_tab(ws_id, path, agent_label, agent_cmd)

    for tab_label, cmd in rest:
        if tab_label not in by_label:
            add_tab(ws_id, path, tab_label, cmd)
    herdr("tab", "focus", by_label[agent_label])


@app.command(help=__doc__)
def main(
    dir: Annotated[str, typer.Argument(help="Directory to open.")] = ".",
) -> None:
    if not os.path.isdir(dir):
        sys.exit(f"Error: {dir} is not a directory")
    path = os.path.abspath(dir)
    label = os.path.basename(path)

    ensure_herdr_server()

    found = find_workspace(path, label)
    if found:
        ws_id, tagged = found
        herdr("workspace", "focus", ws_id)
        if not tagged:
            add_missing_tabs(ws_id, path)
    else:
        ws_id = create_workspace(path, label)
    tag_path(ws_id, path)

    # Outside herdr, the workspace exists but nothing shows it: attach this terminal.
    if os.environ.get("HERDR_ENV") != "1":
        os.execvp("herdr", ["herdr"])


if __name__ == "__main__":
    try:
        app()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode or 1)
