#!/usr/bin/env python3
"""
DocWeave — schema-driven documentation build pipeline.

Reads project.yaml, walks content files, parses frontmatter and wikilinks,
discovers binary attachments, builds a unified JSON index, and writes it
to the output directory alongside copied attachments.

Usage:
    python3 build_index.py
"""

import json
import os
import re
import shutil
import sys
from fnmatch import fnmatch
from pathlib import Path

import yaml


# ──── 1. Config Loading ────────────────────────────────────────────

def load_config(project_root: str) -> dict:
    """Load and validate project.yaml."""
    path = os.path.join(project_root, "project.yaml")
    if not os.path.exists(path):
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(1)

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    if not config or "project" not in config:
        print("Error: project.yaml must contain a 'project' key", file=sys.stderr)
        sys.exit(1)
    if "types" not in config:
        print("Error: project.yaml must contain a 'types' key", file=sys.stderr)
        sys.exit(1)

    # Normalise build config
    build = config.setdefault("build", {})
    build.setdefault("content_dir", ".")
    build.setdefault("output_dir", ".site")
    build.setdefault("exclude_dirs", [".pi", ".git"])
    build.setdefault("ignore", ["*.tmp", "*.bak", "Thumbs.db", ".DS_Store"])

    # Normalise addons
    config.setdefault("addons", {})
    config["addons"].setdefault("graph", {"enabled": False})

    # Load .docweaveignore if present
    ignore_file = os.path.join(project_root, ".docweaveignore")
    if os.path.exists(ignore_file):
        with open(ignore_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    build["ignore"].append(line)

    return config


def ensure_output_dir(output_dir: str):
    """Create output directory if it doesn't exist."""
    os.makedirs(output_dir, exist_ok=True)


# ──── 2. File Walking ──────────────────────────────────────────────

def walk_content_files(project_root: str, config: dict) -> list[str]:
    """Walk content_dir and return relative paths of all .md files."""
    build = config["build"]
    content_dir = os.path.join(project_root, build["content_dir"])
    exclude_dirs = set(build.get("exclude_dirs", []))
    ignore_patterns = build.get("ignore", [])

    md_files = []
    for dirpath, dirnames, filenames in os.walk(content_dir):
        # Filter excluded dirs in-place
        dirnames[:] = [
            d for d in dirnames
            if d not in exclude_dirs and not d.startswith(".")
        ]

        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            rel_path = os.path.relpath(os.path.join(dirpath, fname), project_root)
            # Skip files matching ignore patterns
            if any(fnmatch(fname, p) for p in ignore_patterns):
                continue
            md_files.append(rel_path)

    return sorted(md_files)


# ──── 3. Frontmatter Parsing ───────────────────────────────────────

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
            # Normalise: strip .md extension if present
            target = re.sub(r"\.md$", "", raw).strip()
            links.append({
                "target": target,
                "display": display.strip() if display else None,
                "line": i,
            })
    return links


# ──── 4. Attachment Scanning ───────────────────────────────────────

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
        # Skip hidden files
        if fname.startswith("."):
            continue
        # Skip markdown files (handled separately)
        if fname.endswith(".md"):
            continue
        # Skip files matching ignore patterns
        if any(fnmatch(fname, p) for p in ignore_patterns):
            continue
        rel_path = os.path.join(dir_path, fname)
        attachments.append(rel_path)

    return attachments


# ──── 5. Note Parsing ──────────────────────────────────────────────

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
        # _index.md → directory slug (e.g., "notes")
        slug = os.path.dirname(rel_path) if os.path.dirname(rel_path) else rel_path
    else:
        slug = rel_path.replace(".md", "")

    slug = slug.replace("\\", "/")
    # Normalise: remove leading ./
    if slug.startswith("./"):
        slug = slug[2:]

    # Extract title: frontmatter 'title' field takes precedence, then first heading, then filename
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
            continue  # Already handled
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


# ──── 6. Index Building ────────────────────────────────────────────

def build_index(project_root: str, config: dict) -> dict:
    """Parse all notes and build the full index structure."""
    md_files = walk_content_files(project_root, config)

    # Parse all notes
    notes = {}
    slug_lookup = {}  # lowercase slug → list of note slugs (for disambiguation)

    for rel_path in md_files:
        note = parse_note(project_root, rel_path, config)
        if note is None:
            continue
        slug = note["slug"]

        # Handle slug collisions
        if slug in notes:
            print(f"  [error] Duplicate slug '{slug}': {rel_path} conflicts with {notes[slug]['path']}", file=sys.stderr)
            continue

        notes[slug] = note

        # Populate slug lookup (case-insensitive)
        key = slug.lower()
        slug_lookup.setdefault(key, []).append(slug)

    # Resolve backlinks (links_in)
    for slug, note in notes.items():
        links_out = note.get("links_out", [])
        for target in links_out:
            resolved = None

            # Direct match: canonical slug
            if target in notes:
                resolved = target
            else:
                # Try directory + _index convention: "notes/_index" → slug "notes"
                # Also "notes" (the directory slug from _index.md)
                dir_slug = target.replace("/_index", "")
                if dir_slug in notes:
                    resolved = dir_slug
                else:
                    # Case-insensitive lookup
                    target_key = target.lower()
                    dir_key = dir_slug.lower()
                    candidates = slug_lookup.get(target_key, [])
                    if not candidates:
                        candidates = slug_lookup.get(dir_key, [])
                    if len(candidates) == 1:
                        resolved = candidates[0]
                    elif len(candidates) > 1:
                        note.setdefault("links_unresolved", []).append({
                            "target": target,
                            "candidates": candidates,
                        })

            if resolved:
                notes[resolved].setdefault("links_in", []).append(slug)

    # Build slug_lookup map (entity name → canonical slug)
    slug_lookup_map = {}
    for sl, note in notes.items():
        # Index title
        if note.get("title"):
            key = note["title"].lower()
            if key not in slug_lookup_map:
                slug_lookup_map[key] = sl
        # Index by basename of slug
        base = sl.split("/")[-1].lower()
        if base not in slug_lookup_map:
            slug_lookup_map[base] = sl

    # Build sidebar tree
    sidebar_tree = build_sidebar_tree(notes)

    # Build type config for frontend
    types_config = {}
    for type_name, type_schema in config.get("types", {}).items():
        types_config[type_name] = {
            "icon": type_schema.get("icon", "📄"),
            "color": type_schema.get("color", "#888888"),
            "label": type_schema.get("label", type_name),
            "fields": type_schema.get("fields", {}),
        }

    index = {
        "project": config.get("project", {}),
        "types_config": types_config,
        "notes": notes,
        "sidebar_tree": sidebar_tree,
        "slug_lookup": slug_lookup_map,
        "stats": {
            "total_notes": len(notes),
            "total_files": len(md_files),
            "types": {t: {"label": types_config[t]["label"], "count": 0} for t in types_config},
        },
    }

    # Count per type
    for slug, note in notes.items():
        t = note.get("type")
        if t in index["stats"]["types"]:
            index["stats"]["types"][t]["count"] += 1

    return index


def build_sidebar_tree(notes: dict) -> list:
    """Build a recursive sidebar tree structure from note slugs.
    Returns a list of tree nodes:
      {name, type: "directory", note_slug?, title?, children: [...]}
      {name, type: "leaf", slug, note_type}
    """
    # Identify _index notes (their slug IS the directory name, e.g. "cats")
    index_notes = {}  # dir_name -> note slug
    for slug, note in notes.items():
        path = note.get("path", "")
        if path.endswith("_index.md"):
            # The slug of an _index note is the directory name
            dir_name = slug  # e.g. "cats", "litters"
            index_notes[dir_name] = slug

    # Group remaining notes by directory
    dirs = {}  # dir_path -> {children: [...]}
    root_children = []

    for slug, note in notes.items():
        path = note.get("path", "")
        if path.endswith("_index.md"):
            continue  # handled above

        parts = slug.split("/")
        if len(parts) > 1:
            dir_name = parts[0]
            if dir_name not in dirs:
                dirs[dir_name] = []
            # Use h1 (heading name) for sidebar display, not frontmatter title
            leaf_name = note.get("h1", note.get("title", slug))
            dirs[dir_name].append({
                "name": leaf_name,
                "type": "leaf",
                "slug": slug,
                "note_type": note.get("type", ""),
            })
        else:
            root_children.append({
                "name": note.get("title", parts[-1]),
                "type": "leaf",
                "slug": slug,
                "note_type": note.get("type", ""),
            })

    # Build tree
    tree = []

    # Sort dir names alphabetically
    for dir_name in sorted(dirs.keys()):
        dir_node = {
            "name": dir_name,
            "type": "directory",
            "children": sorted(dirs[dir_name], key=lambda c: c.get("name", "").lower()),
        }
        if dir_name in index_notes:
            dir_node["note_slug"] = index_notes[dir_name]
            dir_node["title"] = notes[index_notes[dir_name]].get("title", dir_name)
        tree.append(dir_node)

    # Root-level leaf notes
    root_children.sort(key=lambda c: c.get("name", "").lower())
    tree.extend(root_children)

    return tree


# ──── 7. Addons ────────────────────────────────────────────────────

def run_addons(index: dict, config: dict, project_root: str):
    """Run post-processing addons to enrich the index."""
    addons = config.get("addons", {})

    # Graph addon: no data to add to index, but flag its presence
    if addons.get("graph", {}).get("enabled"):
        index["addons"] = index.get("addons", {})
        index["addons"]["graph"] = {"enabled": True}

    # Timeline addon
    if "timeline" in addons:
        run_timeline_addon(index, config, project_root)

    # Future addons hook here
    # if "tag_cloud" in addons: run_tag_cloud_addon(...)
    # if "rss" in addons: run_rss_addon(...)


def run_timeline_addon(index: dict, config: dict, project_root: str):
    """Build timeline from notes with a date field matching addons.timeline.field."""
    addon_cfg = config["addons"]["timeline"]
    field_name = addon_cfg.get("field")
    date_format = addon_cfg.get("format", "iso")

    if not field_name:
        return

    timeline = []
    unparseable = []

    for slug, note in index["notes"].items():
        raw = note.get(field_name)
        if raw is None:
            continue

        # Determine date value
        if date_format == "iso":
            date_val = str(raw)
            timeline.append({
                "slug": slug,
                "title": note.get("title", slug),
                "type": note.get("type"),
                "date": date_val,
            })
        else:
            # Fallback: treat as label
            unparseable.append({
                "slug": slug,
                "title": note.get("title", slug),
                "date": str(raw),
            })

    # Sort chronologically
    timeline.sort(key=lambda e: e.get("date", ""))

    index["addons"] = index.get("addons", {})
    index["addons"]["timeline"] = {
        "entries": timeline,
        "unparseable": unparseable,
        "field": field_name,
        "format": date_format,
    }


# ──── 8. Output Writing ────────────────────────────────────────────

def write_index(index: dict, project_root: str, config: dict):
    """Write index.json and copy attachments to output directory."""
    output_dir = os.path.join(project_root, config["build"]["output_dir"])
    ensure_output_dir(output_dir)

    # Copy shared renderer files (index.html, zettel.html, style.css)
    renderer_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "renderer")
    renderer_files_copied = 0
    if os.path.isdir(renderer_dir):
        for fname in os.listdir(renderer_dir):
            src = os.path.join(renderer_dir, fname)
            if os.path.isfile(src):
                dst = os.path.join(output_dir, fname)
                shutil.copy2(src, dst)
                renderer_files_copied += 1
    if renderer_files_copied:
        print(f"  → {renderer_files_copied} renderer file(s) copied")
    else:
        print(f"  [warn] No renderer files found in {renderer_dir}")

    # Write index.json
    index_path = os.path.join(output_dir, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"  → {os.path.relpath(index_path, project_root)} ({os.path.getsize(index_path)} bytes)")

    # Copy binary attachments
    attachments_copied = 0
    for slug, note in index["notes"].items():
        for att in note.get("attachments", []):
            src = os.path.join(project_root, att)
            dst = os.path.join(output_dir, att)
            if os.path.exists(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                attachments_copied += 1

    if attachments_copied:
        print(f"  → {attachments_copied} attachment(s) copied")


# ──── 9. Main ──────────────────────────────────────────────────────

def main():
    project_root = os.getcwd()

    print(f"DocWeave — build index")
    print(f"  root: {project_root}")
    print()

    # 1. Load config
    print("[1/5] Loading project.yaml...")
    config = load_config(project_root)
    print(f"  project: {config['project'].get('name', 'Untitled')}")
    print(f"  types:   {', '.join(config['types'].keys())}")
    print(f"  output:  {config['build']['output_dir']}")

    # 2. Build index
    print()
    print("[2/5] Scanning and parsing notes...")
    index = build_index(project_root, config)
    print(f"  {index['stats']['total_notes']} note(s) indexed")
    for t, info in index['stats']['types'].items():
        if info['count'] > 0:
            print(f"    {info['label']}: {info['count']}")

    # 3. Run addons
    print()
    print("[3/5] Running addons...")
    run_addons(index, config, project_root)
    active_addons = index.get("addons", {})
    if active_addons:
        for name, data in active_addons.items():
            if isinstance(data, dict) and data.get("enabled") is False:
                continue
            print(f"  ✓ {name}")
    else:
        print("  (none enabled)")

    # 4. Write output
    print()
    print("[4/5] Writing output...")
    write_index(index, project_root, config)

    # 5. Summary
    print()
    print("[5/5] Done.")
    print(f"  Notes:     {index['stats']['total_notes']}")
    print(f"  Slug refs: {len(index.get('slug_lookup', {}))} total")
    print(f"  Ambiguous links: {index['stats'].get('ambiguous_links', 0)}")
    print(f"  Addons:    {', '.join(active_addons.keys()) if active_addons else 'none'}")


if __name__ == "__main__":
    main()
