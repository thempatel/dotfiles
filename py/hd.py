#!/usr/bin/env -S uv run --no-config --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""hd - switch to the herdr workspace for a directory, or create one.

A new workspace is labelled with the directory's basename and gets three tabs:
agent (runs sbox-agent), term (a shell) and nvim. An open workspace is found by
the path hash hd tags it with, or by label for an untagged workspace (which
then gets tagged).
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


def find_workspace(path: str, label: str) -> str | None:
    workspaces = herdr("workspace", "list")["result"]["workspaces"]
    want = path_hash(path)
    for ws in workspaces:
        if (ws.get("tokens") or {}).get(TAG_NAME) == want:
            return ws["workspace_id"]
    # A workspace tagged with another path is a different directory with the same
    # basename, so the label fallback only considers untagged workspaces.
    for ws in workspaces:
        if ws["label"] == label and TAG_NAME not in (ws.get("tokens") or {}):
            return ws["workspace_id"]
    return None


def create_workspace(path: str, label: str) -> str:
    result = herdr("workspace", "create", "--cwd", path, "--label", label, "--focus")[
        "result"
    ]
    ws_id = result["workspace"]["workspace_id"]
    agent_tab = result["tab"]["tab_id"]

    herdr("tab", "rename", agent_tab, "agent")
    herdr("pane", "run", result["root_pane"]["pane_id"], "clear && sbox-agent")

    herdr(
        "tab",
        "create",
        "--workspace",
        ws_id,
        "--cwd",
        path,
        "--label",
        "term",
        "--no-focus",
    )

    nvim = herdr(
        "tab",
        "create",
        "--workspace",
        ws_id,
        "--cwd",
        path,
        "--label",
        "nvim",
        "--no-focus",
    )
    herdr("pane", "run", nvim["result"]["root_pane"]["pane_id"], "nvim")

    herdr("tab", "focus", agent_tab)
    return ws_id


@app.command(help=__doc__)
def main(
    dir: Annotated[str, typer.Argument(help="Directory to open.")] = ".",
) -> None:
    if not os.path.isdir(dir):
        sys.exit(f"Error: {dir} is not a directory")
    path = os.path.abspath(dir)
    label = os.path.basename(path)

    ensure_herdr_server()

    ws_id = find_workspace(path, label)
    if ws_id:
        herdr("workspace", "focus", ws_id)
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
