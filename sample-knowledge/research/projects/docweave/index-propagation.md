---
type: concept
description: "Propagated indexes let an LLM navigate the entire knowledge base by reading one _index.md per level — from root to leaf in logarithmic steps"
topics: [docweave, architecture]
---

# Index Propagation

The core idea: every directory's `_index.md` contains a `## Directories` section that lists each subdirectory with its `description` (sourced from the child's frontmatter). This means:

**An LLM can navigate hierarchically:**

```
root/_index.md
  → "Research I follow"
  → research/research/_index.md  
    → "Artificial intelligence"
    → research/ai/_index.md
      → "Landmark AI papers"
      → research/ai/papers/_index.md
        → "The transformer architecture"
        → .../attention-is-all-you-need/_index.md
          → "Multi-Head Attention explained"
          → .../multi-head-attention.md
```

Each hop reads one `_index.md` file (a few KB), decides whether to go deeper, and follows a `[[wikilink]]` to the next level. No JSON parsing, no database queries — just flat markdown files.

**For humans**, the same `_index.md` files render as browsable directory pages in the `.site/` output.