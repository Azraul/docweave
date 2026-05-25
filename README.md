# DocWeave — Schema-Driven Documentation

**DocWeave** is a schema-driven static-site generator for personal wikis, knowledge bases, and documentation projects. It turns markdown notes with YAML frontmatter into a browsable wiki with backlinks, a force-directed graph view, timelines, and automatic attachment handling — all driven by a single YAML schema.

## How It Works

Instead of templates or hardcoded entity types, a `project.yaml` file defines your project's data model:

```yaml
# project.yaml
types:
  cat:
    icon: "🐱"
    color: "#e67e22"
    label: "Cat"
    fields:
      born:   { label: "Born", type: date }
      color:  { label: "Color" }
      parents:{ label: "Parents" }
```

The build pipeline reads this schema, parses all markdown files, resolves `[[wikilinks]]`, builds backlinks, and generates a JSON index. The static HTML/JS renderer then adapts everything — type badges, field pills, dates, timeline nav, graph colors — from that schema at runtime. No templates to create, no code to change per project.

## Demo

The **[sample-cats/](sample-cats/)** directory is a complete demo: a wiki for a cat breeding family, with two entity types (`cat` and `litter`), cross-references, timeline, and a graph view.

![graph-preview](/preview.png "Graph preview")

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

## Features

| Feature | Description |
|---|---|
| **Schema-driven** | Types, field roles (tag vs. date), icons, colors — all in one YAML file |
| **Wikilinks** | `[[note-title]]` and `[[path/to/note|display text]]` with backlink resolution |
| **Graph view** | D3.js force-directed graph with type filtering, search, and preview |
| **Timeline addon** | Chronological navigation from any date field |
| **Attachments** | Binary files (PDFs, images) beside `_index.md` auto-discovered and copied |
| **Type badges** | Icon + color-coded type labels, rendered from schema |
| **Search** | Full-text search across titles, bodies, and all frontmatter fields |

## Project Structure

```
├── .pi/                   # Pi coding assistant config
│   ├── settings.json     #   Project settings (points to project.yaml)
│   └── extensions/       #   Custom tools
│       └── docweave-link-validator.ts
├── bin/docweave           # CLI entry point (executable)
├── docweave/              # Python package — the build engine
│   ├── __init__.py        #   Package init
│   ├── __main__.py        #   Entry: `python3 -m docweave`
│   ├── config.py          #   project.yaml loading & validation
│   ├── parser.py          #   Frontmatter, wikilinks, note parsing
│   ├── builder.py         #   Index building, backlinks, sidebar
│   ├── addons.py          #   Timeline and future addons (post-scan)
│   ├── update_indexes.py  #   Auto-generate _index.md files (pre-scan)
│   └── writer.py          #   JSON output, renderer & attachment copy
├── renderer/             # ★ Source: shared HTML/CSS/JS renderer files
│   ├── index.html        #   Wiki view (sidebar + note content)
│   ├── zettel.html       #   Graph view (D3.js force layout)
│   └── style.css         #   Dark theme
├── sample-cats/          # Demo project — a cat breeder's wiki
│   ├── project.yaml      #   Schema definition (types, fields, addons)
│   ├── cats/             #   Notes of type "cat"
│   ├── litters/          #   Notes of type "litter"
│   └── .site/            # ★ Generated output (gitignored)
├── Makefile              # Build and serve shortcuts
├── plan.md               # Full design document
└── README.md
```

The `renderer/` directory contains the **source files** for the wiki and graph views. On every build, `bin/docweave` or `make build` copies them into each project's `.site/` directory alongside the generated `index.json`. This means `.site/` is fully self-contained — you could zip it and host it on any static server, no build tools needed.

> 💡 **Edit the renderer?** Change files in `renderer/`, then run `make build` to sync them into `.site/`.

## Addons

DocWeave supports two kinds of addons: **pre-scan** (run before notes are parsed) and **post-scan** (run after the index is built). Addons are enabled in `project.yaml` under the `addons` key.

### update\_indexes (pre-scan)

Auto-generates `_index.md` files in every content directory. For each directory it:

1. Lists all `.md` files, grouped by frontmatter `type`
2. Extracts the first substantive paragraph as a description (~200 chars)
3. Links to subdirectory `_index.md` files
4. Preserves existing frontmatter, intro text, and `## See Also` / `## Related` sections

```yaml
# project.yaml
addons:
  update_indexes:
    enabled: true
```

This is invaluable for large projects — adding a new note automatically updates its parent directory's index on the next build, so you never have stale directory listings.

### graph (post-scan)

Enables the D3.js force-directed graph view in the browser.

```yaml
addons:
  graph:
    enabled: true
```

### timeline (post-scan)

Builds a chronological timeline from a date field. Supports ISO dates (`format: iso`) and era strings like `~3500 BCE` (`format: era`).

```yaml
addons:
  timeline:
    field: born
    format: iso
```

Or for worldbuilding projects with BCE/CE dates:

```yaml
addons:
  timeline:
    field: era
    format: era
```

## Link Validation

DocWeave ships a **link validator** as a pi extension at `.pi/extensions/docweave-link-validator.ts`. It scans all markdown files and reports:

- **Broken wikilinks** — `[[slug]]` references that don't match any note
- **Orphaned notes** — files with no incoming links (ignores root meta-files like README)
- **Duplicate slugs** — the same slug used by multiple files

In the pi coding assistant, just ask:

```
Check for broken links
```

Or use the command directly:

```
/validate-links --check summary
/validate-links --check wikilinks
/validate-links --check orphans
/validate-links --check duplicates
```
> ⚡ **Quick preview**: run `make serve` from the project root, then open `http://localhost:8000`.

## Adding a New Project

1. Copy the `sample-cats/` directory or create a new one
2. Edit `project.yaml` with your own types and fields
3. Write markdown notes with YAML frontmatter (each needs a `type:` field)
4. Run `../bin/docweave` from your project directory

## Tech Stack

- **Build:** Python + PyYAML (stdlib except `yaml`)
- **Render:** Vanilla HTML + CSS + JavaScript
- **Graph:** D3.js v7 (loaded from CDN)
- **Markdown:** marked.js (loaded from CDN)

## Design Philosophy

> The schema *is* the template. A new project type requires no code — just a `project.yaml` and content files.