"""DocWeave CLI entry point — invoked as ``python3 -m docweave``."""

import os
import sys

from .config import load_config
from .builder import build_index
from .addons import run_addons
from .update_indexes import run_update_indexes
from .writer import write_index


def main():
    project_root = os.getcwd()

    print("DocWeave — build index")
    print(f"  root: {project_root}")
    print()

    # 1. Load config
    print("[1/5] Loading project.yaml...")
    config = load_config(project_root)
    print(f"  project: {config['project'].get('name', 'Untitled')}")
    print(f"  types:   {', '.join(config['types'].keys())}")
    print(f"  output:  {config['build']['output_dir']}")

    # 1.5 Regenerate _index.md files (if enabled)
    print()
    print("[1.5/5] Regenerating _index.md files...")
    run_update_indexes(project_root, config)

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
