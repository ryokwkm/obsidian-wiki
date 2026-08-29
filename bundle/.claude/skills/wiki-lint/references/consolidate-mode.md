# Consolidate mode (`--consolidate`)

Read this only when the invocation carries `--consolidate`. It switches wiki-lint from
report-only to **act-and-report** — the "dream cycle" that runs periodically so the wiki
self-heals.

## Safety protocol

**Always run in dry-run first.** Before writing anything:

1. Run every lint check (Checks 0–13 in `SKILL.md`).
2. Print the planned consolidation actions as a structured list (see Dry-Run Output below).
3. Ask the user: `"Apply these N changes? [yes / no / select]"`.
4. Only proceed with writes after explicit confirmation. If the user selects individual
   actions, apply only those.
5. Never merge pages — use `wiki-dedup` for that. Never write `lifecycle` — only link,
   demote `tier`, and flag.

The one write that needs no confirmation is the single `log.md` append at the end.

## Consolidation actions (in order, after confirmation)

### Action 1: Fix broken links

Operate **only** on entries in the script's `broken` list. Never on `ambiguous` ones —
those links are not wrong, they just match several pages, and demoting one to plain text
destroys a working reference (see Action 1a).

For each broken target:
- Search the vault for a page whose title or filename is the closest fuzzy match (use `Grep` across `index.md` titles)
- If a unique best match exists (edit distance ≤ 2 characters or same root word): rewrite the link. Note the rewrite: `[[Oringal]] → [[corrected-page]]`.
- If no match: convert to plain text (`~~[[Target]]~~` → `Target`) and add a comment `<!-- broken link: no match found -->`.
- Never create a new page just to satisfy a broken link.
- Rewrite the link **in the notation the source page already uses** — turning
  `[label](../dir/page.md)` into `[[page]]` changes how it resolves.

### Action 1a: Qualify ambiguous links

For each entry in the script's `ambiguous` list: rewrite the target with its directory
(`[[build-spec]]` → `[[project-a/build-spec]]`), choosing the page
that fits the source page's subject. **If which one was meant is not obvious from the
surrounding text, leave it and report it** — guessing here silently rewires the graph.

### Action 2: Add missing cross-references for orphans

For each orphan page from Check 1, after excluding the two false positives named there
(0-byte files, and directories that are deliberately not wiki pages — those get a
`.wikilintignore` entry instead, never a cross-reference):
- Grep the vault body text for mentions of the page's title or aliases (case-insensitive).
  **Ignore mentions inside code fences and inline code** — those are examples, and linking
  them changes the meaning of the surrounding text.
- For each mention found in another page, add a link replacing the plain-text mention,
  in the notation that page already uses.
- Limit to 3 insertions per orphan — don't flood pages with links.
- Scope is orphans only. Do not widen it into a full-vault link pass.

### Action 3: Flag stale ranked pages

**This action never writes `lifecycle`.** Not because promotion is human-only — the rubric
(`~/.claude/doc/doc_wiki_lifecycle_rubric.md`) assigns ranks 1–4 to AI — but because
`--consolidate` does not read the page body, and a rank is decided by the evidence in the
body. It may only annotate.

Threshold is **90 days** for every tier — the same value as Rule 12c, never a local variant.
Compute from `evidence_at`, falling back to `updated:`.

Branch on the **rank** the page's `lifecycle` value sits at — read the rank from the rubric
(§序列 / §序列外) rather than restating the values here, and match values as a set, never as
a substring:

- ranks 5–6 (the rungs a human approved) and stale → add at the top of the body: `> ⚠️ **Stale**: A human vouched for this on <date>. Verify before relying on it.`
- ranks 3–4 (the rungs an AI checked) and stale → add: `> ⚠️ **Re-verify**: The evidence behind this dates from <date>. Re-running the check is cheap.` **Word it as re-verification, not doubt** — the measurement was correct when taken
- `index` (unranked) and stale → add: `> ⚠️ **Possibly out of date**: This page indexes others and was last touched <date>.`
- everything else → no callout

Only add a callout if one isn't already present.

### Action 4: Tier demotion

For pages with `tier: supporting` (or unset) that have **≤ 1 incoming link** AND haven't
been updated in 90+ days:
- Set `tier: peripheral`.
- Emit a list of demotions for the user to review.
- Do not demote `tier: core` pages automatically — those were manually set.

`≤ 1` is the demotion threshold everywhere in this bundle (same value as the schema doc's
Importance Tiering — never a local variant).

### Action 5: Contradiction callouts

For each pair of pages marked as contradicting each other (via `relationships: contradicts`
in frontmatter, or flagged in Check 5):
- Check whether a `> ⚠️ Contradiction flagged with [[Other Page]]` callout already exists near the relevant claim.
- If not, add it as one line directly after the claim (or the section) it contradicts. If the contradicting claim cannot be located, put it at the end of the body. Do not assume a "Key Ideas" or "Open Questions" section exists (why: schema doc, Page Template).
- Do not resolve the contradiction; only flag it visually.

### Action 6: Write consolidation report

After all actions, write a report to `synthesis/consolidation-<YYYY-MM-DD>.md`:

```markdown
---
title: Consolidation Report <YYYY-MM-DD>
category: synthesis
tags: [maintenance, consolidation]
sources: []
summary: Auto-generated consolidation report from wiki-lint --consolidate run on <date>.
lifecycle: draft
lifecycle_changed: <date>
tier: peripheral
created: <ISO timestamp>
updated: <ISO timestamp>
---

# Consolidation Report — <YYYY-MM-DD>

## Summary
- Broken links fixed: N
- Ambiguous links qualified: Q
- Cross-references added: M
- Stale callouts added: K
- Tier demotions: D
- Contradiction callouts added: C

## Broken Link Fixes
- `concepts/foo.md:12` — [[OldTarget]] → [[correct-target]]
- `entities/bar.md:8` — [[Missing]] → `Missing` (no match found)

## Ambiguous Links Qualified
- `project-a/a.md` — [[build-spec]] → [[project-a/build-spec]]

## Cross-References Added (orphan rescue)
- `concepts/baz.md` — now linked from: [[concepts/alpha]], [[skills/beta]]

## Stale Callouts
- `synthesis/old-analysis.md` — stale callout added (lifecycle=verified, evidence_at 2025-10-01)
- `project-a/calibration.md` — re-verify callout added (lifecycle=tested, evidence_at 2025-11-20)

## Tier Demotions
- `concepts/unused-concept.md` — supporting → peripheral (1 link, 120 days stale)

## Contradiction Callouts
- `concepts/scaling.md` — flagged contradiction with [[synthesis/efficiency]]
```

The report page is a `draft` like any other new page: it states what a run did, and no
evidence in it was checked, so it never carries a rank above `draft`.

## Dry-Run Output (shown before any writes)

```
wiki-lint --consolidate — Dry Run

Planned actions (N total):
[1] Fix broken link: concepts/foo.md:12 [[OldTarget]] → [[correct-target]]
[1a] Qualify ambiguous link: project-a/a.md [[build-spec]] → [[project-a/build-spec]]
[2] Add cross-ref: concepts/baz.md ← [[concepts/alpha]] (orphan rescue)
[3] Stale callout: synthesis/old-analysis.md (lifecycle=verified, 208 days since evidence_at)
[3] Re-verify callout: project-a/calibration.md (lifecycle=tested, 95 days since evidence_at)
[4] Tier demotion: concepts/unused.md → peripheral (1 link, 112 days stale)
[5] Contradiction callout: concepts/scaling.md ↔ [[synthesis/efficiency]]

Apply these 7 changes? [yes / no / select by number]
```

## Log entry for consolidate mode

```
- [TIMESTAMP] LINT_CONSOLIDATE links_fixed=N orphans_rescued=M stale_callouts=K tier_demotions=D contradiction_callouts=C report=synthesis/consolidation-YYYY-MM-DD.md
```

`[TIMESTAMP]` is the output of `date -u +%Y-%m-%dT%H:%M:%SZ` — run it and paste the result
verbatim.

## No tag alias normalization here

This mode does not normalize tag aliases. Do not add such a pass by inventing an alias
list inside this skill — a tag alias table needs one canonical home first
(`~/.claude/doc/doc_wiki_schema.md`).
