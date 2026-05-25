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
│   ├── addons.py          #   Timeline and future addons
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