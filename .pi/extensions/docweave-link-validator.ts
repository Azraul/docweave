// ──── docweave-link-validator.ts ───────────────────────────────────
// Pi extension — validates link health for DocWeave projects.
//
// Checks:
//   1. Broken wikilinks  — [[links]] that resolve to no file
//   2. Orphaned notes    — .md files with no incoming wikilinks
//   3. Duplicate slugs   — same slug in multiple files
//
// DocWeave slug conventions:
//   - _index.md → slug = directory name (e.g. "cats/_index.md" → "cats")
//   - Regular .md → slug = path minus .md (e.g. "cats/bella.md" → "cats/bella")
//   - Wikilinks: [[slug]] or [[slug|display]]
//
// CLI: pi /validate-links [--check type] [--page N]

import type { ExtensionAPI, AgentToolResult } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import fs from "node:fs";
import path from "node:path";

// ──── Types ────────────────────────────────────────────────────────

interface ProjectConfig {
  project: Record<string, unknown>;
  types: Record<string, { label?: string; icon?: string; color?: string; fields?: Record<string, unknown> }>;
  build?: { content_dir?: string; exclude_dirs?: string[]; ignore?: string[] };
}

interface NoteMeta {
  slug: string;
  relPath: string;
  type: string | null;
  linksOut: string[];
  isIndex: boolean;
}

interface BrokenLink {
  sourceFile: string;
  line: number;
  rawTarget: string;
  displayText: string | null;
  suggestion: string | null;
}

interface OrphanNote {
  file: string;
  type: string | null;
}

interface DuplicateSlug {
  slug: string;
  files: string[];
}

interface ValidationIssues {
  brokenLinks: BrokenLink[];
  orphans: OrphanNote[];
  duplicates: DuplicateSlug[];
}

// ──── Constants ────────────────────────────────────────────────────

const FRONTMATTER_RE = /^---\n[\s\S]*?\n---\n?/;
const WIKILINK_RE = /\[\[([^\[\]]+?)(?:\|([^\[\]]*?))?\]\]/g;
const ROOT_META = new Set(["readme.md", "index.md", "license.md", "contributing.md", "plan.md"]);

// ──── Helpers ──────────────────────────────────────────────────────

function parseFrontmatter(text: string): Record<string, unknown> | null {
  const m = text.match(/^---\n([\s\S]*?)\n---/);
  if (!m) return null;
  const out: Record<string, unknown> = {};
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^(\w+):\s*(.+)/);
    if (!kv) continue;
    const [, key, raw] = kv;
    const val = raw.trim();
    if (val.startsWith("[") && val.endsWith("]")) {
      out[key] = val
        .slice(1, -1)
        .split(",")
        .map((s) => s.trim().replace(/^["']|["']$/g, ""))
        .filter(Boolean);
    } else {
      out[key] = val.replace(/^["']|["']$/g, "");
    }
  }
  return out;
}

function stripFrontmatter(text: string): string {
  return text.replace(FRONTMATTER_RE, "").trim();
}

/** Compute a DocWeave slug from a file's relative path. */
function slugFromPath(relPath: string): string {
  const normalised = relPath.replace(/\\/g, "/");
  if (normalised.endsWith("_index.md")) {
    const dir = path.dirname(normalised);
    return dir === "." ? normalised.replace("_index.md", "").replace(/\/$/, "") : dir;
  }
  return normalised.replace(/\.md$/, "");
}

/** Load project.yaml from the given directory. */
function loadProjectConfig(projectRoot: string): ProjectConfig | null {
  const yamlPath = path.join(projectRoot, "project.yaml");
  if (!fs.existsSync(yamlPath)) return null;

  // Minimal YAML parser — just enough for project.yaml structure
  const text = fs.readFileSync(yamlPath, "utf-8");
  const result: ProjectConfig = { project: {}, types: {} };
  let currentSection = "";
  let currentType = "";

  for (const line of text.split("\n")) {
    const sectionMatch = line.match(/^(\w+):/);
    if (sectionMatch && !line.startsWith(" ") && !line.startsWith("\t")) {
      currentSection = sectionMatch[1];
      currentType = "";
    }

    if (currentSection === "project") {
      const kv = line.match(/^\s{2}(\w+):\s*(.+)/);
      if (kv) result.project[kv[1]] = kv[2]?.replace(/^["']|["']$/g, "") ?? "";
    }

    if (currentSection === "types") {
      const typeMatch = line.match(/^\s{2}(\w+):/);
      if (typeMatch) {
        currentType = typeMatch[1];
        result.types[currentType] = {};
      }
      if (currentType) {
        const kv = line.match(/^\s{4}(\w+):\s*(.+)/);
        if (kv) {
          const val = kv[2].replace(/^["']|["']$/g, "");
          if (kv[1] === "fields") {
            result.types[currentType].fields = {};
          } else {
            (result.types[currentType] as Record<string, unknown>)[kv[1]] = val;
          }
        }
      }
    }
  }

  return result.project?.name ? result : null;
}

// ──── Slug Map Building ────────────────────────────────────────────

/** Build a case-insensitive slug → files map from all indexed notes. */
function buildSlugMap(notes: NoteMeta[]): Map<string, string[]> {
  const map = new Map<string, string[]>();
  for (const note of notes) {
    const key = note.slug.toLowerCase();
    const existing = map.get(key);
    if (existing) existing.push(note.relPath);
    else map.set(key, [note.relPath]);

    // Also index by basename for bare-slug lookups: "cats/bella" → "bella"
    const base = note.slug.split("/").pop()?.toLowerCase();
    if (base && base !== key) {
      const baseExisting = map.get(base);
      if (baseExisting) baseExisting.push(note.relPath);
      else map.set(base, [note.relPath]);
    }
  }
  return map;
}

/** Suggest a likely-correct slug for an unresolvable target. */
function suggestTarget(bare: string, slugMap: Map<string, string[]>): string | null {
  const hits = slugMap.get(bare.toLowerCase());
  if (!hits) return null;
  return hits.join(" or ");
}

// ──── Wikilink Resolution ──────────────────────────────────────────

function resolveWikilink(
  normalized: string,
  notesMap: Map<string, NoteMeta>,
  slugMap: Map<string, string[]>,
  projectRoot: string,
): { resolved: boolean; files: string[]; suggestion: string | null } {
  // Direct slug match
  if (notesMap.has(normalized)) {
    return { resolved: true, files: [notesMap.get(normalized)!.relPath], suggestion: null };
  }

  // Full path as written: "cats/bella" → cats/bella.md
  const asFile = normalized + ".md";
  if (fs.existsSync(path.join(projectRoot, asFile))) {
    const slug = slugFromPath(asFile);
    if (notesMap.has(slug)) {
      return { resolved: true, files: [notesMap.get(slug)!.relPath], suggestion: null };
    }
  }

  // Folder note: "cats" might be "cats/_index.md"
  const asIndex = path.join(normalized, "_index.md");
  if (fs.existsSync(path.join(projectRoot, asIndex))) {
    const slug = slugFromPath(asIndex);
    if (notesMap.has(slug)) {
      return { resolved: true, files: [notesMap.get(slug)!.relPath], suggestion: null };
    }
  }

  // Case-insensitive slug lookup
  const hits = slugMap.get(normalized.toLowerCase());
  if (hits && hits.length > 0) {
    return { resolved: true, files: hits, suggestion: null };
  }

  return { resolved: false, files: [], suggestion: suggestTarget(normalized, slugMap) };
}

// ──── Scanning ─────────────────────────────────────────────────────

function walkMarkdownFiles(root: string, excludeDirs: Set<string>): string[] {
  const files: string[] = [];
  let entries: fs.Dirent[];
  try {
    entries = fs.readdirSync(root, { withFileTypes: true });
  } catch {
    return files;
  }

  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (entry.name.startsWith(".") || excludeDirs.has(entry.name)) continue;
      // Also skip common generated dirs
      if (entry.name === ".site") continue;
      files.push(...walkMarkdownFiles(path.join(root, entry.name), excludeDirs));
    } else if (entry.name.endsWith(".md")) {
      files.push(path.join(root, entry.name));
    }
  }
  return files;
}

function scanProject(projectRoot: string): {
  notes: NoteMeta[];
  allFiles: string[];
} {
  const config = loadProjectConfig(projectRoot);
  const contentDir = config?.build?.content_dir ?? ".";
  const excludeDirs = new Set(config?.build?.exclude_dirs ?? [".pi", ".git"]);

  const absContent = path.join(projectRoot, contentDir);
  const rawFiles = walkMarkdownFiles(absContent, excludeDirs);

  const notes: NoteMeta[] = [];
  const allFiles: string[] = [];

  for (const absPath of rawFiles) {
    const relPath = path.relative(projectRoot, absPath);
    allFiles.push(relPath);

    const content = fs.readFileSync(absPath, "utf-8");
    const fm = parseFrontmatter(content);
    const body = stripFrontmatter(content);

    const slug = slugFromPath(relPath);
    const noteType = fm && typeof fm.type === "string" ? fm.type : null;

    // Extract wikilinks
    const linksOut: string[] = [];
    WIKILINK_RE.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = WIKILINK_RE.exec(body)) !== null) {
      const raw = match[1].trim();
      if (raw.startsWith("http://") || raw.startsWith("https://")) continue;
      linksOut.push(raw.replace(/\.md$/i, "").trim());
    }

    notes.push({
      slug,
      relPath,
      type: noteType,
      linksOut,
      isIndex: relPath.endsWith("_index.md"),
    });
  }

  return { notes, allFiles };
}

// ──── Validation ───────────────────────────────────────────────────

function runValidation(projectRoot: string): ValidationIssues {
  const { notes, allFiles } = scanProject(projectRoot);

  // Build lookup maps
  const notesMap = new Map<string, NoteMeta>();
  for (const note of notes) {
    notesMap.set(note.slug, note);
  }
  const slugMap = buildSlugMap(notes);

  // 1. Broken wikilinks
  const brokenLinks: BrokenLink[] = [];
  const referencedFiles = new Set<string>();

  for (const note of notes) {
    const absPath = path.join(projectRoot, note.relPath);
    const content = fs.readFileSync(absPath, "utf-8");
    const body = stripFrontmatter(content);
    const lines = body.split("\n");

    for (let i = 0; i < lines.length; i++) {
      WIKILINK_RE.lastIndex = 0;
      let match: RegExpExecArray | null;
      while ((match = WIKILINK_RE.exec(lines[i])) !== null) {
        const rawTarget = match[1].trim();
        const displayText = match[2]?.trim() ?? null;
        if (rawTarget.startsWith("http://") || rawTarget.startsWith("https://")) continue;

        const normalized = rawTarget.replace(/\.md$/i, "").trim();
        const result = resolveWikilink(normalized, notesMap, slugMap, projectRoot);

        if (result.resolved) {
          result.files.forEach((f) => referencedFiles.add(f));
        } else {
          brokenLinks.push({
            sourceFile: note.relPath,
            line: i + 1,
            rawTarget,
            displayText,
            suggestion: result.suggestion,
          });
        }
      }
    }
  }

  // 2. Orphaned notes (files with no incoming links and not root meta-files)
  const orphans: OrphanNote[] = [];
  for (const note of notes) {
    const basename = path.basename(note.relPath).toLowerCase();
    const isRoot = !note.relPath.includes("/");
    if (isRoot && ROOT_META.has(basename)) continue;

    if (!referencedFiles.has(note.relPath)) {
      orphans.push({ file: note.relPath, type: note.type });
    }
  }

  // 3. Duplicate slugs
  const slugCounts = new Map<string, string[]>();
  for (const note of notes) {
    const existing = slugCounts.get(note.slug) ?? [];
    existing.push(note.relPath);
    slugCounts.set(note.slug, existing);
  }
  const duplicates: DuplicateSlug[] = [];
  for (const [slug, files] of slugCounts) {
    if (files.length > 1) duplicates.push({ slug, files });
  }

  return { brokenLinks, orphans, duplicates };
}

// ──── Formatting ───────────────────────────────────────────────────

function formatSummary(issues: ValidationIssues): string {
  const total = issues.brokenLinks.length + issues.orphans.length + issues.duplicates.length;
  const lines = [
    "## Link Validation — Summary\n",
    `- Broken wikilinks: ${issues.brokenLinks.length}`,
    `- Orphaned notes:   ${issues.orphans.length}`,
    `- Duplicate slugs:  ${issues.duplicates.length}`,
    `- Total issues:     ${total}`,
    "",
    total === 0
      ? "✅ No issues found."
      : 'Run with check="wikilinks", "orphans", or "duplicates" to see details.',
  ];
  return lines.join("\n");
}

function formatDetail(
  issues: ValidationIssues,
  check: string,
  page: number,
  pageSize: number,
): string {
  const items: { category: string; severity: number; text: string }[] = [];

  if (check === "wikilinks" || check === "all") {
    for (const bl of issues.brokenLinks) {
      const s = bl.suggestion ? `\n     💡 Did you mean [[${bl.suggestion}]]?` : "";
      items.push({
        category: "broken wikilink",
        severity: 3,
        text: `${bl.sourceFile}:[[${bl.rawTarget}]]\n     Line ${bl.line}: "${bl.displayText || bl.rawTarget}"${s}`,
      });
    }
  }

  if (check === "orphans" || check === "all") {
    for (const o of issues.orphans) {
      const tag = o.type ? ` (${o.type})` : "";
      items.push({
        category: "orphan",
        severity: 2,
        text: `${o.file}${tag}`,
      });
    }
  }

  if (check === "duplicates" || check === "all") {
    for (const d of issues.duplicates) {
      items.push({
        category: "duplicate slug",
        severity: 1,
        text: `"${d.slug}" appears in:\n     ${d.files.map((f) => `  ${f}`).join("\n     ")}`,
      });
    }
  }

  items.sort((a, b) => b.severity - a.severity || a.category.localeCompare(b.category));

  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = page * pageSize;
  const slice = items.slice(start, start + pageSize);

  const header = `## Link Validation — ${check}\n\npage ${page + 1}/${totalPages} — showing ${slice.length} of ${total}`;
  const body = slice.map((item, i) => `  ${start + i + 1}. ${item.text}`).join("\n");
  const footer = totalPages > 1
    ? `\n\nCall again with page=${Math.min(page + 1, totalPages - 1)} for the next batch.`
    : "";

  return [header, "", body, footer].join("\n");
}

// ──── Extension Entry Point ────────────────────────────────────────

export default function (pi: ExtensionAPI) {
  // ── Helper: discover project root from cwd ────────────────
  function findProjectRoot(): string | null {
    let dir = process.cwd();
    for (let i = 0; i < 10; i++) {
      if (fs.existsSync(path.join(dir, "project.yaml"))) return dir;
      const parent = path.dirname(dir);
      if (parent === dir) return null;
      dir = parent;
    }
    return null;
  }

  // ── Tool (model-facing) ───────────────────────────────────
  pi.registerTool({
    name: "validate_links",
    label: "Validate Links",
    description:
      "Scan all notes in the DocWeave project for link health issues. " +
      "Reports broken wikilinks, orphaned notes, and duplicate slugs. " +
      "Results are paginated for iterative processing. " +
      "Run with check='summary' first to see counts, then drill into specific categories.",
    promptSnippet: "Validate link health across the DocWeave project",
    promptGuidelines: [
      "Use validate_links when the user asks to check for broken links, orphaned notes, " +
      "or duplicate slugs in a DocWeave project. Start with check='summary' to see counts, " +
      "then drill into specific check types.",
    ],

    parameters: Type.Object({
      check: Type.Optional(
        Type.String({
          description:
            "What to validate: 'summary' (counts only), 'wikilinks' (broken [[links]]), " +
            "'orphans' (files no one links to), 'duplicates' (same slug in multiple files), " +
            "or 'all' (everything paginated). Default: 'summary'.",
          default: "summary",
        }),
      ),
      page: Type.Optional(
        Type.Number({
          description: "Page number (0-indexed) for paginated results. Default: 0.",
          default: 0,
        }),
      ),
      pageSize: Type.Optional(
        Type.Number({
          description: "Results per page. Default: 10.",
          default: 10,
          minimum: 1,
          maximum: 100,
        }),
      ),
    }),

    async execute(
      _toolCallId,
      params,
      _signal,
      _onUpdate,
      _ctx,
    ): Promise<AgentToolResult<unknown>> {
      const projectRoot = findProjectRoot();
      if (!projectRoot) {
        return {
          content: [{ type: "text", text: "No project.yaml found in the current directory tree. Are you in a DocWeave project?" }],
          details: { error: "no_project" },
        };
      }

      const issues = runValidation(projectRoot);
      const check = params.check ?? "summary";
      const page = params.page ?? 0;
      const pageSize = params.pageSize ?? 10;

      if (check === "summary") {
        return {
          content: [{ type: "text", text: formatSummary(issues) }],
          details: {
            summary: {
              brokenLinks: issues.brokenLinks.length,
              orphans: issues.orphans.length,
              duplicates: issues.duplicates.length,
            },
          },
        };
      }

      const text = formatDetail(issues, check, page, pageSize);
      return {
        content: [{ type: "text", text }],
        details: {
          check,
          page,
          pageSize,
          summary: {
            brokenLinks: issues.brokenLinks.length,
            orphans: issues.orphans.length,
            duplicates: issues.duplicates.length,
          },
        },
      };
    },
  });

  // ── CLI Command ───────────────────────────────────────────
  pi.registerCommand("validate-links", {
    description:
      "Run link validation on the DocWeave project. " +
      "Args: --check <summary|wikilinks|orphans|duplicates|all> --page <N>",
    handler: async (args) => {
      const projectRoot = findProjectRoot();
      if (!projectRoot) {
        return { content: [{ type: "text", text: "No project.yaml found." }] };
      }

      const parsed: Record<string, string> = {};
      for (let i = 0; i < args.length; i++) {
        if (args[i].startsWith("--")) {
          const key = args[i].slice(2);
          const val = args[i + 1] && !args[i + 1].startsWith("--") ? args[i + 1] : "true";
          parsed[key] = val;
          if (val !== "true") i++;
        }
      }

      const check = parsed.check ?? "summary";
      const issues = runValidation(projectRoot);

      if (check === "summary") {
        return { content: [{ type: "text", text: formatSummary(issues) }] };
      }
      const page = parseInt(parsed.page ?? "0", 10) || 0;
      return { content: [{ type: "text", text: formatDetail(issues, check, page, 20) }] };
    },
  });
}
