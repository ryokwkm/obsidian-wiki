---
name: wiki-update
description: 現在のプロジェクトの知識を Obsidian wiki へ同期する。どのプロジェクトからでも使え、「wiki を更新して」「wiki に同期して」「これを wiki に保存して」「obsidian を更新して」や英語の "update wiki" / "sync to wiki" / "save this to my wiki" と言われたとき、作業してきた内容をナレッジベースへ蒸留したいときに使う。「〜の仕様書を作って」「〜をドキュメント化して」「〜の doc を作って」と言われたときや、単一のファイル・概念について仕様書やドキュメントを書くよう頼まれたときも、独立した `doc_*.md` を生成するのではなく、そのファイル/概念を wiki へ蒸留する。どこにいても vault へ知識を押し込めるクロスプロジェクトな skill。
---

# Wiki Update — Sync Any Project to Your Wiki

You are distilling knowledge from the current project into the user's Obsidian wiki. This skill works from any project directory, not just the obsidian-wiki repo.

## Before You Start

1. **Resolve config** — use `OBSIDIAN_VAULT_PATH` if it is already exported (shell rc / direnv / parent process). Otherwise walk up from CWD to `$HOME` for a `.env` containing `OBSIDIAN_VAULT_PATH=` and take the first match. If neither exists, stop and tell the user to set it in `.claude/settings.json` (`env`), shell rc, or direnv — never hard-code a path or guess a vault. **Which vault to write is a per-project setting, not a global one** — it is configured repo by repo, so do not assume a session already carries it. Read `OBSIDIAN_LINK_FORMAT` the same way (`wikilink` default, or `markdown`). Works from any project directory.
2. Read `$OBSIDIAN_VAULT_PATH/.manifest.json` to check if this project has been synced before.
3. Find out what the wiki already contains **without reading `index.md` whole.** In a mature vault `index.md` runs to tens of kilobytes, which makes a blind full read the most expensive thing this skill does. Follow the Retrieval Primitives table in `~/.claude/doc/doc_wiki_schema.md`: `Grep` `index.md` for the project name and for each concept you are about to write, then read the `summary:` field of the few pages that match. Read `index.md` in full only if those greps come back empty and you still need the shape of the vault.

When writing internal links in Steps 4–5, apply the format that the resolved `OBSIDIAN_LINK_FORMAT` selects — see the Link Format section of `~/.claude/doc/doc_wiki_schema.md`.

## Step 1: Understand the Project

Figure out what this project is by scanning the current working directory:

- `README.md`, docs/, any markdown files
- Source structure (frameworks, languages, key abstractions)
- `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml` or whatever defines the project
- Git log (focus on commit messages that signal decisions, not "fix typo" stuff)
- Claude memory files if they exist (`.claude/` in the project)

Derive a clean project name from the directory name.

## Step 2: Compute the Delta

Check `.manifest.json` for this project:

- **First time?** Full scan. Everything is new.
- **Synced before?** Look at `last_commit_synced`. Before computing the delta, verify the stored SHA is still reachable:
  ```bash
  git merge-base --is-ancestor <last_commit_synced> HEAD
  ```
  - **Exit 0 (ancestor):** Safe. Run `git log <last_commit_synced>..HEAD --oneline` to see what changed.
  - **Exit 1 (not an ancestor — rebase or force-push occurred):** The stored SHA is no longer in this branch's history. Warn the user: *"Stored commit `<sha>` is no longer reachable — branch may have been rebased or force-pushed. Falling back to full scan."* Then treat as first-time sync: re-scan everything and update `last_commit_synced` to the current HEAD SHA at the end of Step 6.

If nothing meaningful changed since last sync, stop (see Step 7 for what to say).

## Step 3: Decide What to Distill

This is the core question from Karpathy's pattern: **what would you want to know about this project if you came back in 3 months with zero context?**

Worth distilling:

- Architecture decisions and *why* they were made
- Patterns discovered while building (things you'd Google again otherwise)
- What tools, services, APIs the project depends on and how they're wired together
- Key abstractions, how they connect, what the mental model is
- Trade-offs that were evaluated, what was picked and why
- Things learned while building that aren't obvious from reading the code

Not worth distilling:

- File listings, boilerplate, config that's obvious
- Individual bug fixes with no broader lesson
- Dependency versions, lock file contents
- Implementation details the code already says clearly
- Routine changes anyone could read from the diff

The heuristic: **if reading the codebase answers the question, don't wiki it. If you'd have to re-derive the reasoning by reading git blame across 20 commits, wiki it.**

## Step 4: Distill into Wiki Pages

### Project-specific knowledge

Goes under `$VAULT/projects/<project-name>/`:

```
projects/<project-name>/
├── <project-name>.md          ← project overview (named after the project, NOT _project.md)
├── concepts/                  ← project-specific ideas, architectures
├── skills/                    ← project-specific how-tos, patterns
└── references/                ← project-specific source summaries
```

The overview page (`<project-name>.md`) should have:
- What the project is (one paragraph)
- Key concepts and how they connect
- Links to project-specific and global wiki pages

### Global knowledge

Things that aren't project-specific go in the global categories:

| What you found | Where it goes |
|---|---|
| A general concept learned | `concepts/` |
| A reusable pattern or technique | `skills/` |
| A tool/service/person | `entities/` |
| Cross-project analysis | `synthesis/` |

### Page format

Every page needs YAML frontmatter. Use folded scalar syntax (`title: >-` / `summary: >-`) — it keeps
the frontmatter parser-safe across punctuation (`:`, `#`, quotes) without escaping rules; indent the
contents by two spaces:

```markdown
---
title: >-
    Page Title
category: concepts
tags: [tag1, tag2]
sources: [projects/<project-name>]
summary: >-
    One or two sentences (≤200 chars) describing what this page covers.
provenance:
  extracted: <computed>         # 本文のマーカー実数から出す。下の数字は書かない
  inferred: <computed>
  ambiguous: <computed>
base_confidence: <computed>     # 式の出力のみ。証拠が強いからと上げない
lifecycle: draft                # floor. This skill distills work you just did, so the evidence is usually
                                # already in hand — promote per `~/.claude/doc/doc_wiki_lifecycle_rubric.md`
                                # and add `lifecycle_evidence` + `evidence_at`. Never copy a neighbour's rank.
lifecycle_changed: TIMESTAMP_DATE
created: TIMESTAMP
updated: TIMESTAMP
---

# Page Title

- A fact the codebase or a doc actually states.
- A reason the design works this way. ^[inferred]

Use [[wikilinks]] to connect to other pages.
```

**`provenance` と `base_confidence` は必ず計算して書く。テンプレの数字を残さない。**
2026-09-02 の lint で、この 2 つが vault 全体（32 ページ）で式から外れていた。原因は 2 つとも
「それらしい定数を写した」こと ——

- `provenance` は本文の `^[inferred]` / `^[ambiguous]` を**実際に数える**。分母はコードフェンス・表・
  見出し・引用を除いた箇条書き＋文。旧テンプレが持っていた `0.6 / 0.35 / 0.05` は
  wiki-capture が持つ raw 用キャリブレーション表の 1 行で、**あの表は `_raw/` 専用**
  （その表自身が "Never carry a number from this table onto a promoted page" と明記している）
- `base_confidence` は `~/.claude/doc/doc_wiki_schema.md` の式の出力**だけ**。証拠が強いページを
  手心で上げてはいけない —— 証拠の強さを載せる軸は `lifecycle` で、そちらに既に入っている。
  二重に載せると `lifecycle` と相関して情報が減るうえ、Rule 12e が毎回ドリフトとして鳴る

**Write a `summary:` frontmatter field** on every new/updated page (1–2 sentences, ≤200 chars), using `>-` folded style. For project sync, a good summary answers "what does this page tell me about the project I wouldn't guess from its title?" This field powers cheap retrieval by `wiki-query`.

**Apply provenance markers** per the Provenance Markers section of `~/.claude/doc/doc_wiki_schema.md`. For project sync specifically:

- **Extracted** — anything visible in the code, config, or a doc/commit message: file structure, dependencies, function signatures, what a file does.
- **Inferred** — *why* a decision was made, design rationale, trade-offs, "the team chose X because Y" — unless a commit message, doc, or ADR states it explicitly.
- **Ambiguous** — when the code and docs disagree, or when there's clearly an in-progress migration with two patterns living side by side.

Compute the rough fractions and write the `provenance:` block on every new/updated page.

### Updating vs creating

- If a page already exists in the vault, **merge** new information into it. Don't create duplicates.
- If you're adding to an existing page, update the `updated` timestamp and add the new source.
- Check `index.md` to see what's already there before creating anything new.

## Step 5: Cross-link

After creating/updating pages:

- Add `[[wikilinks]]` from new pages to existing related pages
- Add `[[wikilinks]]` from existing pages back to the new ones where relevant
- Link the project overview to all project-specific pages and relevant global pages

## Step 6: Update Tracking

### Update `.manifest.json`

Add or update this project's entry **key by key — never replace the object.** Other skills and other
sessions write the same entry. Keep every key you do not recognize, and write with a targeted `jq`
assignment (`.projects["<name>"] += {…}`), not a whole-object assignment. The key set, the jq patterns,
and what breaks when a key is dropped are in `~/.claude/doc/doc_wiki_schema.md` — do not invent fields here.

```json
{
  "projects": {
    "<project-name>": {
      "source_cwd": "/absolute/path/to/project",
      "last_synced": "TIMESTAMP",
      "last_commit_synced": "abc123f",
      "pages_in_vault": ["projects/<project-name>/<project-name>.md", "..."],
      "note": "free-text remark about this project's sync, if there is one"
    }
  }
}
```

### Update `index.md`

Add entries for any new pages created. One entry is one line: the page's `summary:` field verbatim (≤200 chars). Never grow an entry past that — if the text is too long, fix the page's `summary:`, not the index entry (`wiki-lint` already flags summaries over 200 chars).

### Update `log.md`

Append:
```
- [TIMESTAMP] WIKI_UPDATE project=<project-name> pages_updated=X pages_created=Y source_cwd=/path/to/project
```

`[TIMESTAMP]` is the output of `date -u +%Y-%m-%dT%H:%M:%SZ` — run it and paste the result verbatim, never hand-write it (why: schema doc, `log.md`).

### Update `hot.md`

**`hot.md` is a cache: one line per entry, nothing accumulates here.** Other sessions write to it while
you work, so **change it only with `Edit` on the smallest span that covers your change, never `Write`**
(why: schema doc, Special Files).

- Read only what you are about to change: `Grep -A 6 "## Recent Activity" $OBSIDIAN_VAULT_PATH/hot.md` returns the lines to replace without loading the file.
- **Recent Activity** — this section only: one line per operation, newest first, last 3 only. Insert your line at the top with one `Edit`, then drop the oldest line with a **separate** `Edit` — doing both at once forces the whole section into `old_string`.
- **Active Threads** — this section only: one line per thread, 3 max, one `Edit` per line. Drop threads that are no longer active instead of keeping them alongside the new one. **If the section is not in the file, leave it out** — do not add it.
- **Insights, takeaways and decisions do not go here.** They belong in the page body this sync just wrote — that is what the distillation was for. Duplicating them into `hot.md` is how it once grew unbounded.
  - In the page, keep it to **one line**, placed in the section it is about rather than appended to the end, and **only if the page does not already say it in other words** — a takeaway restated somewhere else is the same duplication in a new location.
- `Edit` the frontmatter `updated` timestamp with a separate `Edit` in the same pass.

Write the entry conceptually, not as a file list: "Synced obsidian-wiki — added wiki-capture, whose new capability is turning a live conversation into a wiki page."

If `hot.md` does not exist, create it with exactly the skeleton in `~/.claude/doc/doc_wiki_schema.md`
(Special Files → `hot.md`). There is no takeaways section — that is deliberate, not an omission.

**Do not refresh the QMD search index here.** The markdown vault is the source of truth, and the SessionStart hook re-indexes every vault unconditionally — the pages you just wrote become searchable at the next session's entry point. Until then `wiki-query` falls back to `Grep`, so nothing is lost by leaving the index alone. Never run `qmd update` / `qmd embed` as part of a sync.

## Step 7: Report

This skill usually runs unprompted at the end of some other task, so whatever it prints competes with the answer to what the user actually asked. Keep it out of the way.

- **One line, at the very end**, in the user's language: `wiki: <page> を更新` — or `wiki: 更新なし` when Step 2 found nothing.
- **Do not describe** the steps taken, the pages' structure, or the `index.md` / `hot.md` / `log.md` diffs. The vault is the artifact; the report is not. Anything worth saying at length belongs in the page you just wrote.
- **Failure gets one extra line** naming what broke. Never roll back the rest of the sync to report it.

## Tips

- **Be aggressive about merging.** If the project uses React Server Components, don't create a new page if `concepts/react-server-components.md` already exists. Update the existing one and add this project as a source.
- **Tag by the conventions, not by feel.** Reuse tags that pages in the vault already carry, and follow the tag rules in `~/.claude/doc/doc_wiki_schema.md` (how many tags a page may carry, and the reserved `visibility/` namespace) instead of inventing a new vocabulary per project.
- **Don't copy code.** Distill the *knowledge*, not the implementation. "This project uses a debounced search pattern with 300ms delay" is useful. Pasting the actual debounce function is not.
- **Project overview is the anchor.** The `<project-name>.md` file is what you'd read to get oriented. Make it good.
