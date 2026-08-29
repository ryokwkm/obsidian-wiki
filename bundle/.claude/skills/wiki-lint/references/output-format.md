# Wiki Health Report — output format

The template for a `--check` (report-only) run. One section per lint check, in check order.
**Omit a section whose check found nothing** — a report of sixteen "0 found" headings is
skipped wholesale by the agent that reads it at session start.

Counts here must be the ones from Check 0's script output, not hand-recounted.

```markdown
## Wiki Health Report

### Orphaned Pages (N found)
- `concepts/foo.md` — no incoming and no outgoing links

### Broken Links (N found)
- `entities/bar.md` — links to [[nonexistent-page]]

### Ambiguous Links (N found)
- `project-a/a.md` — `build-spec` matches 2 pages; qualify with the directory

### Missing Frontmatter (N found)
- `skills/baz.md` — missing: tags, sources

### Missing Summary (N found — soft)
- `concepts/foo.md` — no `summary:` field
- `entities/bar.md` — summary exceeds 200 chars

### Stale Content (N found)
- `references/paper-x.md` — source modified 2024-03-10, page last updated 2024-01-05

### Contradictions (N found)
- `concepts/scaling.md` claims "X" but `synthesis/efficiency.md` claims "not X"

### Index Issues (N found)
- `concepts/new-page.md` exists on disk but not in index.md

### Provenance Issues (N found)
- `concepts/scaling.md` — AMBIGUOUS > 15%: 22% of claims are ambiguous (re-source or move to synthesis/)
- `entities/some-tool.md` — drift: frontmatter says inferred=0.10, recomputed=0.45
- `concepts/transformers.md` — hub page (31 incoming links) with INFERRED=28%: errors here propagate widely
- `synthesis/speculation.md` — unsourced synthesis: no `sources:` field, 55% inferred

### Fragmented Tag Clusters (N found)
- **#systems** — 7 pages, cohesion=0.06 ⚠️
- **#databases** — 5 pages, cohesion=0.10 ⚠️

### Over-Tagged and Malformed Tags (N pages / M tags)
- 27 pages carry more than 5 non-`visibility/` tags — 26 at 6, 1 at 7 (unchanged since the last run)
- `concepts/platform-overview.md` — 7 tags
- `skills/test-account-login.md` — 6 tags
- `skills/quality-verification-procedure.md` — 6 tags
- `skills/admin-panel-patterns.md` — 6 tags
- `skills/proxy-app-integration.md` — 6 tags
- tag `my_project` is not lowercase-and-hyphen (underscore) — on 2 pages

### Visibility Issues (N found)
- `entities/user-records.md` — contains `email:` value pattern but no `visibility/pii` tag
- `concepts/auth-flow.md` — tagged `visibility/pii` but missing `sources:` frontmatter

### Misc Promotion Candidates (N found)
Only when the vault has `misc/*.md`; omit the whole section otherwise.

| Page | Top Project | Affinity Score |
|---|---|---|
| `misc/web-martinfowler-articles-microservices.md` | `obsidian-wiki` | 4 |

### Synthesis Gaps (N found)
Concept pairs that co-occur frequently but have no synthesis page:

| Pair | Co-occurrence | Suggested Action |
|---|---|---|
| [[Caching]] × [[Consistency]] | 5 pages | Write a `synthesis/` page |
| [[Testing]] × [[Observability]] | 3 pages | Write a `synthesis/` page |

### Confidence/Lifecycle Issues (N found)
- 66 pages carry the pre-rubric value `lifecycle: active` — convert per `~/.claude/doc/doc_wiki_lifecycle_rubric.md`
- `concepts/foo.md` — missing `lifecycle` field
- `entities/bar.md` — `lifecycle: stalestate` is not in the allowed set
- `concepts/scaling.md` — `base_confidence: 1.4` is out of range [0.0, 1.0]
- `project-a/spec.md` — `lifecycle: tested` but no `evidence_at` (Rule 12f)
- `concepts/bar.md` — `lifecycle: sourced`, `lifecycle_evidence: "§3 の実装表"` — that section is gone (Rule 12f)
- `concepts/heuristic.md` — `lifecycle: tested` but the body has no command output or sample size (Rule 12f, heuristic)
- `synthesis/old-analysis.md` — STALE (evidence_at 2025-10-01, 182 days) lifecycle=verified ⚠️ HIGH PRIORITY
- `concepts/pipeline.md` — STALE (updated 2025-11-15, 137 days) lifecycle=index
- `entities/tool-v1.md` — `superseded_by: [[entities/tool-v2]]` but lifecycle=sourced (expected archived)
- `concepts/drift-example.md` — base_confidence drift: stored=0.80, recomputed=0.59 (delta=0.21)

### Typed Relationship Issues (N found)
- `concepts/foo.md` — relationships[1]: type "contradication" is not an allowed type (did you mean "contradicts"?)
- `concepts/bar.md` — relationships[0]: target "[[skills/nonexistent-skill]]" resolves to no page in vault
- `entities/baz.md` — relationships[2]: self-reference (target resolves to this page's own id)
```

The over-tag backlog and legacy-lifecycle findings are reported as counts, never one
finding per page — the rules are in SKILL.md (Check 8a and Rule 12a); the sample lines
above show the shape.
