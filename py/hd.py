#!/usr/bin/env -S uv run --no-config --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""hd - switch to the Herdr app space for a directory, or create one.

A new space gets three tabs: agent (runs sbox-agent), term (a shell) and nvim.
Spaces are left unnamed, so the app names them after their folder and nests a
git worktree's space under its repo. An open space is found by the path hash hd
puts on its terminals as an hc label, or by its folder for an untagged space
(which then gets tagged, its first tab renamed to agent, and the tabs it lacks
added).

With --prompt, a new space's agent starts with that text as its first message.
In a space that is already open, the text is sent to the agent in its agent
tab, whatever that agent is doing.
"""

import hashlib
import json
import os
import shlex
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


def run_json(*cmd: str) -> dict:
    out = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, text=True).stdout
    return json.loads(out) if out.strip() else {}


def path_hash(path: str) -> str:
    return hashlib.sha1(path.encode()).hexdigest()


# (label, program run in the tab, or None for a plain shell)
TABS = [("agent", ["sbox-agent"]), ("term", None), ("nvim", ["nvim"])]
# The agent tab's program when it starts with a prompt, which goes after it.
AGENT_PROMPT_ARGV = ["sbox-agent", "claude", "--"]


def shell_command(argv: list[str] | None) -> str | None:
    return shlex.join(argv) if argv else None


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
        typer.Option("--prompt", "-p", help="Message for the space's agent."),
    ] = None,
) -> None:
    if not os.path.isdir(dir):
        sys.exit(f"Error: {dir} is not a directory")
    open_in_app(os.path.abspath(dir), prompt)


if __name__ == "__main__":
    try:
        app()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode or 1)
