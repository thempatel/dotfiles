#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""git order - report whether one commit comes before or after another."""

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime

import typer

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Short sha, strict-ISO author date, subject. Tab-separated so a subject
# containing spaces (or tabs) stays intact.
FORMAT = "%h%x09%aI%x09%s"


def git(*args: str, quiet: bool = False) -> subprocess.CompletedProcess[str]:
    """Run git, capturing stdout. Git's own stderr passes through unless quiet."""
    return subprocess.run(
        ["git", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if quiet else None,
        text=True,
    )


@dataclass(frozen=True)
class Commit:
    ref: str
    sha: str
    short: str
    authored: datetime
    subject: str

    @property
    def date(self) -> str:
        """Author date on the reader's clock, so two of them compare by eye."""
        return self.authored.astimezone().strftime("%Y-%m-%d %H:%M")

    @property
    def ref_is_sha(self) -> bool:
        """A ref that prefixes the sha it resolved to is a sha, not a name."""
        return self.sha.startswith(self.ref.lower())


def resolve(ref: str) -> Commit:
    # Peel to the commit so annotated tags report their commit, not the tag object.
    found = git(
        "rev-parse",
        "--verify",
        "--quiet",
        "--end-of-options",
        f"{ref}^{{commit}}",
        quiet=True,
    )
    if found.returncode != 0:
        print(f"fatal: bad revision '{ref}'", file=sys.stderr)
        raise typer.Exit(1)

    sha = found.stdout.strip()
    shown = git("show", "-s", f"--format={FORMAT}", sha)
    if shown.returncode != 0:
        raise typer.Exit(1)

    short, authored, subject = shown.stdout.rstrip("\n").split("\t", 2)
    return Commit(ref, sha, short, datetime.fromisoformat(authored), subject)


def is_ancestor(a: Commit, b: Commit) -> bool:
    return git("merge-base", "--is-ancestor", a.sha, b.sha, quiet=True).returncode == 0


def relation(a: Commit, b: Commit) -> tuple[str, str]:
    """The operator between the two commits, and a label for the unordered cases."""
    if a.sha == b.sha:
        return "=", "   (same commit)"
    if is_ancestor(a, b):
        return "<", ""
    if is_ancestor(b, a):
        return ">", ""
    return "<>", "   (diverged)"


@app.command()
def main(
    first: str = typer.Argument(..., metavar="COMMIT", show_default=False),
    second: str = typer.Argument(..., metavar="COMMIT", show_default=False),
) -> None:
    """Report the relative order of two commits.

    Prints `<`, `>`, `=` or `<>` between them, keeping the arguments in the order
    given. The verdict is ancestry, the only order git guarantees; author dates are
    shown alongside and can run the other way after a rebase.
    """
    if git("rev-parse", "--git-dir").returncode != 0:
        raise typer.Exit(1)  # git has already said why

    a, b = resolve(first), resolve(second)
    rel, suffix = relation(a, b)

    print(f"{a.short} {rel} {b.short}{suffix}\n")

    show_refs = not (a.ref_is_sha and b.ref_is_sha)
    ref_w = max(len(a.ref), len(b.ref))
    sha_w = max(len(a.short), len(b.short))
    for c in (a, b):
        label = f"{c.ref:<{ref_w}}  " if show_refs else ""
        print(f"{label}{c.short:<{sha_w}}  {c.date}  {c.subject}")

    if rel == "<>":
        base = git("merge-base", a.sha, b.sha, quiet=True)
        if base.returncode == 0:
            split = resolve(base.stdout.strip())
            print(f"\nsplit at {split.short}  {split.date}  {split.subject}")
        else:
            print("\nno common ancestor (unrelated histories)")

    if rel in ("<", ">"):
        earlier, later = (a, b) if rel == "<" else (b, a)
        if earlier.authored > later.authored:
            print(
                "\nnote: authored in the opposite order "
                "(rebase, cherry-pick, or clock skew)"
            )


if __name__ == "__main__":
    app()
