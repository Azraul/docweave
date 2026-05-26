# DocWeave — LLM Wiki Generator

**DocWeave** turns markdown notes into a knowledge base that both **humans and LLMs** can navigate.

For **people**: a browsable static site with type badges, graph view, timeline, and backlinks.  
For **LLMs**: structured `index.json`, auto-generated directory indexes, and short semantic `description` fields in every note's frontmatter.

You write atomic notes with YAML frontmatter. DocWeave builds the wiki — and the knowledge structure that an LLM agent can traverse.

## Why an LLM Wiki?

Andrej Karpathy described the vision: a personal knowledge base that an LLM can query like a database. But dumping raw PDFs, images, and random files doesn't work — LLMs can't parse binary formats, and unstructured data is invisible to them.

The alternative: **atomic notes with structured metadata, organized in a hierarchical directory tree with semantic descriptions at every level.**

An LLM agent navigating a DocWeave knowledge base reads one `_index.md` per level, sees what's inside, and drills deeper using `[[wikilinks]]`. It never touches a PDF or image — the `.md` notes describe everything.

## Demo: sample-knowledge

The **[sample-knowledge/](sample-knowledge/)** directory is a complete, working knowledge base. Build it and open `.site/` in a browser:

```bash
cd sample-knowledge
../bin/docweave

# Or from the project root:
make build
```

**What's inside:**

```
sample-knowledge/
  _index.md                         ← Root: "My personal knowledge base"
  project.yaml                      ← One config to rule them all

  people/
    samuel-johnson.md               ← S.J. — lexicographer, wit, accidental meme

  research/
    ai/
      papers/
        attention-is-all-you-need/  ← Vaswani et al. 2017 — Transformer paper
          _index.md                 ← Folder entity, with description
          abstract.md               ← Atomic concept notes inside
          multi-head-attention.md
          positional-encoding.md
        resnet/                     ← He et al. 2015 — Deep residual learning
          _index.md
          abstract.md
          skip-connections.md
        deepseek-v4/                ← DeepSeek-V4 MoE preview
          _index.md
          abstract.md
          on-policy-distillation.md
    projects/
      docweave/                     ← The tool that built this knowledge base
        _index.md
        architecture.md
        index-propagation.md

  podcasts/
    hardcore-history-prophets-of-doom.md  ← Dan Carlin on the Münster Rebellion
```

The three paper folders (`attention-is-all-you-need`, `resnet`, `deepseek-v4`) demonstrate the core pattern: **a folder per entity, with an `_index.md` as the front door and atomic notes inside.**

Each `_index.md` has a `description` in its frontmatter. Those descriptions propagate upward through the directory tree — so `research/_index.md` shows summaries from `research/ai/`, which shows summaries from `research/ai/papers/`, which shows summaries from each paper folder. An LLM reads one file per level and understands the full shape.

## Quick Start

```bash
# Build the sample
cd sample-knowledge
../bin/docweave

# Serve locally
python3 -m http.server -d .site
# → Open http://localhost:8000
```

Or use `make` from the root:

```bash
make build    # Build sample-knowledge
make serve    # Build + serve on :8000
```

## The Architecture

### Atomic Notes + Propagated Indexes

```
leaf note (on-policy-distillation.md)
  → paper folder (_index.md lists it)
    → papers/ _index.md lists paper folder with its description
      → ai/ _index.md lists papers/ category
        → research/ _index.md lists ai/ branch
          → root _index.md lists everything
```

Every directory gets an auto-generated `_index.md` that:

1. Lists `.md` files grouped by frontmatter `type`
2. Links to subdirectory `_index.md` files, using their frontmatter `description`
3. Preserves any hand-written frontmatter fields

An LLM navigating this reads one file per level:

```
root/_index.md  →  research/  →  ai/  →  papers/  →  attention-is-all-you-need/  →  multi-head-attention.md
```

Each hop costs a few KB of context. No JSON parsing, no database queries.

### The `description` Field

The single most important field in any note's frontmatter:

```yaml
---
type: paper
title: "Attention Is All You Need"
era: 2017-06
description: "Vaswani et al. 2017 — The transformer architecture that revolutionized NLP. Introduced self-attention and removed recurrence entirely."
---
```

- **Short** — keep it under 200 characters (~20–35 tokens)
- **Factual** — nouns, attributes, relationships. Not prose.
- **Semantic** — captures what the note *is*, not its first paragraph

When `update_indexes` regenerates directory listings, it prefers this field over auto-extracted body text. The `description` field is optional — notes without one fall back to body extraction — but adding descriptions is the highest-leverage thing you can do for LLM navigability.

### The Buddy-Note Pattern (Binary Files)

PDFs, images, audio files, and other binaries are **invisible to LLMs**. Instead of trying to parse them (fragile, expensive, format-specific), create a `.md` "buddy note" that describes the binary:

```
attention.pdf     ← not committed. LLM can't read it.
attention.md      ← committed. Describes it for the LLM.
```

The buddy note carries the semantic weight:

```yaml
---
type: document
title: "Attention Is All You Need"
description: "Vaswani et al. 2017 — The transformer paper"
file: attention.pdf
---
```

The binary file is gitignored (see `sample-knowledge/.gitignore`). Only the `.md` notes enter version control. If you drop the actual PDF into the folder, DocWeave copies it to `.site/` for human browsing — but the LLM never touches it.

This works for **anything**: PDFs, images, MP3s, videos, datasets. Every binary gets a note that says what it is, who created it, when, and how it connects to other notes.

### What About 100K Files?

If your knowledge base grows to 100,000 notes, the graph addon and monolithic `index.json` become unwieldy. The answer: **split at a higher level.**

```
research/project.yaml     — one project per domain
ai/project.yaml
personal/project.yaml
```

Each sub-project is a self-contained knowledge base with its own graph, timeline, and indexes. An LLM can navigate between them via top-level `_index.md` files. This is the Unix philosophy applied to knowledge: small, focused projects that compose.

## Project Structure

```
├── bin/docweave           # CLI entry point
├── docweave/              # Python build engine
│   ├── __main__.py        #   5-step build pipeline
│   ├── config.py          #   project.yaml loading
│   ├── parser.py          #   Frontmatter, wikilinks, note parsing
│   ├── builder.py         #   Index building, backlinks, sidebar
│   ├── addons.py          #   Graph, timeline runners
│   ├── update_indexes.py  #   Auto-generate _index.md files
│   └── writer.py          #   index.json, attachments
├── renderer/              # HTML/CSS/JS site templates
│   ├── index.html         #   Wiki view (sidebar + notes)
│   ├── zettel.html        #   Graph view (D3.js)
│   └── style.css          #   Dark theme
├── sample-knowledge/      # Complete demo knowledge base
│   ├── project.yaml       #   Config — types, addons, index
│   ├── .gitignore         #   Binary file policy
│   └── .site/             #   Generated output (gitignored)
├── Makefile               # Build + serve shortcuts
└── README.md
```

On every build, the shared renderer files (from `renderer/`) are copied into `.site/` alongside `index.json`. The output is fully self-contained — zip it and host on any static server.

> 💡 **Edit the renderer?** Change files in `renderer/`, then run `make build` to sync them into `.site/`.

## Configuration: project.yaml

A single file defines everything — types, icons, addons, index behavior:

```yaml
project:
  name: "My Knowledge Base"

types:
  person:
    icon: "👤"
    color: "#4a90d9"
    label: "Person"
  paper:
    icon: "📄"
    color: "#d9a04a"
    label: "Paper"
  concept:
    icon: "💡"
    color: "#a04ad9"
    label: "Concept"

index:
  entity_fields: [people, topics]
  name_fields: [people]
  topic_fields: [topics]

addons:
  graph:
    enabled: true
  timeline:
    field: era
    format: era
  update_indexes:
    enabled: true
```

The `index:` section configures how the pi coding assistant extension reads your knowledge base — fields for graph entities, searchable names, and topic categorization. Every tool reads from `project.yaml`.

## Addons

### graph (post-scan)

D3.js force-directed graph — every note is a node, every `[[wikilink]]` is an edge. Type filtering, search, and preview included.

```yaml
addons:
  graph:
    enabled: true
```

In sample-knowledge, the graph shows connections between papers, their atomic concepts, and the docweave project documentation.

---

### timeline (post-scan)

Chronological view from any date field. Two formats:

**`format: iso`** — precise dates (birth years, project milestones)

```yaml
addons:
  timeline:
    field: era
    format: iso
```

Renders Samuel Johnson (1709) → Attention paper (2017) → Hardcore History episode (2014) on a human-readable timeline.

**`format: era`** — fuzzy or ancient dates (`~500 BCE`, `~1919 CE`, `~700–900 CE`)

The origin legend of the **Birman** breed — the story of High Priest Mun-Ha and the sacred temple cats — is set in the pre-Buddhist era (~500 BCE). The first European import arrived ~1919 CE. The timeline addon parses era strings, handles BCE/CE sorting, and unpacks ranges like `~1919–1925 CE`.

```yaml
addons:
  timeline:
    field: era
    format: era
```

---

### update_indexes (pre-scan)

Auto-generates `_index.md` files on every build. Creates directory listings, propagates descriptions upward, and preserves hand-written frontmatter. Every project in this repo uses it.

## Link Validation

DocWeave includes a link validator (pi extension at `.pi/extensions/docweave-link-validator.ts`) that scans for broken wikilinks, orphaned notes, and duplicate slugs.

In the pi coding assistant:

```
Check for broken links
```

Or from the command line:

```
/validate-links --check summary
/validate-links --check wikilinks
/validate-links --check orphans
/validate-links --check duplicates
```

## Design Philosophy

**The schema is the template.** A new project requires no code — just `project.yaml` and content files. The build pipeline reads your schema, parses every note, resolves links, and generates both a browsable wiki and structured JSON — all from one config file.

**Two audiences, one source.** Humans get type badges, graph views, timelines, and backlinks. LLMs get structured frontmatter, short semantic descriptions, propagated directory indexes, and a machine-readable JSON export. Both come from the same markdown files.

**Flat files, static output.** Plain markdown with YAML frontmatter. No database, no runtime, no lock-in. The output is a directory of static files you can zip and host anywhere.

**Propagation over flat search.** Instead of a single monolithic search index, DocWeave builds hierarchical directory summaries. An LLM navigates from broad descriptions to specific notes in logarithmic time — reading one small file per level instead of parsing a giant index.

**Composition over scale.** When a project grows beyond a single graph/timeline, split it into sub-projects. Each sub-project is its own knowledge base, and the top-level `_index.md` files act as a navigation layer between them.

## Tech Stack

- **Build:** Python + PyYAML
- **Render:** Vanilla HTML + CSS + JavaScript
- **Graph:** D3.js v7 (CDN)
- **Markdown:** marked.js (CDN)
- **Editor:** Pi coding assistant extensions (TypeScript)