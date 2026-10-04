---
name: wiki-lint
description: Obsidian wiki の健全性を監査する（孤立ページ・壊れた wikilink・矛盾・陳腐化）。「wiki を掃除して」「何を直すべき」「ノートを監査して」「wiki のヘルスチェック」や英語の "audit my notes" / "wiki health check" と言われたときに使う。`--consolidate` で報告のみから「修復して報告」（dream cycle）へ切り替わり、dry-run とユーザーの確認を経て直す。
---

# Wiki Lint — Health Audit

You are performing a health check on an Obsidian wiki. Your goal is to find and fix structural issues that degrade the wiki's value over time.

**Before scanning anything:** follow the Retrieval Primitives table in `~/.claude/doc/doc_wiki_schema.md`. Prefer frontmatter-scoped greps and section-anchored reads over full-page reads. On a large vault, blindly reading every page to lint it is exactly what this framework is built to avoid.

## Before You Start

1. **Resolve the vault path** — use `$OBSIDIAN_VAULT_PATH` if it is already exported; otherwise walk up from CWD to `$HOME` looking for a `.env` that contains `OBSIDIAN_VAULT_PATH=` and take the first one. If neither exists, stop and tell the user to set `OBSIDIAN_VAULT_PATH` in `.claude/settings.json` (`env`), a shell rc, or direnv. Never fall back to a hard-coded path — one repo, one vault.
2. Take the page inventory from the Check 0 script rather than reading `index.md` whole (Check 6 compares `index.md` against it)
3. Read the tail of `log.md` for recent activity context — `grep '^- \[' "$OBSIDIAN_VAULT_PATH/log.md" | tail -30`. **Never read `log.md` whole**: it is append-only and unbounded (100 kB+ ≒ 25k tokens on an active vault). Grep for entry lines rather than plain `tail` — the file contains blank lines, so a raw `tail -N` returns fewer than N entries.

## Lint Checks

Run these checks in order; the deliverable is the single report described under Output Format.

### 0. Build the link graph — run this first

Checks 1, 2, 2a, 7, 11 and 13 all read the same graph. Build it once, with the script:

```bash
python3 ~/.claude/skills/wiki-lint/scripts/linkgraph.py "$OBSIDIAN_VAULT_PATH"
```

It prints orphans, broken links and ambiguous links. `--quiet` gives counts only;
`--json` adds the full graph. **The JSON is keyed by vault** — the script takes
`vault [vault ...]`, so the top level is `{"<basename of the path you passed>": {…}}`,
one key per argument, and everything else lives inside it: `stats`, `orphans`, `broken`,
`ambiguous`, `pages`, `edges` (`[{from, to}]`), `incoming` (how many pages link here,
0 included), `incoming_links` (raw count), `outgoing`, `links_to_excluded` and
`unreadable`. Unwrap that one level before reading any of them, e.g.
`… --json | python3 -c 'import json,sys; g=json.load(sys.stdin).popitem()[1]; print(len(g["edges"]))'`.
Do **not** reach for `jq '.edges | length'`: a top-level key that does not exist gives
`null | length` = `0`, so the check reports "nothing found" with no error at all.
Checks 7 and 11 need the `--json` form.

Two of those need action even though they are not findings:
- **`unreadable`** — files that could not be read (dangling symlink, permission). They are
  missing from the graph, so report them; do not silently treat them as absent.
- **`links_to_excluded`** — links into a directory that is excluded from the scan. The
  target exists, so this is not a broken link, but it is also not an edge. Worth a mention
  only if the count is large — it means a directory is being treated as both.

**Take the numbers from the script. Do not recount by hand, and do not "verify" a
finding by re-grepping — a grep that disagrees with the script is the grep being wrong.**

Counting links looks like a grep recipe but is not one: two link notations with *different*
resolution semantics, literal link syntax inside code examples, and same-named pages in
different directories. A hand pass gets a different answer each time (measured: the same
instructions produced 5 orphans on one vault and 87 on another).

**Fallback.** If `python3` is unavailable, follow `references/link-graph.md` and say in
the report that you used the manual fallback — it is known to disagree with the script.

### 1. Orphaned Pages

Pages the script lists under `orphans`: **no incoming links and no resolvable outgoing
links**. A page that links out is not an orphan — it is reachable when you walk the graph
backwards from anywhere it points.

**Before reporting, check the two common false positives:**
- **Empty file** (0 bytes). It also trips missing-frontmatter, missing-summary and
  lifecycle checks, so one empty file shows up as four findings. `qmd` does not index
  0-byte files either. Propose deleting it rather than filling it in.
- **A directory that is deliberately not wiki pages** (reports, one-off exports, raw
  source kept for reference). Add the directory to `.wikilintignore` at the vault root
  (one glob per line, `#` for comments) instead of cross-linking it. Directories starting
  with `_` are already excluded.

**How to fix a real orphan:**
- Identify which existing pages should link to it
- Add links in appropriate sections, in the notation that page already uses

### 2. Broken Links

Links the script lists under `broken`: the target does not resolve to any page.

**How to fix:**
- If the target was renamed, update the link
- If the target should exist, create it
- If the link is wrong, remove or correct it

### 2a. Ambiguous Links

Links the script lists under `ambiguous`: the target matches **more than one** page, so
there is no way to tell which one was meant. These are worse than broken links — nothing
looks wrong in the vault, and any tool that silently picks the first match attributes the
reference to the wrong page.

**How to fix:** qualify the link with its directory (`[[project-a/build-spec]]`
rather than `[[build-spec]]`), or rename one of the colliding pages.

### 3. Missing Frontmatter

Every page should have: title, category, tags, sources, created, updated.

**How to check:**
- Grep frontmatter blocks (scope to `^---` at file heads) instead of reading every page in full
- Flag pages missing required fields

**How to fix:**
- Add missing fields with reasonable defaults

Findings go in the `Missing Frontmatter` section (sample lines in `references/output-format.md`) and their total in `missing_frontmatter=N` on the `LINT` log entry.

### 3a. Missing Summary (soft warning)

Every page *should* have a `summary:` frontmatter field — 1–2 sentences, ≤200 chars. This is what cheap retrieval (e.g. `wiki-query`'s index-only mode) reads to avoid opening page bodies.

**How to check:**
- Grep frontmatter for `^summary:` across the vault
- Flag pages without it, **but as a soft warning, not an error** — older pages predating this field are fine; the check exists to nudge ingest skills into filling it on new writes.
- Also flag pages whose summary exceeds 200 chars: take them from `summary_over_limit` in the metrics script run (Check 7 — run it once and reuse the output). Do not count characters by hand.

**How to fix:**
- Re-ingest the page, or manually write a short summary (1–2 sentences of the page's content).

### 4. Stale Content

Pages whose `updated` timestamp is old relative to their sources.

**How to check:**
- Compare page `updated` timestamps to source file modification times
- Flag pages where sources have been modified after the page was last updated

### 5. Contradictions

Claims that conflict across pages.

**How to check:**
- This requires reading related pages and comparing claims
- Focus on pages that share tags or are heavily cross-referenced
- Look for phrases like "however", "in contrast", "despite" that may signal existing acknowledged contradictions vs. unacknowledged ones

**How to fix:**
- Add an "Open Questions" section noting the contradiction
- Reference both sources and their claims

### 6. Index Consistency

Verify `index.md` matches the actual page inventory.

**How to check:**
- Compare pages listed in `index.md` to actual files on disk
- Each entry must be the page's `summary:` verbatim, optionally followed by a `( #tag)` suffix. The metrics script run lists the entries that are not under `index.entry_not_verbatim` (`null` when the vault has no `index.md`) — do not compare by eye. An entry that grows past its summary is how `index.md` bloated twice before.
- When more than 3 entries are listed, report the count and 3 examples rather than every line.
- `index.entries` is how many entries the script could match to a page. If it is far below the page count, the script did not recognise the entry format — say so; an empty `entry_not_verbatim` then means "not checked", not "no issues".

**How to fix:** copy the page's `summary:` into the entry — never the other way. If the summary is over 200 chars, shorten the summary first (Check 3a).

Findings go in the `Index Issues` section (sample lines in `references/output-format.md`) and their total in `index_issues=N` on the `LINT` log entry.

### 7. Provenance Drift

Check whether pages are being honest about how much of their content is inferred vs extracted. The marker convention (`^[extracted]` / `^[inferred]` / `^[ambiguous]` — every claim carries one) and the optional `provenance:` frontmatter block are defined in `~/.claude/doc/doc_wiki_schema.md`.

**How to check:** take the fractions from the metrics script — do not count markers by hand (hand counts disagree with each other):

```bash
python3 ~/.claude/skills/wiki-lint/scripts/frontmatter_metrics.py "$OBSIDIAN_VAULT_PATH"
```

It prints JSON. Each entry under `pages` has `provenance` = `{extracted, inferred, ambiguous, n_markers, stored, drift_flag}` (`null` when the page has no marker). The denominator is the marker total, with markers inside code excluded. The same run feeds Check 3a (`summary_over_limit`), Check 6 (`index`), Check 8 (`clusters`) and Rule 12e (`base_confidence`), so run it once.

- Apply these thresholds:
  - **AMBIGUOUS > 15%**: flag as "speculation-heavy" — even 1-in-7 claims being genuinely uncertain is a signal the page needs tighter sourcing or should be moved to `synthesis/`
  - **INFERRED > 40% with no `sources:` in frontmatter**: flag as "unsourced synthesis" — the page is making connections but has nothing to cite
  - **Hub pages** (top 10 by incoming count — take these from the Check 0 graph, do not re-derive) with INFERRED > 40%: flag as "high-traffic page with questionable provenance" — errors on hub pages propagate to every page that links to them. 40%, not the upstream 20%: pages mark only part of their claims and the unmarked rest is mostly extracted, so a marker-total fraction runs about twice a per-claim one. On the reference vault 20% flagged 9 of 10 hubs; 40% flags the same 2 that 20% flagged when unmarked claims were counted as extracted
  - **Drift**: `drift_flag` is true — the stored `provenance:` block is more than 0.20 off the recomputed value in some field
- **Skip** pages with no `provenance:` frontmatter and no markers — treated as fully extracted by convention

**How to fix:**
- For ambiguous-heavy: re-ingest from sources, resolve the uncertain claims, or split speculative content into a `synthesis/` page
- For unsourced synthesis: add `sources:` to frontmatter or clearly label the page as synthesis
- For hub pages with INFERRED > 40%: prioritize for re-ingestion — errors here have the widest blast radius
- For drift: update the `provenance:` frontmatter to match the recomputed values

### 8. Fragmented Tag Clusters

Checks whether pages that share a tag are actually linked to each other. Tags imply a topic cluster; if those pages don't reference each other, the cluster is fragmented — knowledge islands that should be woven together.

**How to check:** read `clusters` from the Check 7 script run. It lists every tag on ≥ 5 pages with `n`, `linked_pairs` (pairs of pages in the group linked in either direction — a pair counts once) and `cohesion = linked_pairs / (n × (n−1) / 2)`. Flag any tag whose cohesion is below 0.15.

**How to fix:**
- Report the cluster with its cohesion score. Weaving it together means adding links between pages in the group — that is a body write, so do it deliberately: use the notation each page already uses, and add a few links per page rather than cross-linking every pair
- If a tag group is large (n > 15) and still fragmented, consider splitting it into more specific sub-tags

### 8a. Over-Tagged and Malformed Tags

The tag rules are in `~/.claude/doc/doc_wiki_schema.md`: **at most 5 tags per page**,
lowercase, hyphen-separated, reusing existing tags where possible. `visibility/` tags are a
reserved group and do **not** count toward the 5.

Nothing checks the limit at write time, so a vault that grew without audits carries a
backlog. The doc above is the only authority for the limit and the vocabulary.

**How to check:**
- Grep frontmatter for `^tags:` — handle **both** the inline `[a, b]` form and the
  block-list form (`tags:` followed by `- a` lines); pages here use both, and a regex that
  only knows one form silently reports a smaller number
- Drop `visibility/*` entries, then flag pages with **6 or more** remaining tags
- Separately flag tags that are not lowercase-and-hyphen — an uppercase letter, an
  underscore, or a space inside the tag

**Report counts plus the worst offenders, never one finding per page.** Dozens of
per-page findings push every other section out of the report, and the backlog predates
the check. The section is:
- one line with the count and the distribution (`27 pages over 5 tags — 26 at 6, 1 at 7`)
- the **top 5 by tag count**, worst first, as individual lines
- one line per malformed tag *name* (not per page), with how many pages carry it

**A count that stays flat is the expected state, not a finding.** What carries information
is the delta against the previous `over_tagged=` in `log.md`: a count that grew means a
write path added tags past the limit, and that is worth naming in the report.

**How to fix:** n/a for `--fix`. Which tag to drop is decided by what the page is about and
lint does not read page bodies, so deleting the sixth tag removes whichever one happens to
sort last. Renaming a malformed tag means rewriting every page that carries it — a
vault-wide write. Surface both for the user, or for the next skill that opens the page with
its body in context.

Findings go in the `Over-Tagged and Malformed Tags` section (sample lines in
`references/output-format.md`) and their totals in two keys on the `LINT` log entry:
`over_tagged=N` (pages over the limit) and `malformed_tags=N` (distinct tag names, not
pages). Two units, two keys — folding them into one makes the delta unreadable.

### 9. Visibility Tag Consistency

Checks that `visibility/` tags are applied correctly and aren't silently missing where they matter.

**How to check:**

- **Untagged PII patterns:** Grep page bodies for patterns that commonly indicate sensitive data — lines containing `password`, `api_key`, `secret`, `token`, `ssn`, `email:`, `phone:` followed by an actual value (not a field description). If a page matches and lacks `visibility/pii` or `visibility/internal`, flag it as a likely mis-classification.
- **`visibility/pii` without `sources:`:** A page tagged `visibility/pii` should always have a `sources:` frontmatter field — if there's no provenance, there's no way to verify the classification. Flag any `visibility/pii` page missing `sources:`.

**How to fix:**
- For untagged PII patterns: add `visibility/pii` (or `visibility/internal` if it's team-context rather than personal data) to the page's frontmatter tags
- For missing `sources:`: add provenance or escalate to the user — don't auto-fill

### 10. Misc Promotion Candidates (only when `misc/` exists)

**Glob `$OBSIDIAN_VAULT_PATH/misc/*.md` first. If there are no matches, skip this check
entirely — no finding, no report section.** Only the URL-ingest path files pages there, so a
vault that has never used it has no `misc/` at all, and a check that reports "0 candidates"
every run is a line nobody reads.

**How to check:** read the `affinity` frontmatter field of each `misc/` page and flag any
where a single project's score is ≥ 3.

**How to fix:** move the page to `projects/<project-name>/references/` (or another
appropriate category), update its `category` frontmatter, remove `promotion_status`, and
grep the vault for backlinks to update them. If `affinity` is empty on a page that carries
many wikilinks, the score is stale rather than low — say so instead of promoting on it.

### 11. Synthesis Gaps

Identify high-value synthesis opportunities the wiki is missing — concept pairs that co-occur across many pages but have no `synthesis/` page connecting them.

**How to check:**
- List all pages in `synthesis/` — collect the concept pairs each one already covers (from its links or title)
- Pick 10-15 frequently linked concepts from `concepts/` and `entities/` — rank them by
  the incoming counts from the Check 0 graph
- For each pair, count the pages that link to **both**. Use the `edges` list from
  `--json`: it is `[{from, to}]` over resolved links, so the pages linking to a concept are
  the `from` values of the edges whose `to` is that concept's path. Intersect the two sets.

  Do **not** count with `grep -rl "\[\[ConceptA\]\]"`. That pattern misses
  `[[concepts/ConceptA]]`, `[[ConceptA|label]]` and `[label](concepts/ConceptA.md)`, and
  it counts syntax examples inside code fences. On the two vaults here it would find
  roughly a third of the real co-occurrences on one and almost none on the other.
- Flag pairs with co-occurrence ≥ 3 that have no existing synthesis page

**How to fix:** report the pair. Filling the gap means writing a new `synthesis/` page from
the bodies of the pages involved — a write with the content in context, which lint does not
have. Do not create a stub page just to close the gap.

### 12. Confidence and Lifecycle Schema

Enforces the confidence + lifecycle frontmatter schema. **The rubric is the sole authority on the allowed set, on which rank each value sits at, and on how a rank is decided: `~/.claude/doc/doc_wiki_lifecycle_rubric.md`.** Never copy the allowed set or the rank assignment into this file or any other skill. Refer to ranks, not to value names.

Two modes:
- **`--check`** (default, read-only) — reports errors and warnings
- **`--fix`** — may rewrite `base_confidence` only when drift is detected (Rule 12e); never rewrites `lifecycle`

#### Rule 12a — `lifecycle` enum validation

**How to check:** Grep frontmatter for `^lifecycle:` across all pages, extract the values, and compare **as a set** against the allowed set in the rubric.

**Never grep for an individual value.** Two failure modes, both silent:
- `grep 'lifecycle: verified'` matches only `verified` — it does not see a value that gained a prefix or a synonym, so a new rank is skipped without any error
- bare `grep verified` matches the word wherever it appears in `log.md` entries and page bodies, so the count is not a page count at all

The allowed set — ranked and unranked — is in the rubric (§序列 / §序列外). Read it there; do not copy the values into this file.

**Legacy values (a vault not yet converted to the rubric):** `{active, stable}` predate the rubric. Report them as **one warning line carrying a count**, never one finding per page — per-page findings drown the whole report.

**How to fix:** n/a — `--fix` never writes `lifecycle`: the rank is decided by the evidence in the page body (rubric R1–R4), and lint does not read bodies. Only a skill that has the body in context may set it.

#### Rule 12b — `base_confidence` range

**How to check:** Grep frontmatter for `^base_confidence:` across all pages. Flag any value outside `[0.0, 1.0]` or any page missing the field entirely.

**How to fix:** n/a (wrong value means the skill computed it wrong — surface for manual correction)

#### Rule 12c — Stale page report (computed overlay)

Staleness is never stored — it is computed at read time from `evidence_at` (fall back to `updated:` when the page has no `evidence_at`): `is_stale = (today − date) > 90 days`.

**How to check:** Compute `is_stale` per page, then branch on the **rank** its `lifecycle` value sits at (rubric §序列 for the ranks, §序列外 for the values outside the ladder). Match values as a set, never as a substring:

| Target | Stale behavior |
|---|---|
| ranks 5–6 (the rungs a human approved) | Louder annotation — a human vouched for this and the ground may have moved since |
| ranks 3–4 (the rungs an AI checked) | Standard warning, worded as **re-verify**. Never phrase it as a demotion — re-running an AI check is cheap, and the rubric forbids lint from writing `lifecycle` |
| ranks 1–2 (the bottom of the ladder) | **Skip.** Age adds no information |
| `index` (unranked) | Standard warning — an index nobody has touched in 90 days is the exact failure it exists to prevent |
| every other unranked value | Skip — outside the ladder, not a claim about freshness |

**How to fix:** `--fix` does **not** rewrite `lifecycle`. Staleness clears when a re-check bumps `evidence_at`.

#### Rule 12d — Supersession integrity

**How to check:** For each page with `superseded_by: "[[target]]"`:
- Verify the target page exists
- Verify the target page is not itself `archived` (no circular or chained supersession)
- Verify there are no cycles (A supersedes B which supersedes A)
- Warn if `lifecycle != archived` while `superseded_by` is set (inconsistent state)

**How to fix:** n/a — flag for human resolution

#### Rule 12e — Confidence drift

**How to check:** read `base_confidence` from the Check 7 script run (`null` unless the page has both `base_confidence:` and `sources:`). Each entry has `stored`, `recomputed`, `drift`, `drift_flag` (|drift| > 0.05) and `sources` — how each line was folded into a `source_id` and bucket per the defaults in `~/.claude/doc/doc_wiki_schema.md`. Before flagging, read the `sources` of the flagged pages: when a bucket is plainly wrong for a source (a vendor doc classed `unknown`), rerun with `--bucket <source_id>=<bucket>` rather than accepting the number.

**How to fix (`--fix` only):** rerun the script with `--fix-confidence` (plus the same `--bucket` overrides). It rewrites only the `base_confidence:` line of drifting pages. This is the **only rule** that mutates frontmatter automatically.

#### Rule 12f — Evidence requirements for ranked pages

A rank asserts that an action was taken (rubric: *the axis records the act, not a self-assessed confidence*). This rule checks the page still carries a pointer to that act. **Without this rule the ladder is prose only** — and prose without a check drifts.

**How to check:** For pages at ranks 2–6 (rubric §序列 — the ranks the rubric requires evidence for):

- `lifecycle_evidence` present and non-empty → else **error**
- `evidence_at` present and parseable as an ISO date → else **error**
- The section or table that `lifecycle_evidence` names still exists in the body → else **warn** ("evidence was edited away; the rank is now unbacked")

For ranks 3–4 additionally **warn** when the body carries none of the shapes the rubric requires for that rank — they are the *証拠として本文にあるべきもの* column of §序列. Read the shapes there; do not copy them into this file.

Skip rank 1 and the whole unranked set (rubric §序列外).

**This last check is a heuristic over prose and will produce false positives.** Keep it a warning, never an error, and never let `--fix` act on it. If it fires often enough to be noise, the fix is to tighten the rubric's decision table — not to widen the accepted shapes.

**How to fix:** n/a — surface it for the next skill that touches the page with the body in context.

Findings from Rules 12a–12f go in the `Confidence/Lifecycle Issues` section (sample lines in `references/output-format.md`) and their total in `lifecycle_issues=N` on the `LINT` log entry.

### 13. Typed Relationships Validity

Validate `relationships:` frontmatter blocks. Skip pages that have no `relationships:` block — the field is optional.

**Allowed types:** the single source of truth is the **Typed Relationships table in
`~/.claude/doc/doc_wiki_schema.md`** — 10 concepts, 16 spellings; directional types are
valid in both their forward and reverse spellings. Read that table before checking.
Never copy the set into this file.

**How to check:**
- Grep frontmatter for `^relationships:` across all vault pages
- For each page that has a `relationships:` block, read its frontmatter (not the full page body)
- For each entry in the block:
  1. **Type validation** — report any `type:` value not in the schema doc's table **as a
     warning, not a failure** (see below)
  2. **Broken target** — the link graph from Check 0 already resolved these; a `target:`
     that appears in its `broken` or `ambiguous` list is the finding. Do not re-resolve by hand.
  3. **Self-reference** — flag any entry where the resolved target equals the page's own node id

**Out-of-enum types are a warning.** The out-of-enum types found so far were all written
by `wiki-update` / `wiki-ingest` — the same bundle that defines the enum — so an
out-of-enum type usually means the vocabulary splitting inside one system, not a user
error, and the targets resolve fine. Reporting them as failures buries the findings that
are actually broken. Only unresolved targets and missing required frontmatter are failures.

**Known aliases — normalize on sight.** Same direction, same meaning, and the target is
inside the enum, so the substitution is purely mechanical. **This table's home is here in
wiki-lint** — the schema doc deliberately carries no copy and points to this file:

| written | normalize to |
|---|---|
| `relates_to` | `related_to` |
| `supersedes` | `replaces` |
| `depends_on` | `uses` |
| `enables` | `used_by` |
| `generalizes` | `extended_by` |
| `complements` | `related_to` |
| `applies` | `uses` |
| `applied_by` | `used_by` |

**Concepts the enum does not have: report, do not rewrite.** A type that is neither in
the schema doc's table nor in the alias table has nothing to normalize toward — mapping
it to `related_to` throws away the distinction that made someone write it. Leave the
entry as it is and report it; widening the enum is a schema decision, not a lint fix.

**How to fix:**
- Alias type: normalize per the table above
- `type: superseded_by` / `type: replaced_by`: not a relationship type — the page belongs in
  `lifecycle: archived` with the **top-level** `superseded_by:` field (a different namespace;
  see the schema doc's Confidence and Lifecycle section). Report it with that pointer
- Unknown type: leave it and report it; widening the enum is a schema decision
- Broken target: update or remove the entry; if the target page should exist, create it first
- Self-reference: remove the entry

Findings go in the `Typed Relationship Issues` section (sample lines in `references/output-format.md`) and their total in `relationship_issues=N` on the `LINT` log entry.

## Output Format

Write the findings as a `## Wiki Health Report` with one `###` section per check, in check
order. **The template and a sample line for every section are in
`references/output-format.md` — follow it rather than inventing a layout**, and omit any
section whose check found nothing.

## After Linting

Append **one** line to `log.md` — this is the whole format, every key present every run:
```
- [TIMESTAMP] LINT issues_found=N orphans=X broken_links=Y ambiguous_links=A missing_frontmatter=FM missing_summary=S stale=Z contradictions=W index_issues=I prov_issues=P fragmented_clusters=F over_tagged=T malformed_tags=MT visibility_issues=V promotion_candidates=C synthesis_gaps=G lifecycle_issues=L relationship_issues=R graph=script|manual
```

Key order is check order. `issues_found` is **not** the sum of the other keys — past runs
recorded 111 against a key sum of 151, and 71 against 103 — so a count with no key of its
own is unrecoverable, not merely aggregated. Every check with a report section has a key
here for that reason; add one in the same edit that adds a section.

A check that was skipped because its precondition was absent (Check 10 with no `misc/`) reports `0`. Dropping the key instead makes the line unparseable against earlier runs.

`[TIMESTAMP]` is the output of `date -u +%Y-%m-%dT%H:%M:%SZ` — run it and paste the result verbatim, never hand-write it (why: schema doc, `log.md`).

`graph=` records whether Check 0 ran the script or the manual fallback. Counts from the
two are not comparable, so a run-to-run delta means nothing without it.

Offer to fix issues automatically or let the user decide which to address.

---

## Consolidate Mode (`--consolidate`)

Only when the invocation carries `--consolidate`: this switches wiki-lint from report-only
to act-and-report (the "dream cycle"). **Read `references/consolidate-mode.md` and follow
it** — it defines the actions, the report page, and the dry-run gate.

Three rules from it that decide whether you may write at all:

- **Dry-run first, always.** Print every planned action, then ask `"Apply these N changes? [yes / no / select]"`. No page is written before an explicit answer.
- The only write that needs no confirmation is the single `log.md` append at the end.
- Never merge pages (that is `wiki-dedup`'s job) and never write `lifecycle` — consolidate does not read page bodies, so it has no grounds to rank anything.