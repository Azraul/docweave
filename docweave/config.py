"""project.yaml loading and validation."""

import os
import sys

import yaml


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
    # Auto-exclude common non-content dirs. `docweave` and `bin` are
    # excluded by default so the package can live inside a project tree.
    build.setdefault("exclude_dirs", [".pi", ".git", "docweave", "bin"])
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
