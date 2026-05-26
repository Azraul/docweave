---
type: concept
description: "DocWeave uses bottom-up index propagation — each directory's _index.md aggregates descriptions from its children"
topics: [docweave, architecture]
---

# DocWeave Architecture

DocWeave's core pipeline runs in five phases:

1. **Load project.yaml** — reading types, addons, and build configuration
2. **Regenerate _index.md files** — scanning each directory, composing frontmatter, and generating wiki-linked listings
3. **Scan and parse notes** — extracting frontmatter, building the full index
4. **Run addons** — graph visualization, timeline rendering, and any custom plugins
5. **Write output** — copying rendered assets and generating `index.json`

The key innovation is step 2's **bottom-up approach**: leaf directories are processed first, so parent directories can read their children's `_index.md` frontmatter `description` field and include it in the parent's listing.

This creates a propagation chain where a `description` written at any level flows upward to every ancestor directory.