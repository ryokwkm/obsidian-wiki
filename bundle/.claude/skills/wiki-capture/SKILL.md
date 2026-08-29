---
name: wiki-capture
description: 現在の会話を恒久的で構造化された wiki ノートとして保存する。「これを保存して」「/wiki-capture」「これを記録して」「この会話を残して」「wiki に追加して」や英語の "save this" / "capture this" / "preserve this" / "add this to my wiki" と言われたとき、いま話した内容を残る知識に変えたいときに使う。内容を分類し、チャットの書き起こしではなく宣言的な知識として書き直し、vault の正しいカテゴリへ配置する。60 秒以内に `_raw/` ステージング領域へ投げ込む高速な QUICK MODE も持つ（`/wiki-capture --quick`、「クイックキャプチャ」「この知見を保存して」「このバグ修正を保存して」「この落とし穴を保存して」「raw に放り込んで」や "quick capture" / "quick save to wiki"）。QUICK MODE は manifest も index も書かず、あとから `/wiki-ingest` で本ページへ昇格させる。
---

# Wiki Capture — Conversation to Wiki Note

You are preserving knowledge from the current conversation as a permanent wiki note. The goal is to extract the *substance* — the knowledge itself — not a summary of what was said.

This skill has two modes:

- **Full mode (default)** — classify the content and write a finished, cross-linked wiki page directly into the right category. This is the rest of this document (Steps 1–7).
- **Quick mode (`--quick`)** — zero-friction staging: drop findings to `_raw/` in under 60 seconds with no manifest/index/log writes. Used for mid-session capture. See below, then stop — do **not** run the full-mode steps.

## Quick Mode (`--quick`)

Trigger when invoked as `/wiki-capture --quick`, or by "quick capture" / "capture this finding" / "save this bug fix" / "save this gotcha" / "drop this to raw" / "quick save to wiki".

**There is no automatic invocation.** Quick mode runs only when someone calls it — the bundle registers no Stop hook, so nothing fires this skill at session end. Do not wait for an automatic capture to happen; call `/wiki-capture --quick` while the finding is still in the conversation.

**Speed contract:** Inline only. No subagents. No manifest/`index.md`/`log.md`/`hot.md` writes. Target: <60 seconds. Promotion to full wiki pages happens later via `/wiki-ingest`.

1. **Resolve config** — use `OBSIDIAN_VAULT_PATH` if it is already exported; else walk up from CWD to `$HOME` for a `.env` containing `OBSIDIAN_VAULT_PATH` and use the first hit; else tell the user to set it in `.claude/settings.json` (`env` block) and stop. `OBSIDIAN_RAW_DIR` defaults to `$OBSIDIAN_VAULT_PATH/_raw`. **Assume the directory does not exist** — most vaults have never staged a capture — so create it before writing: `mkdir -p "$OBSIDIAN_RAW_DIR"`.

2. **Gate — KEEP or SKIP?** Before extracting, judge whether this session has capture value. This keeps `_raw/` free of files nobody will promote.
   - **SKIP** (exit with "Nothing worth capturing in this session.") if ALL are true: the conversation is purely conversational (planning/Q&A/explanation) with no implementation; no errors, debugging, or problem-solving visible; nothing surprising or undocumented; every finding is already obvious from the docs.
   - **KEEP** (proceed) if ANY are true: a fix or workaround was found through investigation; non-obvious library/API/framework behavior was confirmed (edge case, undocumented constraint, time-costing gotcha); a debugging session reached a concrete conclusion; a reusable pattern emerged.
   - When the **user asked for it, err toward KEEP** — they called it for a reason. When **you reached for it unprompted** (wrapping up a work stretch on your own initiative), **err toward SKIP** — nobody vetted the request, so only KEEP on clear evidence.

3. **Scan for reusable findings** — non-obvious bugs and root causes, framework/library gotchas, surprising API behavior, investigated workarounds, environment/toolchain quirks, patterns from debugging. Skip PM updates, config already in CLAUDE.md, inconclusive back-and-forth, anything obvious from the docs, and pleasantries. If nothing material emerged, say so and stop.

4. **Cluster by topic** — one `_raw/` file per topic cluster, not per finding. Name each as a kebab-case slug (e.g. `swift-actor-reentrancy`, `nextjs-hydration-mismatch`).

5. **Infer project context** from repo names, file paths, framework mentions, error messages. Use the most specific name you can reliably infer; else `null`.

6. **Write raw files** — for each cluster, write `$OBSIDIAN_RAW_DIR/<ISO-date>-<slug>.md`. Read `references/RAW-FORMAT.md` for the full frontmatter spec, finding-block body structure, and provenance/confidence calibration. Per-cluster fields that vary: `title`, `tags` (2–4, reusing tags that already appear in the vault's `index.md` rather than coining new ones), `summary` (≤200 chars), `project` (inferred or `null`), `base_confidence` and the `provenance.extracted`/`provenance.inferred` split (both from the calibration table in `references/RAW-FORMAT.md` — do not guess a number), `lifecycle_changed` (today), `sources` (`"<project> session (<YYYY-MM-DD>)"`).

7. **Confirm** — list staged files and tell the user to run `/wiki-ingest` to promote them:
   ```
   Staged to _raw/:
     _raw/2026-05-27-swift-actor-reentrancy.md   — "Actor reentrancy causes deadlock in async forEach"
   Run /wiki-ingest to promote these to full wiki pages.
   ```
   Quick mode deliberately does **not** write the manifest, `index.md`, `log.md`, or `hot.md` — promotion via `/wiki-ingest` handles all of that. **Stop here; do not run the full-mode steps below.**

---

## Full Mode

## Before You Start

1. **Resolve config** — same as Quick Mode step 1; additionally read `OBSIDIAN_LINK_FORMAT` (default: `wikilink`).
2. Read `$OBSIDIAN_VAULT_PATH/index.md` to understand existing wiki content (avoid duplicates)
3. Read `$OBSIDIAN_VAULT_PATH/hot.md` if it exists — it gives context on recent activity

When writing internal links in Step 5, apply the `OBSIDIAN_LINK_FORMAT` value per the Link Format rules in `~/.claude/doc/doc_wiki_schema.md` (`wikilink` → `[[path/to/page|display]]`; `markdown` → `[display](relative/path.md)` computed from the current file's directory).

## Step 1: Identify What's Worth Preserving

Scan the conversation. Ask: what knowledge emerged here that would be valuable in 3 months with no memory of this chat?

Worth preserving:
- Decisions made and *why* they were made
- Analysis, frameworks, mental models developed
- Technical findings, patterns, or procedures
- Synthesized understanding of a topic
- Clear explanations of a concept that took effort to arrive at
- Key facts from an external source discussed in the conversation

Skip:
- Logistics, scheduling, pleasantries
- Exploratory back-and-forth where no conclusion was reached
- Content that's already in the wiki

If nothing material emerged, tell the user and stop.

## Step 2: Classify the Content Type

Assign one of five types — this determines the target folder and tone:

| Type | Description | Target folder |
|---|---|---|
| `synthesis` | Multi-step analysis or an answer to a specific question that required reasoning | `synthesis/` |
| `concept` | A definition, framework, or mental model (what a thing *is*) | `concepts/` |
| `source` | Summary of an external document, article, or resource discussed | `references/` |
| `decision` | A strategic, architectural, or design choice and its rationale | `synthesis/` |
| `session` | A complete discussion summary when the conversation spans multiple topics | `journal/` |

If the content clearly belongs to a specific project (detected from context or user mention), place it under `projects/<project-name>/<category>/` instead.

## Step 3: Rewrite as Declarative Knowledge

Do **not** write a summary of the conversation. Write the knowledge itself, in declarative present tense:

- Not: "The user asked about X and Claude explained that..."
- Yes: "X works by..."
- Not: "We decided to use Y because..."
- Yes: "Y is preferred over Z because [reason]. [^[inferred] if the rationale was implied, not stated explicitly]"

Apply provenance markers per `~/.claude/doc/doc_wiki_schema.md`:
- *Extracted* — explicitly stated in the conversation (no marker)
- *Inferred* — generalized or synthesized from the conversation → `^[inferred]`
- *Ambiguous* — disputed, uncertain, or contradictory → `^[ambiguous]`

## Step 4: Generate a Slug and Title

Derive a clear, descriptive title from the content. Slugify it:
- Lowercase, words separated by hyphens
- Max 50 characters
- Avoid dates in the slug (the frontmatter has `created`)

## Step 5: Write the Wiki Note

Create the file at the target path with required frontmatter:

```yaml
---
title: >-
  <Title>
category: <synthesis|concepts|references|journal|skills>
tags: [<2-5 domain tags already used in the vault's index.md>]
sources:
  - conversation:<ISO-date>
created: <ISO-8601 timestamp>
updated: <ISO-8601 timestamp>
summary: >-
  <1-2 sentences, ≤200 chars, answering "what knowledge does this page hold?">
provenance:
  extracted: 0.X
  inferred: 0.X
  ambiguous: 0.X
base_confidence: 0.42           # the formula's fixed output for a single session-transcript source.
                                # With more distinct sources, recompute per the Confidence formula in
                                # `~/.claude/doc/doc_wiki_schema.md` (never from the `_raw/` table)
lifecycle: draft                # floor — captures stay here until a later pass reads the body and
                                # ranks them per `~/.claude/doc/doc_wiki_lifecycle_rubric.md`
lifecycle_changed: <ISO date today>
---
```

Body structure by type:

**synthesis / decision:**
```markdown
# Title

## Context
<What prompted this — the problem or question being addressed>

## Finding / Decision
<The core knowledge or conclusion>

## Reasoning
<Why this is the case or why this choice was made>

## Implications
<What follows from this — what to watch for, next steps, trade-offs>

## Related
<[[wikilinks]] to connected pages>
```

**concept:**
```markdown
# Title

<Definition in one clear sentence.>

## What It Is
<Explanation of the concept>

## How It Works
<Mechanism or structure>

## When to Use
<Applicability, conditions, trade-offs>

## Related
<[[wikilinks]]>
```

**source:**
```markdown
# Title

> Source: <title or URL>

## What It Covers
<What the source is about>

## Key Points
<Bulleted claims with provenance markers>

## Open Questions
<What it raises but doesn't answer — omit if none>

## Related
<[[wikilinks]]>
```

**session:**
```markdown
# Title

*Session captured: <date>*

## Topics Covered
<Brief list>

## Key Takeaways
<The 3-5 most important things that emerged>

## Decisions Made
<Any explicit decisions, with rationale>

## Open Questions
<What remains unresolved>

## Related
<[[wikilinks]]>
```

Every note must link to at least 2 existing wiki pages. Search `index.md` before writing. If fewer than 2 related pages exist, create minimal stubs for the most important concepts referenced.

## Step 6: Update Tracking Files

**`index.md`** — Add the new page under its category section. One entry is one line: the page's `summary:` field verbatim (≤200 chars). Never grow an entry past that — if the text is too long, fix the page's `summary:`, not the index entry (`wiki-lint` already flags summaries over 200 chars).

**`log.md`** — Append:
```
- [TIMESTAMP] CAPTURE type=<type> page="<path>" title="<title>"
```

`[TIMESTAMP]` is the output of `date -u +%Y-%m-%dT%H:%M:%SZ` — run it and paste the result verbatim, never hand-write it (why: schema doc, `log.md`).

**`hot.md`** — change it only with `Edit`, never `Write`, one line at a time, keeping each `old_string` to the smallest span that covers the change and taking that text from what you just read. In **Recent Activity**: insert one line for what was just captured at the top of the list with one `Edit`, then delete the oldest entry with a **separate** `Edit` so the list stays at 3 operations — doing both in a single `Edit` would force the whole list into `old_string`. Then `Edit` the `updated` timestamp. Other sessions edit the same file concurrently, so a whole-file write silently drops whatever they added between your read and your write; `Edit` needs an exact match, so it fails loudly instead of eating their line — and the smaller the span, the less often it collides at all. **Do not copy the note's takeaways here** — they are already in the note, which is where they belong.

## Step 7: Confirm to User

Report the saved path and title:
```
Saved to: projects/<name>/synthesis/<slug>.md
Title: <Title>
Type: synthesis
```

## Quality Checklist

- [ ] Content rewritten as declarative knowledge (not a chat transcript)
- [ ] Type classified correctly; target path is in the right folder
- [ ] Frontmatter complete with title, category, tags, sources, summary, provenance
- [ ] At least 2 wikilinks to existing pages
- [ ] `index.md`, `log.md`, and `hot.md` updated
- [ ] Confirmed save path to user
