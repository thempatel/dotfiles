#!/usr/bin/env -S uv run --no-config --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0", "prompt-toolkit>=3.0"]
# ///
"""wk - pick a project, write a prompt, and start an agent in a fresh worktree.

The worktree is checked out detached at the latest default branch. Worktrees live
in $CODE_ROOT/worktrees/<repo>-wk-N. A worktree is reused when it is free:
registered to the repo, no herdr workspace open on it, and no modified tracked
files. The worktree is opened with `hd`, whose agent tab gets the prompt as its
first message. In the prompt box, enter sends and shift+enter (or ctrl+j) adds a
new line. An empty prompt starts the agent with no message; Esc cancels.
"""

import json
import os
import re
import string
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from prompt_toolkit import prompt
from prompt_toolkit.input.ansi_escape_sequences import ANSI_SEQUENCES
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

app = typer.Typer(
    add_completion=False,
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)

CODE_ROOT = Path(os.environ.get("CODE_ROOT", Path.home() / "src"))
WORKTREE_ROOT = CODE_ROOT / "worktrees"


class Cancelled(Exception):
    """The user backed out of a picker or the prompt box."""


def git(repo: Path | str, *args: str) -> str:
    """Run git in repo and return stdout. Git's stderr passes through; failures raise."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, text=True
    ).stdout.strip()


def git_ok(repo: Path | str, *args: str) -> bool:
    """Run git quietly and report whether it succeeded."""
    return (
        subprocess.run(
            ["git", "-C", str(repo), *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def git_run(repo: Path | str, *args: str) -> None:
    """Run git with its output going to the terminal; failures raise."""
    subprocess.run(["git", "-C", str(repo), *args], check=True)


def has_remote_branch(repo: Path, ref: str) -> bool:
    return git_ok(repo, "show-ref", "--verify", "--quiet", f"refs/remotes/{ref}")


def resolve_root_repo(path: Path | str) -> Path:
    """Resolve any path inside a repo (including a worktree) to its root repo."""
    first = git(path, "worktree", "list", "--porcelain").splitlines()[0]
    return Path(first.removeprefix("worktree "))


def pick_project() -> Path:
    names = sorted(n for n in os.listdir(CODE_ROOT) if not n.startswith("."))
    selected = fzf(names, "--prompt=project> ", "--height=40%", "--reverse")
    if not selected:
        raise Cancelled
    return CODE_ROOT / selected


def fzf(lines: list[str], *args: str) -> str:
    """Run fzf over lines and return its stdout. Raises Cancelled on esc/ctrl-c."""
    proc = subprocess.run(
        ["fzf", *args], input="\n".join(lines) + "\n", stdout=subprocess.PIPE, text=True
    )
    if proc.returncode not in (0, 1):
        raise Cancelled
    return proc.stdout.rstrip("\n")


def default_branch(repo: Path) -> str:
    try:
        ref = subprocess.run(
            ["git", "-C", str(repo), "symbolic-ref", "refs/remotes/origin/HEAD"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ).stdout.strip()
        return ref.removeprefix("refs/remotes/origin/")
    except subprocess.CalledProcessError:
        return git(repo, "rev-parse", "--abbrev-ref", "HEAD")


def default_start_point(repo: Path) -> str:
    """The best start point for a new branch: origin's default branch if it exists."""
    default = default_branch(repo)
    return (
        f"origin/{default}" if has_remote_branch(repo, f"origin/{default}") else default
    )


def refresh_default_branch(repo: Path) -> None:
    """Fetch the default branch so new branches start from the latest commit."""
    default = default_branch(repo)
    if has_remote_branch(repo, f"origin/{default}"):
        git_run(repo, "fetch", "origin", default)


def open_workspace_paths(repo: Path) -> set[str]:
    """Worktree paths of repo that have a herdr workspace open on them.

    Empty when the herdr server is not running, since then no workspace can be open.
    """
    proc = subprocess.run(
        ["herdr", "worktree", "list", "--cwd", str(repo)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        worktrees = json.loads(proc.stdout)["result"]["worktrees"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return set()
    return {wt["path"] for wt in worktrees if wt.get("open_workspace_id")}


def is_worktree_free(wt_dir: Path, repo: Path, open_paths: set[str]) -> bool:
    # A directory matching the -wk-N name is not necessarily a worktree of this repo:
    # git status in a plain directory prints nothing, which would read as free.
    try:
        wt_common = git(
            wt_dir, "rev-parse", "--path-format=absolute", "--git-common-dir"
        )
    except subprocess.CalledProcessError:
        return False
    if wt_common != git(
        repo, "rev-parse", "--path-format=absolute", "--git-common-dir"
    ):
        return False

    if str(wt_dir) in open_paths:
        return False

    status = subprocess.run(
        ["git", "-C", str(wt_dir), "status", "--porcelain", "-uno"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout
    return not status.strip()


def find_worktree_dir(repo: Path) -> tuple[Path, bool]:
    """A free worktree to reuse, or the next unused wk-N path.

    Returns (path, reusable).
    """
    prefix = f"{repo.name}-wk-"
    slots = []
    if WORKTREE_ROOT.is_dir():
        for d in WORKTREE_ROOT.glob(f"{prefix}*"):
            n = d.name.removeprefix(prefix)
            if d.is_dir() and re.fullmatch(r"\d+", n):
                slots.append((int(n), d))
    slots.sort()

    if slots:
        open_paths = open_workspace_paths(repo)
        for _, d in slots:
            if is_worktree_free(d, repo, open_paths):
                return d, True

    next_n = slots[-1][0] + 1 if slots else 1
    return WORKTREE_ROOT / f"{prefix}{next_n}", False


# A terminal sends shift+enter as a bare CR, the same as enter, unless the app
# turns on the kitty keyboard protocol's "disambiguate" flag. That flag also
# changes how Esc and ctrl+letter keys are sent, and prompt_toolkit doesn't know
# those sequences, so they are mapped back to the keys they stand for.
KITTY_ON = "\x1b[>1u"
KITTY_OFF = "\x1b[<u"
KITTY_SEQUENCES = {
    "\x1b[13;2u": Keys.ControlJ,  # shift+enter
    "\x1b[27u": Keys.Escape,
    **{f"\x1b[{ord(c)};5u": Keys(f"c-{c}") for c in string.ascii_lowercase},
}


def ask_prompt() -> str:
    """Read the agent's first message from a text box. Raises Cancelled on esc/ctrl-c."""
    ANSI_SEQUENCES.update(KITTY_SEQUENCES)
    bindings = KeyBindings()

    @bindings.add("enter")
    def send(event):
        event.app.exit(result=event.app.current_buffer.text)

    @bindings.add("c-j")
    def newline(event):
        event.current_buffer.newline(copy_margin=False)

    # eager: fire on Esc alone instead of waiting to see if it starts an
    # alt+key sequence.
    @bindings.add("escape", eager=True)
    def cancel(event):
        event.app.exit(exception=Cancelled())

    print("Prompt for the agent. enter: send, shift+enter: new line, esc: cancel.")
    print("An empty prompt starts the agent with no message.\n")
    sys.stdout.write(KITTY_ON)
    sys.stdout.flush()
    try:
        text = prompt(
            "> ",
            multiline=True,
            prompt_continuation="  ",
            key_bindings=bindings,
        )
    except KeyboardInterrupt:
        raise Cancelled
    finally:
        sys.stdout.write(KITTY_OFF)
        sys.stdout.flush()
    return text.strip()


def ensure_detached_worktree(repo: Path) -> Path:
    """A worktree with a detached checkout of the latest default branch."""
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
    refresh_default_branch(repo)
    base = default_start_point(repo)

    wt_dir, reusable = find_worktree_dir(repo)
    if reusable:
        git_run(wt_dir, "switch", "--detach", base)
    else:
        git_run(repo, "worktree", "add", "--detach", str(wt_dir), base)
    return wt_dir


@app.command(help=__doc__)
def main(
    repo_path: Annotated[
        str | None, typer.Argument(help="Repo to use; skips the project picker.")
    ] = None,
    free: Annotated[
        bool,
        typer.Option(
            "--free", help="Print the worktree wk would reuse, or None (exit 1)."
        ),
    ] = False,
) -> None:
    if free and not repo_path:
        sys.exit("Error: --free requires <repo-path>")

    try:
        repo_arg = repo_path or str(pick_project())
    except Cancelled:
        return

    if not git_ok(repo_arg, "rev-parse", "--git-dir"):
        sys.exit(f"Error: {repo_arg} is not a git repository")
    repo = resolve_root_repo(repo_arg)

    # --free is a query: no prune, no fetch, no worktree created.
    if free:
        wt_dir, reusable = find_worktree_dir(repo)
        print(wt_dir if reusable else "None")
        raise typer.Exit(0 if reusable else 1)

    try:
        prompt = ask_prompt()
    except Cancelled:
        return

    git_run(repo, "worktree", "prune")
    wt_dir = ensure_detached_worktree(repo)

    envrc = wt_dir / ".envrc"
    if envrc.is_file():
        subprocess.run(["direnv", "allow", str(envrc)], check=True)

    hd_args = ["hd", str(wt_dir)]
    if prompt:
        hd_args += ["--prompt", prompt]
    os.execvp("hd", hd_args)


if __name__ == "__main__":
    try:
        app()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode or 1)
