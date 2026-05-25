"""Output writing — index.json, renderer files, binary attachments."""

import json
import os
import shutil


def ensure_output_dir(output_dir: str):
    """Create output directory if it doesn't exist."""
    os.makedirs(output_dir, exist_ok=True)


def write_index(index: dict, project_root: str, config: dict):
    """Write index.json and copy attachments to output directory."""
    output_dir = os.path.join(project_root, config["build"]["output_dir"])
    ensure_output_dir(output_dir)

    # Copy shared renderer files (index.html, zettel.html, style.css)
    _copy_renderer_files(output_dir)

    # Write index.json
    index_path = os.path.join(output_dir, "index.json")
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"  → {os.path.relpath(index_path, project_root)} "
          f"({os.path.getsize(index_path)} bytes)")

    # Copy binary attachments
    _copy_attachments(index, project_root, output_dir)


def _copy_renderer_files(output_dir: str):
    """Copy shared renderer HTML/CSS/JS into the output directory."""
    # __file__ is docweave/writer.py → go up twice for project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    renderer_dir = os.path.join(project_root, "renderer")

    copied = 0
    if os.path.isdir(renderer_dir):
        for fname in os.listdir(renderer_dir):
            src = os.path.join(renderer_dir, fname)
            if os.path.isfile(src):
                dst = os.path.join(output_dir, fname)
                shutil.copy2(src, dst)
                copied += 1

    if copied:
        print(f"  → {copied} renderer file(s) copied")
    else:
        print(f"  [warn] No renderer files found in {renderer_dir}")


def _copy_attachments(index: dict, project_root: str, output_dir: str):
    """Copy binary attachment files to the output directory."""
    copied = 0
    for slug, note in index["notes"].items():
        for att in note.get("attachments", []):
            src = os.path.join(project_root, att)
            dst = os.path.join(output_dir, att)
            if os.path.exists(src):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied += 1

    if copied:
        print(f"  → {copied} attachment(s) copied")
