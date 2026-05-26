# DocWeave — LLM Wiki Generator

**DocWeave** turns markdown notes with YAML frontmatter into two things:

1. A **browsable static wiki** — type badges, graph view, timeline, backlinks, search
2. A **machine-ready knowledge base** — structured `index.json`, auto-generated directory indexes, and short semantic descriptions in every note's frontmatter

All driven by a single `project.yaml` schema. No templates, no code per project.

You write notes. DocWeave builds a wiki for humans *and* an ingestible dataset for LLMs.

## Demo

The **[sample-cats/](sample-cats/)** directory is a complete demo: a wiki for a cat breeding family with two entity types (`cat` and `litter`), cross-references, timeline, and a graph view.

Open `sample-cats/cats/esbeth.md` to see the frontmatter pattern:

```yaml
---
type: cat
sex: female
color: chocolate point
title: Junior Champion
born: "2022"
children: [Bert, Bella, Bia]
description: "Chocolate point female, Junior Champion, dam of Bert, Bella, and Bia"
---
```

That `description` field — short, factual, machine-friendly — is what makes every note LLM-ready.

## Quick Start

```bash
# Build the sample-cats site
cd sample-cats
../bin/docweave

# Serve it locally
python3 -m http.server -d .site
# → Open http://localhost:8000
```

Or use `make` from the root:

```bash
make build    # Build sample-cats
make serve    # Build + serve on :8000
```

## How It Works

A `project.yaml` file defines your data model. Here's the demo schema:

```yaml
# project.yaml
types:
  cat:
    icon: "🐱"
    color: "#e67e22"
    label: "Cat"
    fields:
      born:     { label: "Born", type: date }
      color:    { label: "Color" }
      parents:  { label: "Parents" }
```

The build pipeline reads this schema, parses all markdown files, resolves `[[wikilinks]]`, builds backlinks, and generates `index.json` — a structured export of every note, its frontmatter, its `description`, its outgoing and incoming links, and its attachments. The static HTML/JS renderer then adapts everything — type badges, field pills, dates, timeline nav, graph colors — from that schema at runtime.

## Features

| Feature | Description |
|---|---|
| **LLM-ready frontmatter** | Every note has a short `description` field for quick AI ingestion |
| **Auto-generated indexes** | `_index.md` files built from frontmatter descriptions, not body heuristics |
| **Structured JSON export** | `index.json` with all notes, types, links, and metadata |
| **Schema-driven** | Types, field roles (tag vs. date), icons, colors — all in one YAML file |
| **Wikilinks** | `[[note-title]]` and `[[path/to/note\|display text]]` with backlink resolution |
| **Backlinks** | Automatic inbound-link tracking for every note |
| **Graph view** | D3.js force-directed graph with type filtering, search, and preview |
| **Timeline addon** | Chronological navigation from any `type: date` field |
| **Attachments** | Binary files (PDFs, images) beside `_index.md` auto-discovered and copied |
| **Search** | Full-text search across titles, bodies, and all frontmatter fields |
| **Link validation** | Built-in tool for broken wikilinks, orphans, and duplicate slugs |

## The `description` Field

Every note can carry a short `description` in its YAML frontmatter. This is the **single most important thing** that makes DocWeave LLM-friendly:

```yaml
---
type: character
description: "Elven ranger, captain of the northern guard, carries the Starwood Bow"
---
```

- **Short** — keep it under 200 characters. That's ~20-35 tokens, trivial for an LLM context window.
- **Factual** — nouns, attributes, relationships. Not prose.
- **Semantic** — captures what the note *is*, not just its first paragraph.

When `update_indexes` regenerates directory indexes, it prefers this field over auto-extracted body text. For a project with 100,000 notes, this means reading only the frontmatter (first ~20 lines) instead of every file's full body — a **10–50x reduction** in I/O.

### With or without

The `description` field is optional. Notes without one fall back to the old heuristic (first substantive paragraph). But for any project that aims to be LLM-consumable, adding short descriptions is the highest-leverage thing you can do.

## Auto-Generated Indexes

When enabled, DocWeave regenerates `_index.md` files on every build — one per content directory. Each index:

1. Lists `.md` files grouped by frontmatter `type`
2. Uses each note's `description` field (falls back to auto-extracted first paragraph)
3. Links to subdirectory `_index.md` files
4. Preserves existing frontmatter, intro text, and `## See Also` / `## Related` sections

```yaml
# project.yaml
addons:
  update_indexes:
    enabled: true
```

This means your directory listings are **always fresh** — add a note, rebuild, and the index picks it up. No manual updating.

For LLM consumption, the generated `_index.md` files serve as lightweight table-of-contents summaries. An LLM can read one per context window and understand the full shape of a directory.

## Project Structure

```
├── .pi/                   # Pi coding assistant config
│   ├── settings.json      #   Project settings (points to project.yaml)
│   └── extensions/        #   Custom tools
│       └── docweave-link-validator.ts
├── bin/docweave           # CLI entry point (executable)
├── docweave/              # Python package — the build engine
│   ├── __init__.py        #   Package init
│   ├── __main__.py        #   Entry: python3 -m docweave
│   ├── config.py          #   project.yaml loading & validation
│   ├── parser.py          #   Frontmatter, wikilinks, note parsing
│   ├── builder.py         #   Index building, backlinks, sidebar
│   ├── addons.py          #   Timeline and future addons (post-scan)
│   ├── update_indexes.py  #   Auto-generate _index.md files (pre-scan)
│   └── writer.py          #   JSON output, renderer & attachment copy
├── renderer/              # Source: shared HTML/CSS/JS renderer files
│   ├── index.html         #   Wiki view (sidebar + note content)
│   ├── zettel.html        #   Graph view (D3.js force layout)
│   └── style.css          #   Dark theme
├── sample-cats/           # Demo project
│   ├── project.yaml       #   Schema definition
│   ├── cats/              #   Notes of type "cat"
│   ├── litters/           #   Notes of type "litter"
│   └── .site/             #   Generated output (gitignored)
├── Makefile               # Build and serve shortcuts
└── README.md
```

On every build, the shared renderer files (from `renderer/`) are copied into `.site/` alongside `index.json`. The output is fully self-contained — zip it and host on any static server.

> 💡 **Edit the renderer?** Change files in `renderer/`, then run `make build` to sync them into `.site/`.

## Addons

DocWeave supports two kinds of addons: **pre-scan** (run before notes are parsed) and **post-scan** (run after the index is built). Enable them in `project.yaml` under the `addons` key.

### graph (post-scan)

Enables the D3.js force-directed graph view — every note is a node, every `[[wikilink]]` is an edge.

```yaml
addons:
  graph:
    enabled: true
```

In **[sample-cats](sample-cats/)** (13 notes), the graph shows a tight family tree of cats and litters — parents, kittens, bloodlines. Every `[[wikilink]]` between a cat and its litter becomes an edge. The same pattern scales: a breed registry with thousands of entries becomes an explorable pedigree network.

---

### timeline (post-scan)

Builds a chronological timeline from any date field. Two formats available, depending on your project:

**`format: iso`** — for precise, modern dates (birth years, historical records, project milestones)

```yaml
# sample-cats/project.yaml  —  cat breeding records
addons:
  timeline:
    field: born
    format: iso
```

Each cat's `born: "2022"` becomes a point on the timeline. Result: a chronological view of the breeding program.

**`format: era`** — for fuzzy or ancient dates (`~500 BCE`, `~1919 CE`, `~700–900 CE`)

```yaml
# Birman breed registry —  temple cat history
addons:
  timeline:
    field: era
    format: era
```

The origin legend of the **Birman** breed — the story of High Priest Mun-Ha and the sacred temple cats of Myanmar — is set in the pre-Buddhist era. Notes carry dates like `era: ~500 BCE`:

> **The Legend of Mun-Ha (~500 BCE)** → **First European Import (~1919 CE)**

The addon parses era strings, handles BCE/CE sorting, and even unpacks ranges like `~1919–1925 CE`. The timeline renders oldest-first on the page, regardless of format.

---

### update_indexes (pre-scan)

Auto-generates `_index.md` files. See the [Auto-Generated Indexes](#auto-generated-indexes) section above. Every project in this repo uses it — including the one you're reading.

## Adding a New Project

1. Copy the `sample-cats/` directory or start fresh
2. Edit `project.yaml` with your own types and fields
3. Write markdown notes with YAML frontmatter (each needs `type:` and, ideally, `description:`)
4. Run `../bin/docweave` from your project directory

## Link Validation

DocWeave includes a link validator (pi extension at `.pi/extensions/docweave-link-validator.ts`) that scans all markdown files for broken wikilinks, orphaned notes, and duplicate slugs.

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

## Tech Stack

- **Build:** Python + PyYAML (stdlib except `yaml`)
- **Render:** Vanilla HTML + CSS + JavaScript
- **Graph:** D3.js v7 (loaded from CDN)
- **Markdown:** marked.js (loaded from CDN)

## Design Philosophy

**The schema is the template.** A new project type requires no code — just a `project.yaml` and content files. The build pipeline reads your schema, parses every note, resolves links, and generates both a browsable wiki and a structured JSON index — all from one config file.

**Designed for two audiences.** Humans get type badges, graph views, timelines, and backlinks. LLMs get structured frontmatter, short semantic descriptions, auto-generated directory indexes, and a machine-readable JSON export. Both come from the same markdown files — no duplication.

**Flat files, static output.** Everything is plain markdown with YAML frontmatter. No database, no server-side runtime, no lock-in. The output is a directory of static files you can host anywhere.

**Performance is a feature.** The `description` frontmatter field means index regeneration can skip full-body parsing. For projects with 100,000 notes, the difference between reading the first 20 lines and the full 200+ lines per file is the difference between seconds and minutes. The architecture scales to large knowledge bases without exotic infrastructure.

> A wiki should be useful to people *and* machines. DocWeave gives you both, from the same markdown files.