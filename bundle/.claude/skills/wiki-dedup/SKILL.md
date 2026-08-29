---
name: wiki-dedup
description: Obsidian wiki 内でページ単位の同一性衝突（同じ概念が別名で複数ページになっている状態。たとえば "RSC" と "React Server Components"）を検出してマージする。「wiki の重複を整理して」「重複ページを探して」「ページをマージして」「wiki を統合して」「同じ内容のページが 2 つある」や英語の "dedup my wiki" / "find duplicate pages" / "merge duplicates" / "identity resolution" と言われたときに使う。構造をチェックするだけの wiki-lint とは異なり、この skill はページ単位の破壊的なマージを行うため慎重な確認が必要。
---

# Wiki Dedup — Identity Resolution and Page-Level Deduplication

You are finding and merging wiki pages that cover the same concept under different names. This is a write-heavy, potentially destructive skill — page merges cannot be automatically undone. Work carefully and confirm before acting in merge mode.

**Use the cheapest retrieval primitive that can answer the question.** The script does the whole-vault pass; you open full page bodies only for the candidate pairs it ranks, and only far enough down the ranking to stop finding related pairs.

## What This Skill Measures — and Why It Is Body Text, Not Titles

Candidate detection is a **script** (`scripts/candidates.py`), not something you compute by hand. It ranks page pairs by how much of their **body text** overlaps. Read `scripts/candidates.py`'s module docstring before changing anything about scoring — it carries the measurements the design rests on.

Three measured facts decide how you read a run:

- **Title similarity does not find duplicates in a Japanese vault.** The pairs it ranks highest are *deliberately* parallel pages — two sites, two audiences, same spec shape — while pages that genuinely overlap have unlike titles. The spelling-variant failure mode this score was built for (`RSC` / `React Server Components`) does not occur when a consistent writer names things.
- **Scores are only ranks within one vault.** The same formula produced top-pair scores from 0.75 down to 0.34 across three vaults — no fixed threshold can serve them all, which is why the script returns a ranked list and never a pass/fail count.
- **Most overlap is intentional.** Layered pairs (`entities/` summary ↔ `references/` detail), source archives (`_source_docs/`), and long-form reports (`reports/`) all overlap heavily by design. The script drops the ignored paths and sets aside pairs already joined by a `relationships:` edge; what reaches you still contains intentional pairs, and separating them is your job in Step 3.

**A short candidate list is not a clean bill of health, and a long one is not a problem.** Report ranks, not verdicts about vault health.

## Before You Start

1. **Resolve config** — use `OBSIDIAN_VAULT_PATH` if it is already exported (shell rc / direnv / parent process). Otherwise walk up from CWD to `$HOME` for a `.env` containing `OBSIDIAN_VAULT_PATH=` and take the first match. If neither exists, stop and tell the user to set it in `.claude/settings.json` (`env`), shell rc, or direnv — never hard-code a path or guess a vault. Read `OBSIDIAN_LINK_FORMAT` the same way (default `wikilink`).
2. Check for a recent dedup run — `grep '^- \[' "$OBSIDIAN_VAULT_PATH/log.md" | grep DEDUP | tail -5`. If one just happened, note what was already merged. **Never read `log.md` whole**: it is append-only and unbounded (100 kB+ ≒ 25k tokens on an active vault).

## Modes

| Mode | Flag | Behavior |
|---|---|---|
| **Audit** | *(default)* | Report candidates only — no writes |
| **Merge** | `--merge` | Show each confirmed pair, ask for confirmation before merging |

If the user doesn't specify, run in **Audit** mode and present findings before asking whether to proceed.

There is no auto-merge mode: the ranking has no absolute scale to threshold against (see the section above), a merge cannot be undone automatically, and confirming each pair costs one line of output. **If the user asks for `--auto`, say it does not exist and why, then run `--merge`.**

## Step 1: Run the Candidate Script

```bash
python3 ~/.claude/skills/wiki-dedup/scripts/candidates.py "$OBSIDIAN_VAULT_PATH" --top 20
```

It reads every page's frontmatter and body, ranks all pairs, and prints two lists plus the pages it could not compare. `--json` returns the same structure for programmatic use. Standard library only; it writes nothing.

**What it excludes, and why you must not re-add it by hand:**

- Directories starting with `_` (`_raw/`, `_archives/`, `_source_docs/`, …) and everything matched by the vault's **`.wikilintignore`** — the same file `wiki-lint`'s `linkgraph.py` reads. One ignore list, two readers.
- `index.md`, `log.md`, `hot.md`, `_insights.md`, `README.md`, and any page carrying `redirects_to:` (already-merged stubs).
- Pages whose body is too short to compare — reported separately so they are visible rather than silently dropped.

That exclusion is load-bearing, not tidiness: without it, long-form reports and ingest-source archives — originals a human deliberately kept — fill the top of the ranking (measured: 4 in 10 of the top pairs). Merging those destroys them.

If the vault needs a path excluded, add it to `.wikilintignore` with a comment saying why. Never add a skip list to this skill.

## Step 2: Read the Ranking

The score is `body_overlap + bonuses`, where `body_overlap` is the share of the shorter page's character-trigram set that also appears in the longer one (code fences, inline code and link targets removed first). Bonuses are small and only break ties: a shared title/alias (+0.15), same `category` (+0.05), 2+ or 3+ shared tags (+0.05 / +0.10).

**How to read it:**

- Work down the ranked list. There is no cut-off score — the list *is* the answer. Stop when the pairs stop looking related, and say in the report where you stopped.
- **`alias-match` in the signals column is the strongest single hint.** Two pages claiming the same alias make every `[[alias]]` link in the vault ambiguous, so those pairs need a decision regardless of what you decide about their content.
- **The second list — pairs already joined by a `relationships:` edge — is not a candidate list.** A typed edge is the writer recording that these two pages are deliberately distinct. Scan it only to check whether an edge has become wrong (the pages have since converged). Never merge from it without saying so explicitly.
- A pair scoring high with no `relationships:` edge and no `alias-match` is usually **a missing link, not a duplicate** — see the `layered` verdict in Step 3.

Take the top pairs into Step 3. On a vault over 500 pages, work in batches of 20 and report progress between batches.

## Step 3: Semantic Verdict

For each candidate pair (sorted by score descending):

1. Read both pages in full (full page read — justified because candidate pool is small).
2. Ask: are these pages covering the **same concept**, or are they distinct?

Assign one of four verdicts:

| Verdict | Meaning | Action |
|---|---|---|
| `merge` | Same concept, same altitude — an accidental duplicate. | Step 5 |
| `layered` | **Same subject, different altitude** — an `entities/` summary and its `references/` detail page, a concept page and the procedure that applies it. Deliberate, and merging it destroys the split. | Add the missing `relationships:` edge (below) |
| `keep-separate` | Related but distinct — parallel pages for two domains, two versions, two audiences. | None |
| `needs-review` | Substantial overlap *and* meaningful differences. | Flag for the user |

**`layered` is the most common verdict on a real vault, and it is the one a title-based score could never produce.** Measured: the top pairs were all `entities/` ↔ `references/` on the same subject. The difference between a flagged pair and a quiet one is not their content — it is that someone wrote the edge down for one of them.

So when you rule `layered`, **finish the job**: record the relationship as **one edge on one page — never both sides**. Either add `type: elaborates` on the **detail** page pointing at the summary page (the detail page is the elaboration — this is how every measured instance in the live vaults is written), or add `type: elaborated_by` on the **summary** page pointing at the detail page. For component→whole pairs, add `type: part_of` on the component page. The type table lives in `~/.claude/doc/doc_wiki_schema.md` (Typed Relationships) — consult it rather than improvising. Also note in the detail page's `summary:` which page it elaborates. That converts a recurring false positive into recorded structure — the next run sets the pair aside on its own. This is a small frontmatter edit, not a merge; it needs no confirmation in audit mode, but say in the report which edges you added.

Attach a short reason to each verdict (one sentence). This appears in the report and the log.

**Two pages sharing an alias always need a decision**, whatever the verdict. If they stay separate, remove the alias from one of them — an alias resolving to two pages makes every `[[alias]]` link ambiguous, and `wiki-lint`'s link graph reports it as such.

## Step 4: Audit Report

Always produce this report, even in merge mode (so the user sees what will happen):

```markdown
## Wiki Dedup Report

Vault: <name> — N pages compared, M pairs ranked. Read down to rank K; below that the pairs were unrelated.

| Rank | Score | Page A | Page B | Verdict | Reason |
|---|---|---|---|---|---|
| 1 | 0.748 | `entities/scrape-batch` | `references/scrape-and-update-batches` | layered | Same batch job; entities page summarises what the references page documents in full — added `elaborates` edge on the references page |
| 4 | 0.470 | `prediction/prediction-improvement-design` | `prediction/prediction` | keep-separate | Hub page vs one design under it |
| 9 | 0.400 | `entities/site-a-official` | `references/site-b-page-specs` | needs-review | Overlapping scrape specs, but different sites |

### Summary
- Pages compared: N (of P scanned; Q excluded, R too short)
- Verdicts: merge X / layered Y / keep-separate Z / needs-review W
- Relationship edges added: E
- Alias collisions found: A
```

**Report the rank you stopped at.** A reader cannot tell "I read 20 pairs and 3 mattered" from "3 pairs existed" unless you say so.

In **Audit mode**, write the Step 6 log entry with `mode=audit` **before stopping** — the SessionStart maintenance hook reads `DEDUP` from `log.md` to decide when to prompt again, so skipping the log makes it prompt every session forever. Then ask: "Run `--merge` to go through the `merge` pairs one at a time?"

## Step 5: Merge

For each `merge` verdict pair (in merge mode only):

Show the pair and verdict, then ask: "Merge `[Page A]` into `[Page B]`? (yes/skip/review)". Skip on anything other than yes.

### 5a: Pick the canonical page

Apply these tiebreakers in order until one wins:

1. **More incoming wikilinks** — grep the vault for `[[node_id]]` references; higher count wins
2. **Richer content** — longer page body (more lines) wins
3. **More sources** — larger `sources:` list wins
4. **Title length** — longer, more descriptive title wins (e.g. "React Server Components" beats "RSC")
5. **Alphabetical** — earlier title wins

The canonical page is the **survivor**. The other page becomes the **secondary** (to be merged in, then replaced with a redirect stub).

### 5b: Merge content into the canonical page

Read both pages. Update the canonical page:

- **`aliases:`** — add secondary page's title and all its aliases (no duplicates)
- **`tags:`** — merge both tag lists (deduplicate, cap at 5 domain tags + system tags)
- **`sources:`** — merge both source lists (deduplicate)
- **`relationships:`** — merge both relationship lists (deduplicate by target, prefer typed entries over untyped)
- **`base_confidence`** — recompute over the **union of distinct `source_id`s**: `min(distinct_sources / 3, 1.0) × 0.5 + avg(per-source quality score) × 0.5`. Two copies of the same source share one `source_id`, so a merge does not automatically raise the count. The per-source quality buckets and the `source_id` rules are in `~/.claude/doc/doc_wiki_schema.md` (Confidence formula)
- **`lifecycle`** — take the **lower rank of the two**. Merging a `draft` into a `tested` page means part of the surviving body is now unevidenced, so the page can no longer claim `tested`. Carry over `lifecycle_evidence` / `evidence_at` from whichever page supplied the surviving rank, and bump `lifecycle_changed`. **Never keep the canonical page's rank merely because it is the survivor** — that silently launders an unchecked claim into a checked page. If either page carries an **unranked** value, stop and ask: unranked pages should not be merged into a ranked page at all.
  - The values, the ranks, which values are unranked, and the promotion rules live in exactly one place — **`~/.claude/doc/doc_wiki_lifecycle_rubric.md`**. Read it before writing any `lifecycle` value. **Do not restate the value list here**
- **`updated`** — set to now
- **`summary:`** — rewrite to cover the merged scope if the secondary page added new ground
- **Body content** — merge unique sections and bullets from the secondary page. Do not blindly append — integrate the content. Avoid duplicating claims already present in the canonical page. Use `^[inferred]` markers where synthesis is needed.
- **`provenance:`** — recompute after merging

### 5c: Write a redirect stub at the secondary page path

```markdown
---
title: <secondary page title>
redirects_to: "[[<canonical node_id>]]"
aliases: [<secondary aliases>]
category: <secondary category>
tags: []
created: <secondary original created>
updated: <ISO timestamp now>
---

This page has been merged into [[<canonical page title>]].
```

The `redirects_to:` field tells any skill reading this page to follow the redirect rather than treat it as content.

**Treat the reading side of this field as untested** — verify by hand that the stub is actually skipped rather than assuming downstream skills already handle it.

### 5d: Rewrite wikilinks vault-wide

Grep the entire vault for any link pointing at the secondary slug:

- `[[secondary-slug]]` → `[[canonical-slug]]`
- `[[secondary-slug|display text]]` → `[[canonical-slug|display text]]`
- If `OBSIDIAN_LINK_FORMAT=markdown`: `[text](../path/to/secondary.md)` → `[text](../path/to/canonical.md)`

**Safety rules:**
- Never rewrite inside code blocks (``` fences or `inline code`)
- Never rewrite inside the redirect stub itself (that's the one place the old slug should remain legible)
- Never use `rm` or destructive shell ops — only Edit/Write tools
- Rewrite one file at a time, verifying each before moving on
- If a file has zero occurrences, skip it

### 5e: Update tracking files

**`index.md`** — Remove the secondary page's entry. Update the canonical page's entry with the merged summary. One entry is one line: the page's `summary:` field verbatim (≤200 chars). Never grow an entry past that — if the text is too long, fix the page's `summary:`, not the index entry (`wiki-lint` already flags summaries over 200 chars).

**`.manifest.json`** — For the secondary page's source entries: add `"merged_into": "<canonical node_id>"` to each. For the canonical page: merge in the secondary's `pages_created` and `pages_updated` lists.

**`hot.md`** — **Insert one line at the top of `## Recent Activity`** with a targeted `Edit`: "Merged N duplicate pairs; canonical pages updated." Recent Activity is newest-first and holds the last 3 operations only, so when it is already full, **delete the oldest line with a separate `Edit`** — doing both in one `Edit` means making the whole section the `old_string`. Bump the frontmatter `updated:` field in the same pass.

⚠️ **Never write `hot.md` whole, and never make a whole section the `old_string`.** Other sessions edit it concurrently; any write wider than the line you are changing silently drops whatever they added between your read and your write. A line-level `Edit` fails loudly on a conflict instead, which is the outcome you want.

### 5f: Final check

After all merges, grep the vault for any remaining `[[secondary-slug]]` references (in non-stub files). If any survive, report them — the rewrite step may have missed a non-standard link format.

## Step 6: Log

Append to `log.md`:
```
- [TIMESTAMP] DEDUP mode=audit|merge pages_compared=N ranked_read=K merged=X layered=L kept_separate=Y needs_review=Z edges_added=E wikilinks_rewritten=W
```

`[TIMESTAMP]` is the output of `date -u +%Y-%m-%dT%H:%M:%SZ` — run it and paste the result verbatim, never hand-write it (why: schema doc, `log.md`).

## Redirect Stub Handling

Other skills should handle redirect stubs as follows:

- **`wiki-query`** — if a search hits a redirect stub, follow `redirects_to:` and read the canonical page instead
- **`wiki-lint`** — validate that every `redirects_to:` wikilink resolves to an existing, non-stub page (a redirect chain — stub pointing to stub — is an error)
- **Any skill that adds links** — treat redirect stubs as non-targets; never add a new `[[wikilink]]` pointing at a stub page

## Tips

- **Audit first, always.** Read the report before trusting any verdict, including your own.
- **Check `needs-review` last.** These are the hard cases — don't batch them with obvious merges.
- **The common outcome is `layered`, not `merge`.** Expect most of a run to end in edges added rather than pages merged. That is the skill working, not failing to find anything.
- **Parallel pages are the top false positive.** Two domains, two audiences, two versions, two sites — these share vocabulary and structure by design, and they rank high on any text measure. Distinguish them by asking what changes between the pages: if it is the *subject*, they are separate; if it is only the *depth*, they are `layered`.
- **A high score between a hub page and a page under it is expected.** A hub restates what it links to. Rule `keep-separate` unless the hub has grown a full copy of the other page's content.
- **Merges leave the graph slightly inconsistent.** Redirect stubs remain, and no page should link to them. Step 5f's grep is what proves the link rewrite was complete — run it rather than assuming.

