"""Index building — walks files, resolves backlinks, builds sidebar tree."""

import os
import sys
from fnmatch import fnmatch

from . import parser


def walk_content_files(project_root: str, config: dict) -> list[str]:
    """Walk content_dir and return relative paths of all .md files."""
    build_cfg = config["build"]
    content_dir = os.path.join(project_root, build_cfg["content_dir"])
    exclude_dirs = set(build_cfg.get("exclude_dirs", []))
    ignore_patterns = build_cfg.get("ignore", [])

    md_files = []
    for dirpath, dirnames, filenames in os.walk(content_dir):
        dirnames[:] = [
            d for d in dirnames
            if d not in exclude_dirs and not d.startswith(".")
        ]

        for fname in filenames:
            if not fname.endswith(".md"):
                continue
            rel_path = os.path.relpath(os.path.join(dirpath, fname), project_root)
            if any(fnmatch(fname, p) for p in ignore_patterns):
                continue
            if any(fnmatch(rel_path, p) for p in ignore_patterns):
                continue
            md_files.append(rel_path)

    return sorted(md_files)


def build_index(project_root: str, config: dict) -> dict:
    """Parse all notes and build the full index structure."""
    md_files = walk_content_files(project_root, config)

    notes = {}
    slug_lookup = {}  # lowercase slug → list of note slugs (for disambiguation)
    ambiguous_count = 0

    for rel_path in md_files:
        note = parser.parse_note(project_root, rel_path, config)
        if note is None:
            continue
        slug = note["slug"]

        if slug in notes:
            print(
                f"  [error] Duplicate slug '{slug}': {rel_path} "
                f"conflicts with {notes[slug]['path']}",
                file=sys.stderr,
            )
            continue

        notes[slug] = note
        key = slug.lower()
        slug_lookup.setdefault(key, []).append(slug)

    # Resolve backlinks (links_in)
    for slug, note in notes.items():
        for target in note.get("links_out", []):
            resolved = _resolve_link(target, notes, slug_lookup)

            if isinstance(resolved, str):
                notes[resolved].setdefault("links_in", []).append(slug)
            elif isinstance(resolved, list):
                ambiguous_count += 1
                note.setdefault("links_unresolved", []).append({
                    "target": target,
                    "candidates": resolved,
                })

    # Build slug_lookup map (entity name → canonical slug)
    slug_lookup_map = {}
    for sl, note in notes.items():
        if note.get("title"):
            key = note["title"].lower()
            if key in slug_lookup_map:
                print(
                    f"  [warn] Duplicate title '{note['title']}': "
                    f"{sl} and {slug_lookup_map[key]} share the same slug lookup key",
                    file=sys.stderr,
                )
            slug_lookup_map.setdefault(key, sl)

        base = sl.split("/")[-1].lower()
        if base in slug_lookup_map and slug_lookup_map[base] != sl:
            print(
                f"  [warn] Duplicate basename '{base}': "
                f"{sl} and {slug_lookup_map[base]} share the same slug lookup key",
                file=sys.stderr,
            )
        slug_lookup_map.setdefault(base, sl)

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
            "ambiguous_links": ambiguous_count,
            "types": {t: {"label": types_config[t]["label"], "count": 0}
                      for t in types_config},
        },
    }

    for slug, note in notes.items():
        t = note.get("type")
        if t in index["stats"]["types"]:
            index["stats"]["types"][t]["count"] += 1

    return index


def _resolve_link(target: str, notes: dict, slug_lookup: dict) -> str | list | None:
    """Resolve a wikilink target to a canonical slug.

    Returns:
        str  — resolved slug
        list — multiple ambiguous candidates
        None — no match
    """
    # Direct match
    if target in notes:
        return target

    # Directory + _index convention: "notes/_index" → slug "notes"
    dir_slug = target.replace("/_index", "")
    if dir_slug in notes:
        return dir_slug

    # Case-insensitive lookup
    target_key = target.lower()
    candidates = slug_lookup.get(target_key, [])
    if not candidates:
        # Also try with /_index stripped
        candidates = slug_lookup.get(dir_slug.lower(), [])

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        return candidates  # ambiguous
    return None


def build_sidebar_tree(notes: dict) -> list:
    """Build a recursive sidebar tree structure from note slugs.

    Returns a list of tree nodes:
      {name, type: "directory", note_slug?, title?, children: [...]}
      {name, type: "leaf", slug, note_type}
    """
    index_notes = {}
    for slug, note in notes.items():
        path = note.get("path", "")
        if path.endswith("_index.md"):
            index_notes[slug] = slug

    dirs = {}
    root_children = []

    for slug, note in notes.items():
        path = note.get("path", "")
        if path.endswith("_index.md"):
            continue

        parts = slug.split("/")
        if len(parts) > 1:
            dir_name = parts[0]
            if dir_name not in dirs:
                dirs[dir_name] = []
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

    tree = []
    for dir_name in sorted(dirs.keys()):
        dir_node = {
            "name": dir_name,
            "type": "directory",
            "children": sorted(dirs[dir_name],
                              key=lambda c: c.get("name", "").lower()),
        }
        if dir_name in index_notes:
            dir_node["note_slug"] = index_notes[dir_name]
            dir_node["title"] = notes[index_notes[dir_name]].get("title", dir_name)
        tree.append(dir_node)

    root_children.sort(key=lambda c: c.get("name", "").lower())
    tree.extend(root_children)

    return tree
