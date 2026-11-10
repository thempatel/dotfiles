#!/usr/bin/env -S uv run --no-config --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""wk - pick a project and branch, check it out in a reusable worktree, open it in herdr.

Worktrees live in $CODE_ROOT/worktrees/<repo>-wk-N. A worktree is reused when it
is free: registered to the repo, no herdr workspace open on it, and no modified
tracked files. The chosen worktree is opened with `hd`.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    add_completion=False,
    rich_markup_mode=None,
    context_settings={"help_option_names": ["-h", "--help"]},
)

CODE_ROOT = Path(os.environ.get("CODE_ROOT", Path.home() / "src"))
WORKTREE_ROOT = CODE_ROOT / "worktrees"


class Cancelled(Exception):
    """The user backed out of an fzf picker."""


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


def has_local_branch(repo: Path, branch: str) -> bool:
    return git_ok(repo, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")


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


def list_branch_candidates(repo: Path) -> list[tuple[str, str]]:
    """(branch name, source ref) pairs for the picker.

    Local branches come first. A remote branch is listed only when no local branch
    has the same short name.
    """
    local = git(
        repo,
        "branch",
        "--sort=-committerdate",
        "--sort=-HEAD",
        "--format=%(refname:short)",
    ).splitlines()
    remote_refs = [
        ref
        for ref in git(
            repo, "branch", "-r", "--sort=-committerdate", "--format=%(refname:short)"
        ).splitlines()
        if "/" in ref and not ref.endswith("/HEAD")
    ][:100]

    local_set = set(local)
    candidates = [(b, b) for b in local if b]
    candidates += [
        (ref.split("/", 1)[1], ref)
        for ref in remote_refs
        if ref.split("/", 1)[1] not in local_set
    ]
    return candidates


def resolve_remote_branch_ref(repo: Path, branch: str) -> str:
    """The remote ref to track for a new local branch, or "" if none or ambiguous."""
    if has_remote_branch(repo, f"origin/{branch}"):
        return f"origin/{branch}"
    matches = [
        ref
        for ref in git(
            repo, "for-each-ref", "refs/remotes", "--format=%(refname:short)"
        ).splitlines()
        if not ref.endswith("/HEAD") and "/" in ref and ref.split("/", 1)[1] == branch
    ]
    return matches[0] if len(matches) == 1 else ""


def find_worktree_for_branch(repo: Path, branch: str) -> Path | None:
    """The worktree that already has branch checked out, if any."""
    wt = None
    for line in git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            wt = line.removeprefix("worktree ")
        elif line == f"branch refs/heads/{branch}":
            return Path(wt)
    return None


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


def reuse_worktree(wt_dir: Path, repo: Path, branch: str, source: str) -> None:
    if has_local_branch(repo, branch):
        git_run(wt_dir, "switch", branch)
    elif source:
        git_run(wt_dir, "switch", "-c", branch, source)
        git_run(wt_dir, "branch", "--set-upstream-to", source, branch)
    else:
        refresh_default_branch(repo)
        git_run(wt_dir, "switch", "--detach", default_start_point(repo))
        git_run(wt_dir, "switch", "-c", branch)


def pick_branch(repo: Path) -> tuple[str, str]:
    """Interactive branch picker. Returns (branch, source ref); branch "" means detached."""
    candidates = list_branch_candidates(repo)
    out = fzf(
        [f"{name}\t{source}" for name, source in candidates],
        "--prompt=branch> ",
        "--height=40%",
        "--reverse",
        "--border-label= Branches ",
        "--header=Enter: use input (blank = detached off main)  Tab: copy highlighted branch\n"
        "Type to filter existing branches or enter a new branch name",
        "--delimiter=\t",
        "--with-nth=1",
        '--bind=tab:transform-query:[[ -n {} ]] && printf %s {1} || printf %s "$FZF_QUERY"',
        "--expect=enter",
        "--print-query",
    )
    lines = out.split("\n")
    query, key, selection = (lines + ["", "", ""])[:3]
    if key != "enter" and not selection:
        selection = key

    source = ""
    if key == "enter":
        branch = query
    elif selection:
        branch, _, source = selection.partition("\t")
    else:
        branch = query

    if not branch:
        return "", ""

    if not source and not has_local_branch(repo, branch):
        source = resolve_remote_branch_ref(repo, branch)
    return branch, source


def ensure_worktree(repo: Path, branch: str, source: str) -> Path:
    """A worktree with branch checked out, reusing or creating one as needed."""
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
    wt_dir = find_worktree_for_branch(repo, branch)
    if wt_dir:
        return wt_dir

    wt_dir, reusable = find_worktree_dir(repo)
    if reusable:
        reuse_worktree(wt_dir, repo, branch, source)
    elif has_local_branch(repo, branch):
        git_run(repo, "worktree", "add", str(wt_dir), branch)
    elif source:
        git_run(repo, "worktree", "add", "-b", branch, str(wt_dir), source)
        git_run(wt_dir, "branch", "--set-upstream-to", source, branch)
    else:
        refresh_default_branch(repo)
        git_run(
            repo,
            "worktree",
            "add",
            "-b",
            branch,
            str(wt_dir),
            default_start_point(repo),
        )
    return wt_dir


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

    git_run(repo, "worktree", "prune")

    try:
        branch, source = pick_branch(repo)
    except Cancelled:
        return

    wt_dir = (
        ensure_worktree(repo, branch, source)
        if branch
        else ensure_detached_worktree(repo)
    )

    envrc = wt_dir / ".envrc"
    if envrc.is_file():
        subprocess.run(["direnv", "allow", str(envrc)], check=True)

    os.execvp("hd", ["hd", str(wt_dir)])


if __name__ == "__main__":
    try:
        app()
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode or 1)
