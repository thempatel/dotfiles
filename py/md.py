#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.9.0"]
# ///
"""md - A tool for manipulating markdown files."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import typer

app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """md - A tool for manipulating markdown files."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Section:
    heading: str
    level: int
    content: list[str] = field(default_factory=list)
    children: list["Section"] = field(default_factory=list)

    def line_count(self) -> int:
        """Total content lines in this section and all descendants."""
        total = len(self.content)
        for child in self.children:
            total += child.line_count() + 1  # +1 for the heading line
        return total

    def flatten(self) -> list[str]:
        """Render this section back to markdown lines."""
        lines: list[str] = []
        if self.heading:
            lines.append(f"{'#' * self.level} {self.heading}")
        lines.extend(self.content)
        for child in self.children:
            lines.extend(child.flatten())
        return lines


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def _detect_code_fence(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("```") or stripped.startswith("~~~")


def parse_markdown(text: str) -> Section:
    """Parse markdown text into a tree of Sections.

    Heading levels are normalized so the smallest heading found becomes
    level 1, which lets us handle files that start at e.g. ### correctly.
    """
    lines = text.split("\n")

    # Find minimum heading level (outside of code fences)
    min_level = 7
    in_fence = False
    for line in lines:
        if _detect_code_fence(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            min_level = min(min_level, len(m.group(1)))

    offset = (min_level - 1) if min_level < 7 else 0

    root = Section(heading="", level=0)
    stack: list[Section] = [root]
    in_fence = False

    for line in lines:
        if _detect_code_fence(line):
            in_fence = not in_fence
            stack[-1].content.append(line)
            continue

        if in_fence:
            stack[-1].content.append(line)
            continue

        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1)) - offset
            heading = m.group(2).strip()
            section = Section(heading=heading, level=level)

            # Unwind to the closest ancestor with a lower level
            while len(stack) > 1 and stack[-1].level >= level:
                stack.pop()

            stack[-1].children.append(section)
            stack.append(section)
        else:
            stack[-1].content.append(line)

    return root


# ---------------------------------------------------------------------------
# Collapsing
# ---------------------------------------------------------------------------


def _merge_sections(sections: list[Section]) -> Section:
    """Merge several leaf sections into one, preserving headings as content."""
    if len(sections) == 1:
        return sections[0]

    merged = Section(
        heading=sections[0].heading,
        level=sections[0].level,
        content=list(sections[0].content),
    )
    for s in sections[1:]:
        merged.content.append("")
        merged.content.append(f"{'#' * s.level} {s.heading}")
        merged.content.extend(s.content)
    return merged


def collapse_small(node: Section, min_lines: int) -> None:
    """Bottom-up pass: collapse leaf sections smaller than *min_lines*.

    Strategy:
    1. Merge consecutive small leaf siblings into a single file.
    2. If only one small leaf remains with no siblings, collapse it upward
       into its parent's content.
    """
    # Recurse first so leaves are resolved before we inspect them.
    for child in node.children:
        collapse_small(child, min_lines)

    if not node.children:
        return

    # -- pass 1: group consecutive small leaves and merge them -------------
    new_children: list[Section] = []
    small_group: list[Section] = []

    def flush_small() -> None:
        if small_group:
            new_children.append(_merge_sections(small_group))
            small_group.clear()

    for child in node.children:
        is_small_leaf = not child.children and child.line_count() < min_lines
        if is_small_leaf:
            small_group.append(child)
        else:
            flush_small()
            new_children.append(child)
    flush_small()

    # -- pass 2: if a single small child remains, collapse into parent -----
    if (
        len(new_children) == 1
        and not new_children[0].children
        and new_children[0].line_count() < min_lines
    ):
        child = new_children[0]
        node.content.append("")
        node.content.extend(child.flatten())
        node.children = []
    else:
        node.children = new_children


# ---------------------------------------------------------------------------
# Writing to filesystem
# ---------------------------------------------------------------------------


def _strip_blank_edges(lines: list[str]) -> list[str]:
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    end = len(lines)
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-.")
    # Cap length to stay well within filesystem limits (255 bytes) while
    # leaving room for the .md extension and dedup suffixes.
    if len(text) > 200:
        text = text[:200].rstrip("-")
    return text or "untitled"


def _dedup_slug(slug: str, used: set[str]) -> str:
    """Return a unique slug within *used*, considering both bare names (dirs)
    and .md names (files) so they never collide on the filesystem."""
    candidate = slug
    i = 2
    while candidate in used or f"{candidate}.md" in used:
        candidate = f"{slug}-{i}"
        i += 1
    # Reserve both the bare name and the .md form so a later dir can't
    # collide with an earlier file or vice-versa.
    used.add(candidate)
    used.add(f"{candidate}.md")
    return candidate


@dataclass
class _Written:
    """A file or directory that was emitted, used to build TOCs in index.md."""

    slug: str
    heading: str
    is_dir: bool
    children: list["_Written"] = field(default_factory=list)


def _format_index(nodes: list[_Written], path_prefix: str, depth: int) -> list[str]:
    lines: list[str] = []
    indent = "  " * depth
    for node in nodes:
        link = (
            f"{path_prefix}{node.slug}/index.md"
            if node.is_dir
            else f"{path_prefix}{node.slug}.md"
        )
        lines.append(f"{indent}- [{node.heading}]({link})")
        if node.children:
            lines.extend(
                _format_index(node.children, f"{path_prefix}{node.slug}/", depth + 1)
            )
    return lines


def write_tree(section: Section, output_dir: Path) -> list[_Written]:
    """Write the section tree to disk. Each directory gets an index.md
    containing its heading, preamble, and a nested TOC of descendants."""
    output_dir.mkdir(parents=True, exist_ok=True)
    used_slugs: set[str] = {"index", "index.md"}

    written: list[_Written] = []
    for child in section.children:
        slug = _dedup_slug(_slugify(child.heading), used_slugs)
        if child.children:
            sub = write_tree(child, output_dir / slug)
            written.append(_Written(slug, child.heading, is_dir=True, children=sub))
        else:
            lines = [f"# {child.heading}"]
            body = _strip_blank_edges(child.content)
            if body:
                lines.append("")
                lines.extend(body)
            (output_dir / f"{slug}.md").write_text("\n".join(lines) + "\n")
            written.append(_Written(slug, child.heading, is_dir=False))

    content = _strip_blank_edges(section.content)
    index_lines: list[str] = []
    if section.heading:
        index_lines.append(f"# {section.heading}")
    elif written:
        index_lines.append("# Index")
    if content:
        if index_lines:
            index_lines.append("")
        index_lines.extend(content)
    if written:
        if index_lines:
            index_lines.append("")
        index_lines.extend(_format_index(written, "", 0))
    if index_lines:
        (output_dir / "index.md").write_text("\n".join(index_lines) + "\n")

    return written


# ---------------------------------------------------------------------------
# Dry-run tree printer
# ---------------------------------------------------------------------------


def _print_tree(section: Section, prefix: str = "", is_last: bool = True) -> None:
    if section.heading:
        connector = "`-- " if is_last else "|-- "
        kind = "dir" if section.children else "file"
        lc = section.line_count()
        typer.echo(f"{prefix}{connector}[{kind}] {section.heading}  ({lc} lines)")
        prefix += "    " if is_last else "|   "

    for i, child in enumerate(section.children):
        _print_tree(child, prefix, i == len(section.children) - 1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.command()
def split(
    ctx: typer.Context,
    file: Path = typer.Argument(None, help="Markdown file to split."),
    output_dir: Path = typer.Option(
        None,
        "-o",
        "--output-dir",
        help="Output directory (default: filename without extension).",
    ),
    min_lines: int = typer.Option(
        10,
        "-m",
        "--min-lines",
        help="Minimum lines for a leaf file; smaller sections get collapsed.",
    ),
    dry_run: bool = typer.Option(
        False, "-n", "--dry-run", help="Print the resulting tree without writing files."
    ),
) -> None:
    """Split a markdown file into a directory tree of sub-files."""
    if file is None:
        typer.echo(ctx.get_help())
        raise typer.Exit(0)

    if not file.exists():
        typer.echo(f"File not found: {file}", err=True)
        raise typer.Exit(1)

    root = parse_markdown(file.read_text())
    collapse_small(root, min_lines)

    # If the document has a single wrapping heading (e.g. `# Guide` at the top
    # of guide.md), promote it so the output dir doesn't get a redundant
    # subdirectory of the same name. Any text before that heading is folded
    # into the promoted section's body.
    if not root.heading and len(root.children) == 1:
        only = root.children[0]
        preamble = _strip_blank_edges(root.content)
        if preamble:
            only.content = [*preamble, "", *only.content]
        root = only

    if dry_run:
        if not root.children:
            typer.echo("(no sections to split)")
        else:
            _print_tree(root)
        return

    if output_dir is None:
        output_dir = file.with_suffix("")

    write_tree(root, output_dir)
    typer.echo(f"Wrote to {output_dir}/")


if __name__ == "__main__":
    app()
