"""Frontmatter, wikilink, and note file parsing."""

import os
import re
from fnmatch import fnmatch

import yaml


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\[\]]+?)(?:\|([^\[\]]*?))?\]\]")


def parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content. Returns dict or None."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1))
        if isinstance(fm, dict):
            return fm
        return None
    except yaml.YAMLError:
        return None


def extract_body(content: str) -> str:
    """Return markdown body after stripping frontmatter."""
    m = FRONTMATTER_RE.match(content)
    if m:
        return content[m.end():].strip()
    return content.strip()


def extract_wikilinks(body: str) -> list[dict]:
    """Extract wikilinks from body text.

    Returns list of {target, display, line} dicts.
    """
    links = []
    for i, line in enumerate(body.split("\n"), 1):
        for match in WIKILINK_RE.finditer(line):
            raw = match.group(1).strip()
            display = match.group(2)
            if raw.startswith("http://") or raw.startswith("https://"):
                continue
            target = re.sub(r"\.md$", "", raw).strip()
            links.append({
                "target": target,
                "display": display.strip() if display else None,
                "line": i,
            })
    return links


def scan_attachments(project_root: str, dir_path: str, config: dict) -> list[str]:
    """Scan a directory for non-.md files (binary attachments).

    Returns list of relative paths from project root.
    """
    ignore_patterns = config["build"].get("ignore", [])
    abs_dir = os.path.join(project_root, dir_path)
    if not os.path.isdir(abs_dir):
        return []

    attachments = []
    for fname in sorted(os.listdir(abs_dir)):
        if fname.startswith("."):
            continue
        if fname.endswith(".md"):
            continue
        if any(fnmatch(fname, p) for p in ignore_patterns):
            continue
        rel_path = os.path.join(dir_path, fname)
        attachments.append(rel_path)

    return attachments


def parse_note(project_root: str, rel_path: str, config: dict) -> dict | None:
    """Parse a single markdown file into a note entry.

    Returns None if frontmatter is missing or type is unknown.
    """
    abs_path = os.path.join(project_root, rel_path)
    try:
        with open(abs_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return None

    fm = parse_frontmatter(content)
    if fm is None:
        print(f"  [warn] No frontmatter: {rel_path}", file=sys.stderr)
        return None

    note_type = fm.get("type")
    if not note_type:
        print(f"  [warn] No 'type' field: {rel_path}", file=sys.stderr)
        return None

    types_config = config.get("types", {})
    if note_type not in types_config:
        print(f"  [warn] Unknown type '{note_type}': {rel_path}", file=sys.stderr)
        return None

    type_schema = types_config[note_type]
    field_schemas = type_schema.get("fields", {})

    body = extract_body(content)
    wikilinks = extract_wikilinks(body)

    # Build slug
    slug = rel_path.replace("\\", "/")
    if slug.endswith("_index.md"):
        slug = os.path.dirname(rel_path) if os.path.dirname(rel_path) else rel_path
    else:
        slug = rel_path.replace(".md", "")

    slug = slug.replace("\\", "/")
    if slug.startswith("./"):
        slug = slug[2:]

    # Extract title: frontmatter > first heading > filename
    fm_title = fm.get("title")
    h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    h1 = h1_match.group(1).strip() if h1_match else None
    if fm_title and isinstance(fm_title, str):
        title = fm_title.strip()
    elif h1:
        title = h1
    else:
        title = os.path.basename(rel_path).replace(".md", "")

    # Build note entry
    note = {
        "slug": slug,
        "title": title,
        "h1": h1 or title,
        "type": note_type,
        "path": rel_path.replace("\\", "/"),
        "body": body,
        "links_out": [l["target"] for l in wikilinks],
        "links_in": [],
    }

    # Classify frontmatter fields according to schema
    for key, value in fm.items():
        if key in ("type", "title"):
            continue
        schema = field_schemas.get(key, {})
        field_type = schema.get("type", "tag")
        label = schema.get("label", key)

        note[key] = value
        note[f"_{key}_type"] = field_type
        note[f"_{key}_label"] = label

    # Directory scoping for _index.md files: scan for attachments
    if rel_path.endswith("_index.md"):
        note_dir = os.path.dirname(rel_path)
        attachments = scan_attachments(project_root, note_dir, config)
        if attachments:
            note["attachments"] = attachments

    return note
