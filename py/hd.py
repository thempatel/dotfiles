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

The root of a git checkout (the main one or a linked worktree) is opened through
herdr's worktree support instead, so herdr groups the worktrees of a repo under
the main checkout's workspace.

With --prompt, a new workspace's agent starts with that text as its first
message. In a workspace that is already open, the text is sent to the agent in
its agent tab, whatever that agent is doing.

With --app, hd drives the Herdr desktop app (herdr-app and hc) instead of the
herdr TUI, and opens the same three tabs in a space. Its spaces are left
unnamed, so the app names them after their folder and nests a git worktree's
space under its repo. An open space is found by the path hash hd puts on its
terminals as an hc label, or by its folder for an untagged space.
"""

import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
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


def herdr(*args: str, quiet: bool = False) -> dict:
    return run_json("herdr", *args, quiet=quiet)


def run_json(*cmd: str, quiet: bool = False) -> dict:
    out = subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if quiet else None,
        text=True,
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


# (label, program run in the tab, or None for a plain shell)
TABS = [("agent", ["sbox-agent"]), ("term", None), ("nvim", ["nvim"])]
# The agent tab's program when it starts with a prompt, which goes after it.
AGENT_PROMPT_ARGV = ["sbox-agent", "claude", "--"]


def shell_command(argv: list[str] | None) -> str | None:
    return shlex.join(argv) if argv else None


# The prompt goes through a file because `herdr pane run` rejects a command line
# longer than the terminal's input limit (about 1 KB on macOS), which a typed-in
# prompt can easily exceed.
def agent_command(prompt: str | None) -> str:
    """The agent tab's command, starting the agent with prompt as its first message."""
    if not prompt:
        return f"clear && {shell_command(TABS[0][1])}"
    fd, prompt_file = tempfile.mkstemp(prefix="hd-prompt-", suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write(prompt)
    quoted = shlex.quote(prompt_file)
    return (
        f'clear && {shell_command(AGENT_PROMPT_ARGV)} "$(cat {quoted} && rm {quoted})"'
    )


def prompt_agent(ws_id: str, prompt: str | None) -> None:
    """Send prompt to the agent in an open workspace and focus its tab."""
    if not prompt:
        return
    agents = [
        a
        for a in herdr("agent", "list")["result"]["agents"]
        if a["workspace_id"] == ws_id
    ]
    tabs = herdr("tab", "list", "--workspace", ws_id)["result"]["tabs"]
    agent_tabs = {t["tab_id"] for t in tabs if t["label"] == TABS[0][0]}
    agents.sort(key=lambda a: a["tab_id"] not in agent_tabs)
    if not agents:
        print("hd: no agent in the open workspace; prompt not sent", file=sys.stderr)
        return
    try:
        herdr("agent", "prompt", agents[0]["pane_id"], prompt, quiet=True)
    except subprocess.CalledProcessError:
        # herdr refuses when the agent is waiting on an approval dialog.
        print("hd: the agent did not accept the prompt; not sent", file=sys.stderr)
        return
    herdr("tab", "focus", agents[0]["tab_id"])


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


def main_checkout(path: str) -> str | None:
    """Return the repo's main checkout if path is the root of a git checkout."""
    try:
        result = herdr("worktree", "list", "--cwd", path, quiet=True)["result"]
    except subprocess.CalledProcessError:
        return None
    real = os.path.realpath(path)
    if all(os.path.realpath(w["path"]) != real for w in result["worktrees"]):
        return None
    return result["source"]["source_checkout_path"]


def create_workspace(path: str, label: str, prompt: str | None) -> str:
    result = herdr("workspace", "create", "--cwd", path, "--label", label, "--focus")[
        "result"
    ]
    return setup_tabs(result, path, prompt)


# herdr only groups a worktree under its repo's workspace when it is opened
# through `worktree open`. If the repo has no workspace yet, herdr creates one.
def open_checkout(path: str, main: str, prompt: str | None) -> str:
    result = herdr("worktree", "open", "--cwd", main, "--path", path, "--focus")[
        "result"
    ]
    ws = result["workspace"]
    if not result["already_open"]:
        return setup_tabs(result, path, prompt)
    if TAG_NAME not in (ws.get("tokens") or {}):
        add_missing_tabs(ws["workspace_id"], path)
    prompt_agent(ws["workspace_id"], prompt)
    return ws["workspace_id"]


def setup_tabs(result: dict, path: str, prompt: str | None) -> str:
    """Make a new workspace's first tab the agent tab and add the other tabs."""
    ws_id = result["workspace"]["workspace_id"]
    agent_tab = result["tab"]["tab_id"]

    (agent_label, _), *rest = TABS
    herdr("tab", "rename", agent_tab, agent_label)
    herdr("pane", "run", result["root_pane"]["pane_id"], agent_command(prompt))
    for tab_label, argv in rest:
        add_tab(ws_id, path, tab_label, shell_command(argv))

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
    (agent_label, _), *rest = TABS
    agent_cmd = agent_command(None)

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

    for tab_label, argv in rest:
        if tab_label not in by_label:
            add_tab(ws_id, path, tab_label, shell_command(argv))
    herdr("tab", "focus", by_label[agent_label])


APP_BUNDLE = "dev.herdr.app"
APP_TAG = f"{TAG_SOURCE}.{TAG_NAME}"


def app_do(command: str, **args) -> dict:
    """Run a Herdr app command; args are passed as one JSON object."""
    proc = subprocess.run(
        ["herdr-app", "do", command, json.dumps(args)],
        check=False,
        stdout=subprocess.PIPE,
        text=True,
    )
    out = json.loads(proc.stdout) if proc.stdout.strip() else {}
    if proc.returncode != 0:
        sys.exit(f"hd: herdr-app {command}: {out.get('error', 'failed')}")
    return out


def app_running() -> bool:
    return (
        subprocess.run(
            ["herdr-app", "status"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def ensure_app() -> None:
    if app_running():
        return
    subprocess.run(["open", "-b", APP_BUNDLE], check=True)
    for _ in range(100):
        if app_running():
            return
        time.sleep(0.1)
    sys.exit("Error: the Herdr app did not start")


def app_space(space_id: str) -> dict:
    spaces = run_json("herdr-app", "ls")["spaces"]
    return next(s for s in spaces if s["id"] == space_id)


def app_terminals(space: dict) -> list[str]:
    return [t["terminal"] for tab in space["tabs"] for t in tab["terminals"]]


def app_find_space(path: str) -> tuple[dict, bool] | None:
    """Return (space, tagged), or None if no space on this computer matches."""
    spaces = [s for s in run_json("herdr-app", "ls")["spaces"] if s["machine"] is None]
    tagged = {
        t["address"]
        for t in run_json(
            "hc", "ls", "--json", "--label", f"{APP_TAG}={path_hash(path)}"
        )["terminals"]
    }
    for space in spaces:
        if tagged.intersection(app_terminals(space)):
            return space, True
    real = os.path.realpath(path)
    for space in spaces:
        if space["folder"] and os.path.realpath(space["folder"]) == real:
            return space, False
    return None


# hc labels belong to terminals, so every terminal in the space carries the tag:
# the space stays findable while any of them is open.
def app_tag(space_id: str, path: str) -> None:
    for terminal in app_terminals(app_space(space_id)):
        subprocess.run(
            ["hc", "label", terminal, f"{APP_TAG}={path_hash(path)}"],
            check=True,
            stdout=subprocess.DEVNULL,
        )


def app_add_tab(space_id: str, path: str, label: str, argv: list[str] | None) -> str:
    args = {"space": space_id, "name": label, "folder": path, "focus": False}
    if argv:
        args["argv"] = argv
    return app_do("tab.new", **args)["tab"]


def app_create_space(path: str, prompt: str | None) -> str:
    (agent_label, agent_argv), *rest = TABS
    args = {"folder": path, "tab": agent_label, "machine": ""}
    # The app passes the task to the program as its last argument.
    if prompt:
        args |= {"argv": AGENT_PROMPT_ARGV, "task": prompt}
    else:
        args["argv"] = agent_argv
    space_id = app_do("space.new", **args)["space"]
    for tab_label, argv in rest:
        app_add_tab(space_id, path, tab_label, argv)
    return space_id


def app_shell_is_idle(terminal: str) -> bool:
    info = run_json("hc", "get", terminal, "--json")
    return info["foreground"]["pid"] == info["pid"]


# An untagged space wasn't made by hd (e.g. one made in the app). Its first tab
# that isn't one of hd's becomes the agent tab, and the hd tabs it lacks are added.
def app_add_missing_tabs(space: dict, path: str) -> None:
    by_label = {t["name"]: t["id"] for t in space["tabs"]}
    (agent_label, agent_argv), *rest = TABS

    if agent_label not in by_label:
        hd_labels = {tab_label for tab_label, _ in TABS}
        other = next((t for t in space["tabs"] if t["name"] not in hd_labels), None)
        if other:
            app_do("tab.rename", id=other["id"], name=agent_label)
            by_label[agent_label] = other["id"]
            # The tab may already be running an agent or editor; typing the
            # command into it would feed it keystrokes.
            terminal = other["terminals"][0]["terminal"]
            if app_shell_is_idle(terminal):
                subprocess.run(
                    ["hc", "send", terminal, shell_command(agent_argv)],
                    check=True,
                    stdout=subprocess.DEVNULL,
                )
        else:
            by_label[agent_label] = app_add_tab(
                space["id"], path, agent_label, agent_argv
            )

    for tab_label, argv in rest:
        if tab_label not in by_label:
            app_add_tab(space["id"], path, tab_label, argv)
    app_do("tab.select", id=by_label[agent_label])


def app_prompt_agent(space_id: str, prompt: str | None) -> None:
    """Send prompt to the agent in an open space and show it."""
    if not prompt:
        return
    agents = [
        (tab["name"], t["terminal"])
        for tab in app_space(space_id)["tabs"]
        for t in tab["terminals"]
        if t["status"] is not None
    ]
    agents.sort(key=lambda a: a[0] != TABS[0][0])
    if not agents:
        print("hd: no agent in the open space; prompt not sent", file=sys.stderr)
        return
    terminal = agents[0][1]
    # hc refuses when the agent is waiting on an approval dialog.
    sent = subprocess.run(
        ["hc", "send", terminal, prompt],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if sent.returncode != 0:
        print("hd: the agent did not accept the prompt; not sent", file=sys.stderr)
        return
    app_do("agent.focus", terminal=terminal)


def open_in_app(path: str, prompt: str | None) -> None:
    ensure_app()
    if found := app_find_space(path):
        space, tagged = found
        space_id = space["id"]
        app_do("space.select", id=space_id)
        if not tagged:
            app_add_missing_tabs(space, path)
        app_prompt_agent(space_id, prompt)
    else:
        space_id = app_create_space(path, prompt)
    app_tag(space_id, path)

    # From a terminal outside the app, bring the app's window to the front.
    if os.environ.get("__CFBundleIdentifier") != APP_BUNDLE:
        subprocess.run(["open", "-b", APP_BUNDLE], check=True)


@app.command(help=__doc__)
def main(
    dir: Annotated[str, typer.Argument(help="Directory to open.")] = ".",
    prompt: Annotated[
        str | None,
        typer.Option("--prompt", "-p", help="Message for the workspace's agent."),
    ] = None,
    use_app: Annotated[
        bool,
        typer.Option("--app", "-a", help="Drive the Herdr app instead of the TUI."),
    ] = False,
) -> None:
    if not os.path.isdir(dir):
        sys.exit(f"Error: {dir} is not a directory")
    path = os.path.abspath(dir)
    label = os.path.basename(path)

    if use_app:
        open_in_app(path, prompt)
        return

    ensure_herdr_server()

    repo_main = main_checkout(path)
    if repo_main:
        ws_id = open_checkout(path, repo_main, prompt)
    elif found := find_workspace(path, label):
        ws_id, tagged = found
        herdr("workspace", "focus", ws_id)
        if not tagged:
            add_missing_tabs(ws_id, path)
        prompt_agent(ws_id, prompt)
    else:
        ws_id = create_workspace(path, label, prompt)
    tag_path(ws_id, path)

    # Outside herdr, the workspace exists but nothing shows it: attach this terminal.
    # A herdr popup (the wk key binding) is inside herdr but may not set HERDR_ENV;
    # attaching there would nest a second herdr client in the popup.
    if os.environ.get("HERDR_ENV") != "1" and not os.environ.get("HERDR_SOCKET_PATH"):
        os.execvp("herdr", ["herdr"])


if __name__ == "__main__":
    try:
        app()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode or 1)
