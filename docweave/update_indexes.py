"""Auto-generate _index.md files from directory contents.

Integrated as a docweave pre-scan step, gated by
``addons.update_indexes.enabled`` in ``project.yaml``.

Scans each content directory, reads frontmatter and first paragraph from each
note, and regenerates _index.md files with accurate file listings organized by
type. Preserves existing frontmatter, intro text, and See Also / Related
sections.
"""

import os
import re
from pathlib import Path

import yaml

# ── File filters ───────────────────────────────────────────────────────────

EXCLUDE_FILES = {"_index.md", "AGENTS.md", "README.md", "temp.md", "SKILL.md"}

# Frontmatter parsers
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n?---\s*\n", re.DOTALL)


def parse_frontmatter(text: str):
    """Return (frontmatter_dict, body)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    body = text[m.end() :]
    return fm, body


def extract_heading(body: str) -> str | None:
    """Extract the first `# Heading` from body text."""
    m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None


def extract_first_paragraph(body: str, heading: str | None = None) -> str:
    """Extract the first substantive paragraph after the heading (~200 chars)."""
    if heading:
        body = re.sub(r"^#\s+.*$", "", body, count=1, flags=re.MULTILINE)

    paragraphs = re.split(r"\n\s*\n", body)
    for para in paragraphs:
        cleaned = para.strip()
        if not cleaned or cleaned.startswith("---") or cleaned.startswith("```"):
            continue
        if len(cleaned) < 20:
            continue
        excerpt = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", r"\1", cleaned)
        if len(excerpt) > 200:
            excerpt = excerpt[:200].rsplit(" ", 1)[0] + "…"
        return excerpt.strip()
    return ""


def slug_to_display(slug: str) -> str:
    """Convert a filename slug to a display name."""
    name = slug.rsplit("/", 1)[-1].replace("_", " ").replace("-", " ").strip()
    return name.title()


# ── Index generation ───────────────────────────────────────────────────────


def generate_index(dir_path: Path, content_dir: Path, exclude_dirs: set) -> str | None:
    """Generate _index.md content for a directory. Returns None if empty."""
    rel = dir_path.relative_to(content_dir)
    rel_str = str(rel) if str(rel) != "." else ""

    # Collect .md files and subdirectories
    files = []
    subdirs = []
    for child in sorted(dir_path.iterdir()):
        if child.name.startswith("."):
            continue
        if child.is_dir():
            if child.name not in exclude_dirs:
                subdirs.append(child)
        elif child.suffix == ".md" and child.name not in EXCLUDE_FILES:
            files.append(child)

    if not files and not subdirs:
        return None

    raw_path = dir_path / "_index.md"
    existing_fm = {}
    existing_body = ""
    if raw_path.exists():
        existing_fm, existing_body = parse_frontmatter(raw_path.read_text(encoding="utf-8"))

    fm = dict(existing_fm)
    if "type" not in fm:
        fm["type"] = "index"
    if "topics" not in fm:
        fm["topics"] = [rel_str.replace("/", " ").strip() or "index"]

    lines = []
    title = existing_fm.get("title") or (f"{slug_to_display(rel_str)}" if rel_str else "Home")

    # Preserve existing intro paragraph
    existing_intro = ""
    if existing_body:
        match = re.search(r"^(.*?)(?:\n##|\n- \*\*\[\[|\n---|\Z)", existing_body, re.DOTALL)
        if match:
            intro_candidate = match.group(1).strip()
            if intro_candidate and not intro_candidate.startswith("##") and not intro_candidate.startswith("-"):
                if len(intro_candidate) > 60:
                    existing_intro = intro_candidate

    if existing_intro:
        has_heading = any(l.startswith("# ") for l in existing_intro.split("\n"))
        if not has_heading and title:
            lines.append(f"# {title}")
            lines.append("")
        lines.append(existing_intro)
        lines.append("")
    else:
        if title:
            lines.append(f"# {title}")
            lines.append("")

    existing_sections = extract_existing_sections(existing_body)

    # Group files by type
    by_type: dict[str, list] = {}
    by_topic: dict[str, list] = {}
    uncategorized = []

    for f in files:
        text = f.read_text(encoding="utf-8")
        fm_note, body = parse_frontmatter(text)

        # Prefer explicit frontmatter description (fast, semantic, LLM-friendly)
        desc = fm_note.get("description", "")
        if not desc:
            heading = extract_heading(body)
            desc = extract_first_paragraph(body, heading)
        else:
            # Truncate long descriptions at 200 chars
            if len(desc) > 200:
                desc = desc[:200].rsplit(" ", 1)[0] + "…"
            heading = None

        note_type = fm_note.get("type", "note")
        topics = fm_note.get("topics", [])
        if isinstance(topics, str):
            topics = [topics]

        entry = (f, fm_note, desc)

        if note_type and note_type != "default":
            by_type.setdefault(note_type, []).append(entry)
        else:
            if topics:
                for t in topics:
                    by_topic.setdefault(t, []).append(entry)
            else:
                uncategorized.append(entry)

    # Render type sections
    type_order = [
        "character", "location", "event", "faction", "concept", "group",
        "article", "topic", "art", "visual",
    ]
    rendered_types = set()

    for t in type_order:
        if t in by_type:
            render_section(lines, t, by_type[t], content_dir, page_title=title)
            rendered_types.add(t)

    for t in sorted(by_type):
        if t not in rendered_types:
            render_section(lines, t, by_type[t], content_dir, page_title=title)

    if not by_type and by_topic:
        for topic in sorted(by_topic):
            render_section(lines, topic.title(), by_topic[topic], content_dir, page_title=title)

    if uncategorized:
        if not by_type and not by_topic:
            render_section(lines, "Notes", uncategorized, content_dir, page_title=title)
        else:
            render_section(lines, "Other", uncategorized, content_dir, page_title=title)

    # Subdirectory entries
    if subdirs:
        lines.append("## Directories")
        lines.append("")
    for sd in subdirs:
        sub_rel = sd.relative_to(content_dir)
        sub_slug = str(sub_rel) + "/_index"
        sub_file = sd / "_index.md"
        if not sub_file.exists():
            continue
        sub_text = sub_file.read_text(encoding="utf-8")
        sub_fm, sub_body = parse_frontmatter(sub_text)
        sub_title = extract_heading(sub_body) or slug_to_display(sd.name)
        sub_desc = extract_first_paragraph(sub_body, sub_title)
        if not sub_desc:
            sub_types = sub_fm.get("topics", [])
            if sub_types:
                sub_desc = f"Notes on {', '.join(sub_types[:3])}."
            else:
                sub_desc = f"See [[{sub_slug}|{sub_title}]] for details."

        lines.append(f"- **[[{sub_slug}|{sub_title}]]** — {sub_desc}")

    # Preserve See Also / Related
    if existing_sections.get("see_also"):
        lines.append("")
        lines.append("## See Also")
        lines.extend(existing_sections["see_also"])

    if existing_sections.get("related"):
        lines.append("")
        lines.append("## Related")
        lines.extend(existing_sections["related"])

    lines.append("")
    lines.append("<!-- auto-generated by docweave -->")

    return build_full_index(fm, lines)


def render_section(lines, section_title, entries, content_dir, page_title=""):
    """Render a list of file entries under a section heading."""
    display_title = section_title.replace("_", " ").title()
    if not display_title.endswith("s"):
        display_title = display_title + "s"
    if display_title.lower() == page_title.lower():
        display_title = ""
    if display_title:
        lines.append(f"## {display_title}")
        lines.append("")

    for f, fm, desc in sorted(entries, key=lambda x: x[0].name):
        slug = str(f.relative_to(content_dir).with_suffix(""))
        display_name = (
            fm.get("title")
            or extract_heading(f.read_text(encoding="utf-8").split("---", 2)[-1] if "---" in f.read_text(encoding="utf-8") else "")
            or slug_to_display(f.stem)
        )
        if desc and not desc.startswith("See "):
            lines.append(f"- **[[{slug}|{display_name}]]** — {desc}")
        else:
            lines.append(f"- **[[{slug}|{display_name}]]**")
    lines.append("")


def extract_existing_sections(body: str) -> dict:
    """Extract See Also and Related sections from existing _index body."""
    sections = {}
    current_section = None
    for line in body.split("\n"):
        if line.startswith("## See Also"):
            current_section = "see_also"
            sections.setdefault("see_also", [])
            continue
        elif line.startswith("## Related"):
            current_section = "related"
            sections.setdefault("related", [])
            continue
        elif line.startswith("## "):
            current_section = None
            continue
        if current_section and line.strip() and not line.strip().startswith("<!--"):
            sections.setdefault(current_section, []).append(line)
    return sections


def build_full_index(fm: dict, body_lines: list) -> str:
    """Build the complete _index.md file content including frontmatter."""
    fm_lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, list):
            fm_lines.append(f"{key}: [{', '.join(str(v) for v in value)}]")
        elif isinstance(value, str):
            fm_lines.append(f"{key}: {value}")
        else:
            fm_lines.append(f"{key}: {value}")
    fm_lines.append("---")
    fm_lines.append("")
    return "\n".join(fm_lines + body_lines)


# ── Directory walking ──────────────────────────────────────────────────────


def find_directories(root: Path, exclude_dirs: set) -> list[Path]:
    """Find all directories containing .md files, excluding hidden/excluded dirs."""
    dirs = []
    for d in root.rglob("*"):
        if not d.is_dir():
            continue
        rel_parts = d.relative_to(root).parts
        if any(p.startswith(".") or p in exclude_dirs for p in rel_parts):
            continue
        has_md = any(f.suffix == ".md" for f in d.iterdir())
        has_md_subdirs = any(
            child.is_dir()
            and child.name not in exclude_dirs
            and not child.name.startswith(".")
            for child in d.iterdir()
        )
        if has_md or has_md_subdirs:
            dirs.append(d)
    return sorted(dirs)


# ── Public entry point (called from docweave build) ────────────────────────


def run_update_indexes(project_root: str, config: dict) -> None:
    """Regenerate all _index.md files. Called as a pre-scan step by docweave."""
    addon_cfg = config.get("addons", {}).get("update_indexes", {})
    if not addon_cfg.get("enabled", False):
        return

    content_dir = Path(project_root)
    exclude_dirs = set(config["build"].get("exclude_dirs", [])) | {".scripts"}

    directories = find_directories(content_dir, exclude_dirs)
    updated = 0
    skipped = 0

    for d in directories:
        rel = d.relative_to(content_dir)
        index_path = d / "_index.md"
        result = generate_index(d, content_dir, exclude_dirs)

        if result is None:
            if index_path.exists():
                index_path.unlink()
                print(f"  🗑️  Removed empty {rel / '_index.md'}")
                updated += 1
            else:
                skipped += 1
            continue

        index_path.write_text(result, encoding="utf-8")
        if index_path.exists():
            print(f"  ✓ Updated {rel / '_index.md'}")
            updated += 1

    total = updated + skipped
    print(f"\n  {updated} updated, {skipped} skipped (empty)")


# ── Standalone CLI entry point ─────────────────────────────────────────────


def main():
    """Standalone CLI: run the update_indexes step independently.

    Usage:
        python3 -m docweave.update_indexes
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Auto-generate _index.md files from directory contents."
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Dry-run: show what would change without writing.",
    )
    parser.add_argument(
        "--dir", "-d",
        type=str,
        default=None,
        help="Only update a specific directory tree (e.g., 'events' or 'characters').",
    )
    args = parser.parse_args()

    # Load project config to get exclude dirs
    project_root = os.getcwd()
    config_path = os.path.join(project_root, "project.yaml")
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    exclude_dirs = set(config.get("build", {}).get("exclude_dirs", [])) | {".scripts"}

    content_root = Path(project_root)

    if args.dir:
        target = content_root / args.dir
        if not target.is_dir():
            print(f"❌ Directory '{target}' does not exist.", file=sys.stderr)
            sys.exit(1)
        directories = [target] + [
            d for d in find_directories(target, exclude_dirs)
            if d != target and str(d).startswith(str(target))
        ]
    else:
        directories = find_directories(content_root, exclude_dirs)

    updated = 0
    skipped = 0
    errors = 0

    for d in directories:
        rel = d.relative_to(content_root)
        index_path = d / "_index.md"
        result = generate_index(d, content_root, exclude_dirs)

        if result is None:
            if index_path.exists() and not args.check:
                index_path.unlink()
                print(f"  🗑️  Removed empty {rel / '_index.md'}")
                updated += 1
            else:
                skipped += 1
            continue

        if args.check:
            if index_path.exists():
                existing = index_path.read_text(encoding="utf-8")
                if existing.strip() == result.strip():
                    print(f"  ✓ {rel / '_index.md'} — unchanged")
                else:
                    print(f"  ✗ {rel / '_index.md'} — would update")
                    existing_lines = existing.strip().split("\n")
                    new_lines = result.strip().split("\n")
                    delta = len(new_lines) - len(existing_lines)
                    print(f"    ({len(new_lines)} lines vs {len(existing_lines)} existing, delta: {delta:+d})")
                    updated += 1
            else:
                print(f"  ✗ {rel / '_index.md'} — would create ({len(result.split(chr(10)))} lines)")
                updated += 1
        else:
            try:
                index_path.write_text(result, encoding="utf-8")
                print(f"  ✓ Updated {rel / '_index.md'}")
                updated += 1
            except Exception as e:
                print(f"  ❌ Error writing {rel / '_index.md'}: {e}", file=sys.stderr)
                errors += 1

    total = updated + skipped + errors
    print(f"\n{'───' * 10}")
    print(f"  {total} directories scanned")
    print(f"  {updated} would change" if args.check else f"  {updated} written")
    print(f"  {skipped} skipped (empty)")
    if errors:
        print(f"  {errors} errors")
    print("  (dry run — no files written)" if args.check else "")


if __name__ == "__main__":
    main()
