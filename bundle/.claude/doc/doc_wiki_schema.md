# wiki スキーマ — vault へ書く / 引くときの規約

wiki バンドルの skill が共有する**データ規約**。ページの frontmatter、vault ルートの特殊ファイル、型付きリンク、
retrieval のコスト順序を定める。**vault へ書く直前**（ページ作成・frontmatter 更新・`index.md` / `log.md` /
`.manifest.json` の更新）と、**vault から引く直前**（どの primitive で読むかを決めるとき）に、
該当する節だけを読む。頭から通読する必要はない。

`lifecycle` の値・序列・判定手順だけはここに無い。唯一の正典は `~/.claude/doc/doc_wiki_lifecycle_rubric.md`
（→ Confidence and Lifecycle 節）。**値の一覧をこの doc や skill 本文へ書き写さないこと** —— 正典が 2 箇所に
分裂していたことが 2026-08-12 に見つかった 66 ページの誤値（`active`）の直接原因だった。

## 見出し索引

| 節 | 何を決めるか |
|---|---|
| Wiki Organization | カテゴリ（何の知識か）と `projects/`（どこから来た知識か）のディレクトリ構造 |
| Special Files | `index.md` / `log.md` / `.manifest.json` の形式・書き込み規約と、派生ビュー（`index.md` / `hot.md`）の同時更新の扱い |
| Page Template | 新規ページの frontmatter + 本文の雛形 |
| Reserved System Tags | `visibility/` 予約タグ 3 種とタグ語彙の置き場（枚数・形式に機械検査が無いことの注記付き） |
| Provenance Markers | `^[inferred]` / `^[ambiguous]` と frontmatter の `provenance:` |
| Typed Relationships | `relationships:` の型（10 概念・16 綴り）と、文脈から型を推論する表 |
| Confidence and Lifecycle | `base_confidence` の算出式と、lifecycle 正典へのポインタ |
| Importance Tiering | `tier:` 3 段と昇格・降格の閾値（昇格に書き手がいないことの注記付き） |
| Retrieval Primitives | vault を読むときのコスト順序（安い順に試す） |
| Link Format | `OBSIDIAN_LINK_FORMAT` = `wikilink` / `markdown` の生成規則 |

## Wiki Organization

The vault has two levels of structure: **categories** (what kind of knowledge) and **projects** (where the knowledge came from).

### Categories

Organize pages into these default categories (customizable via `OBSIDIAN_CATEGORIES`):

| Category | Purpose | Example |
|---|---|---|
| `concepts/` | Ideas, theories, mental models | `concepts/transformer-architecture.md` |
| `entities/` | People, orgs, tools, projects | `entities/andrej-karpathy.md` |
| `skills/` | How-to knowledge, procedures | `skills/fine-tuning-llms.md` |
| `references/` | Summaries of specific sources; academic papers use the richer paper deep-dive template carried by `wiki-ingest` | `references/attention-is-all-you-need.md` |
| `synthesis/` | Cross-cutting analysis across sources | `synthesis/scaling-laws-debate.md` |
| `journal/` | Timestamped observations, session logs | `journal/2024-03-15.md` |

### Projects

Knowledge often belongs to a specific project. The `projects/` directory mirrors this:

```
$OBSIDIAN_VAULT_PATH/
├── projects/
│   ├── my-project/
│   │   ├── my-project.md      ← project overview (named after project)
│   │   ├── concepts/          ← project-scoped category pages
│   │   ├── skills/
│   │   └── ...
│   ├── another-project/
│   │   └── ...
│   └── side-project/
│       └── ...
├── concepts/                   ← global (cross-project) knowledge
├── entities/
├── skills/
└── ...
```

**When knowledge is project-specific** (a debugging technique that only applies to one codebase, a project-specific architecture decision), put it under `projects/<project-name>/<category>/`.

**When knowledge is general** (a concept like "React Server Components", a person like "Andrej Karpathy", a widely applicable skill), put it in the global category directory.

**Cross-referencing:** Project pages should `[[wikilink]]` to global pages and vice versa. A project's overview page should link to the key concept, skill, and entity pages relevant to that project — whether they live under the project or globally.

**Naming rule:** The project overview file must be named `<project-name>.md`, not `_project.md`. Obsidian's graph view uses the filename as the node label — `_project.md` makes every project appear as `_project` in the graph, making it unreadable. So `projects/my-project/my-project.md`, `projects/another-project/another-project.md`, etc.

Each project directory has an overview page structured like this:

```markdown
---
title: My Project
category: project
tags: [ai, web, backend]
source_path: ~/.claude/projects/-Users-name-Documents-projects-my-project
created: 2026-03-01T00:00:00Z
updated: 2026-04-06T00:00:00Z
---

# My Project

One-paragraph summary of what this project is.

## Key Concepts
- [[concepts/some-api]] — used for core functionality
- [[projects/my-project/concepts/main-architecture]] — project-specific architecture

## Related
- [[entities/some-service]] — deployment platform
```

## Special Files

Every wiki has these files at its root.

**派生ビュー（`index.md` / `hot.md`）は捨てて作り直せるキャッシュで、蒸留物の置き場ではない。** バイト上限は
env（`WIKI_INDEX_MAX_BYTES` / `WIKI_HOT_MAX_BYTES`）で測られる。超過したら上限を上げるのではなく、そこへ
書き足している側を直す。

**同時更新の前提**: vault は複数セッションが同時に触る。`index.md` / `hot.md` は**該当箇所だけを `Edit` で
書き換える**（`old_string` は直前に読んだテキストから採り、変更に必要な最小限のスパンに留める。ファイル全体を
`Write` で書き戻すと、読んでから書くまでの間に入った他セッションの追記が黙って消える。`Edit` は完全一致が要るので、
競合しても黙って消さずに失敗する —— それが望ましい挙動で、スパンが小さいほどその空振りも減る）。
`.manifest.json` は読んで考えてから書くのではなく、`jq` の 1 コマンドで読んで即書く（窓を秒未満にする）。

### `hot.md`
A ~500-word cache of recent activity — one line per entry, nothing accumulates here. Insights,
takeaways and decisions belong in page bodies, never in `hot.md`. If it does not exist, any writing
skill creates it with exactly this skeleton. **There is no takeaways section — that is deliberate,
not an omission:**

```markdown
---
title: Hot Cache
updated: TIMESTAMP
---
## Recent Activity
## Active Threads
## Flagged Contradictions
```

### `index.md`
A content-oriented catalog organized by category. Each entry has a one-line summary and tags. Update it after every ingest operation. Format:

```markdown
# Wiki Index

## Concepts
- [[transformer-architecture]] — The dominant architecture for sequence modeling ( #ml #architecture)
- [[attention-mechanism]] — Core building block of transformers ( #ml #fundamentals)

## Entities
- [[andrej-karpathy]] — AI researcher, educator, former Tesla AI director ( #person #ml)
```
**Format rule**: Add a space after the opening `(` and tags.
❌ Don't: `description (#tag)` — breaks tag parsing
✅ Do: `description ( #tag)` — proper spacing and tag parsing

One entry is one line: the page's `summary:` field verbatim (≤200 chars). Never grow an entry past that — if the text is too long, fix the page's `summary:`, not the index entry.

### `log.md`
Chronological append-only record tracking every operation. Each entry is parseable:

```markdown
## Log

- [2024-03-15T10:30:42Z] INGEST source="papers/attention.pdf" pages_updated=12 pages_created=3
- [2024-03-15T11:04:07Z] QUERY query="How do transformers handle long sequences?" result_pages=4
- [2024-03-16T09:12:33Z] LINT issues_found=2 orphans=1 contradictions=1
- [2024-03-17T10:47:19Z] ARCHIVE reason="rebuild" pages=87 destination="_archives/..."
- [2024-03-17T10:52:08Z] REBUILD archived_to="_archives/..." previous_pages=87
```

**Every timestamp is the output of `date -u +%Y-%m-%dT%H:%M:%SZ`** — run it and paste the result verbatim. Never hand-write one: hand-rounded values (`:00` seconds) sort out of order against real ones, so `tail -N` returns the wrong set. The examples above carry real-looking seconds for exactly this reason.

⚠️ **The key sets in the examples above are abbreviated.** Each writing skill owns the full key set for its own verb and states it in its own `SKILL.md` — `wiki-lint` in particular requires every one of its keys on every run, and the `LINT` line above shows only three of them. Copy the shape (`- [TIMESTAMP] VERB key=value …`) from here; take the keys from the skill that writes the line.

**Reading it back**: `log.md` is append-only and unbounded (100 kB+ ≒ 25k tokens on an active vault), so never read it whole — take the tail with `grep '^- \[' "$OBSIDIAN_VAULT_PATH/log.md" | tail -N`. Grep for entry lines rather than plain `tail`: the file contains blank lines, so a raw `tail -N` returns fewer than N entries. When filtering by period, compare only the leading `YYYY-MM-DD` — entries mix `Z`, `+0900`, and date-only forms, so full-timestamp comparison is unreliable.

### `.manifest.json`
Tracks what has been ingested — source files, per-project sync state, and which wiki pages each produced. This is the backbone of the delta system.

The manifest enables:
- **Delta computation** — what's new or modified since last ingest
- **Append mode** — only process the delta, not everything
- **Audit** — which source produced which wiki page
- **Staleness detection** — source changed but wiki page hasn't been updated

**実 vault が採っている形**（21 sources / 2 projects の実測に基づく。名前と値は例示用に置き換えてある）。
これを正とする:

```json
{
  "version": 1,
  "project": "my-project",
  "last_updated": "2026-08-12T11:53:32Z",
  "sources": {
    "README.md": {
      "ingested_at": "2026-06-24T09:21:26Z",
      "size_bytes": 20491,
      "modified_at": "2026-06-22T01:23:58Z",
      "content_hash": "sha256:946163e3fb…",
      "source_type": "document",
      "project": "my-project",
      "pages_created": ["entities/my-project-repo.md", "synthesis/claude-config-hierarchy.md"],
      "pages_updated": []
    }
  },
  "projects": {
    "my-project": {
      "source_cwd": "/Users/you/projects/my-project",
      "last_synced": "2026-08-12T11:53:32Z",
      "last_commit_synced": "32d309a",
      "pages_in_vault": ["concepts/vault-topology.md", "…"],
      "note": "この同期で何を蒸留したか / 未蒸留の残り（自由文）"
    }
  },
  "stats": { "total_sources_ingested": 21, "total_pages": 29 }
}
```

**注意すべき実測事実**:

- **`sources` は無いことがある。** プロジェクト同期だけで育った vault は `projects` しか持たない
  （実在する。破損ではない）。**読む側は全キーを optional として扱う**（`sources` が無いなら
  「ソース単位の履歴は無い」と解釈し、作り直さない）。
- **`projects.<name>` の共通キーは 5 つ**（`source_cwd` / `last_synced` / `last_commit_synced` /
  `pages_in_vault` / `note`。`note` だけは欠けている実例がある）。ただし **vault 固有の追加キーが実在する**
  —— 実測では `source_repos`（複数リポジトリごとの同期済み SHA）と `snapshot_date` を持つ vault があった。
  **知らないキーは必ずそのまま保持して書き戻す**（`source_repos` は `last_commit_synced` と同じ delta 判定の
  状態なので、落とすと次回が全再スキャンになる）。
- **`last_synced` は表記が混在する**（`Z` / `+0900` / 日付のみ、が実データに同居する）。
  比較するときは先頭の `YYYY-MM-DD` だけを見る。書くときは `date -u +%Y-%m-%dT%H:%M:%SZ` の出力をそのまま貼る。

**`projects` エントリの書き込みは「キー単位のマージ」。オブジェクトごと置き換えてはならない。**

同じリポジトリのエントリを複数の skill が書く（プロジェクト同期と履歴取り込みが同じキーに当たる）。
テンプレートから作った新しいオブジェクトを
代入すると、そのエントリが持っていた他のキーが黙って消える。**落ちると何が壊れるか**:

- `last_commit_synced` を落とすと、次回の同期が `git merge-base --is-ancestor <last_commit_synced> HEAD` を
  引けず、delta 計算が「初回同期＝全走査」へ落ちる（`source_repos` を持つ vault ではそのキーが同じ役割を
  担うので、落とせば同じことが起きる）
- `source_cwd` を落とすと、`wiki-query` が答えに添える `Source code:` 行が永久に解決しなくなる
- `pages_in_vault` を落とすと、そのプロジェクトが vault に持つページの一覧が失われる

**書き方**: 読んで考えてから書くのではなく、`jq` の 1 コマンドで読んで即書く（他セッションの更新を消す窓を
秒未満にする）。**必ず加算代入 `+=` で、更新するキーだけを渡す**:

```bash
m="$OBSIDIAN_VAULT_PATH/.manifest.json"

# ✅ 既存キーを残したままマージ（jq は入力ファイルへ直接書けないので tmp 経由で差し替える）
jq '.projects["my-project"] += {"last_synced": "2026-08-12T11:53:32Z", "last_commit_synced": "32d309a"}' \
  "$m" > "$TMPDIR/manifest.json" && mv "$TMPDIR/manifest.json" "$m"

# ✅ pages_in_vault は「置換」ではなく追記して重複を除く（`+=` に配列を渡すと丸ごと入れ替わる）
jq --argjson new '["concepts/foo.md"]' \
  '.projects["my-project"].pages_in_vault = ((.projects["my-project"].pages_in_vault // []) + $new | unique)' \
  "$m" > "$TMPDIR/manifest.json" && mv "$TMPDIR/manifest.json" "$m"

# ❌ 丸ごと代入 —— 書かなかったキーが全部消える
jq '.projects["my-project"] = { … }' …
```

プロジェクト名は manifest の既存キーに合わせる（`my-project` を `myproject` として別立てしない）。
1 回の実行あたりの件数（会話数・ファイル数など）は `projects` に置かない —— `sources` 側の各エントリと
`log.md` の行が既に持っており、恒久的に残したい所感は `note`（自由文）へ書く。

**Source keys: expand `~`, but never rewrite a relative key into an absolute one.**

The manifest is keyed by the raw string, so the *same file* under two spellings is tracked
twice, and the delta check then re-ingests it because the lookup misses the other form.
There are two spellings to worry about, and they need opposite treatment:

- **`~` and env vars — always expand** before comparing or writing. `~/.claude/x.jsonl`
  and `/Users/me/.claude/x.jsonl` are the same file, and nothing is lost by picking one.
- **Project-relative keys — keep exactly as they are.** These are the normal case, not a
  defect: keys like `README.md` or `.claude/doc/doc_dq.md` are relative to the ingest root
  because that is what the ingesting project passed in. Rewriting them to absolute paths
  makes every existing entry miss on the next delta check, and the whole vault gets
  re-ingested. (In the measured vault, every manifest entry was relative.)

**To look up a path that may be recorded under a relative key:** index the relative keys
by basename, then accept an entry whose key is a path *suffix* of the path you have.
`concepts/foo.md` matches the key `foo.md` and the key `concepts/foo.md`, but not
`other/foo.md`. Do this before deciding a source is new.

Never "normalize" an existing manifest into absolute form as a cleanup step. If you find
both forms of the *same* file, merge those two entries and keep the newest `ingested_at` —
that is the only rewrite worth doing.

**Recording provenance.** When you write a manifest entry, populate `pages_created` and `pages_updated` with the vault-relative page paths that source contributed to. This is what makes re-ingestion (when a source changes) able to find the pages to revisit, instead of guessing.

## Page Template

When creating a new wiki page, use this structure:

```markdown
---
title: Page Title
category: concepts
tags: [ml, architecture]
aliases: [alternate name]
relationships:
  - target: "[[concepts/related-concept]]"
    type: extends
sources: [papers/attention.pdf]
summary: One or two sentences, ≤200 chars, so a reader (or another skill) can preview this page without opening it.
provenance:
  extracted: 0.72
  inferred: 0.25
  ambiguous: 0.03
base_confidence: 0.65
lifecycle: draft               # the floor. Promote per ~/.claude/doc/doc_wiki_lifecycle_rubric.md — a rank above draft also requires lifecycle_evidence + evidence_at
lifecycle_changed: 2024-03-15
tier: supporting
created: 2024-03-15T10:30:42Z
updated: 2024-03-15T10:30:42Z
---

# Page Title

One-paragraph summary of what this page covers.

## Key Ideas

- The source's central claim, paraphrased directly.
- A generalization the source implies but doesn't state outright. ^[inferred]
- A figure two sources disagree on. ^[ambiguous]

Use [[wikilinks]] to connect to related pages.

## Open Questions

Things that are unresolved or need more sources.

## Sources

- [[references/attention-is-all-you-need]] — Original paper
```

**`## Key Ideas` / `## Open Questions` はこの雛形（＝新規ページ）の中だけの見出しで、既存ページへの挿入位置として
参照してはならない**（実 vault にはほぼ存在しない見出し）。既存ページへ 1 行足すときは、**その主張が属する
箇所の直後**に置き（見つからなければ本文末尾）、特定の見出しの存在を前提にしないこと。

**`created` / `updated`** are the output of `date -u +%Y-%m-%dT%H:%M:%SZ`, same as `log.md` entries — run it, never hand-write. Set `updated` on every edit: a page without it drops out of staleness detection entirely, so it can never be reported as stale.

## Reserved System Tags

タグの規約（**1 ページ最大 5 タグ**・**lowercase / hyphen 区切り**・既存タグの再利用を優先）は
**この doc が正典**。⚠️ **`$OBSIDIAN_VAULT_PATH/_meta/taxonomy.md` を読もうとしないこと・そこから
タグ語彙や上限を採らないこと** —— そのファイルはどの vault にも存在しない。新しいタグを付けるときは
`index.md` の既存タグを見て揃える。

⚠️ **書き込み時に走る機械検査は無い。** 上限・形式の検出は `wiki-lint` の Check 8a
（Over-Tagged and Malformed Tags）が**監査時に報告するだけ**で、書く瞬間には誰も止めてくれない。
検査されている前提で書かないこと（実 vault には検査導入前の超過が残っている）。

以下の `visibility/` は上の 5 タグ枠とは別枠の予約グループで、alias 正規化の対象にしない。

`visibility/` is a reserved tag group with special rules. These tags are **not** domain or type tags and are managed separately from the taxonomy vocabulary:

| Tag | Purpose |
|---|---|
| `visibility/public` | Explicitly public — shown in all modes (same as no tag) |
| `visibility/internal` | Team-only — excluded in filtered query/export mode |
| `visibility/pii` | Sensitive data — excluded in filtered query/export mode |

**Rules for `visibility/` tags:**
- They do **not** count toward the 5-tag limit
- Only one `visibility/` tag per page
- Omit entirely when content is clearly public — no tag needed
- Never add `visibility/internal` just because content is technical; use it only for genuinely team-restricted knowledge
- When auditing tags, report `visibility/` usage separately — do not flag them as unknown or non-canonical

## Provenance Markers

Every claim on a wiki page has one of three provenance states. Mark them inline so the reader (and future ingest passes) can tell signal from synthesis.

| State | Marker | Meaning |
|---|---|---|
| **Extracted** | *(no marker — default)* | A paraphrase of something a source actually says. |
| **Inferred** | `^[inferred]` suffix | An LLM-synthesized claim — a connection, generalization, or implication the source doesn't state directly. |
| **Ambiguous** | `^[ambiguous]` suffix | Sources disagree, or the source is unclear. |

Example:

```markdown
- Transformers parallelize across positions, unlike RNNs.
- This is why they scale better on modern hardware. ^[inferred]
- GPT-4 was trained on roughly 13T tokens. ^[ambiguous]
```

(`^[...]` renders cleanly in Obsidian, never collides with `[[wikilinks]]`, keeps one bullet one
bullet, and the extracted-by-default rule keeps unmarked pages valid.)

**Frontmatter summary:** Optionally surface the rough mix at the page level so the user can scan for speculation-heavy pages without reading them:

```yaml
provenance:
  extracted: 0.72   # rough fraction of sentences/bullets with no marker
  inferred: 0.25
  ambiguous: 0.03
```

These are best-effort numbers written by the ingest skill at create/update time. `wiki-lint` recomputes them and flags drift. The block is optional — pages without it are treated as fully extracted by convention.

## Typed Relationships

Plain `[[wikilinks]]` in page bodies carry no semantic weight — they indicate "related to" but not *how*. The optional `relationships:` frontmatter block adds typed, directional edges to the knowledge graph.

### The `relationships:` block

```yaml
relationships:
  - target: "[[Transformer Architecture]]"
    type: extends
  - target: "[[LSTM]]"
    type: contradicts
  - target: "[[Attention Mechanism]]"
    type: implements
```

Each entry has two required fields:
- `target` — a wikilink to the related page. **Always wikilink syntax (`[[path/to/page]]`), regardless of `OBSIDIAN_LINK_FORMAT`** — that setting controls body content only. Frontmatter stays wikilink so multi-hop traversal can resolve edges from a single frontmatter grep.
- `type` — one of the allowed semantic types below

### Allowed relationship types

The enum holds **10 concepts across 16 spellings**: 2 symmetric types, 6 directional concepts (each with a forward and a reverse spelling), and 2 forward-only types.

**Symmetric (no direction):**

| Type | Meaning | Example |
|---|---|---|
| `related_to` | Catch-all: related but no stronger type applies | Concept A is related to Concept B |
| `contradicts` | This page's claims conflict with or refute the target | Evidence A contradicts Evidence B |

**Directional (forward and reverse spellings are both official):**

| Forward (this page → target) | Reverse | Forward meaning | Example |
|---|---|---|---|
| `uses` | `used_by` | This page depends on or relies on the target | RAG uses Vector Databases |
| `extends` | `extended_by` | This page builds on the target | GPT extends Transformer Architecture |
| `implements` | `implemented_by` | This page is a concrete realisation of the target concept | BERT implements Masked Language Modelling |
| `elaborates` | `elaborated_by` | This page is the detailed version of the target — same subject, finer granularity | Implementation Notes elaborates Design Overview |
| `constrains` | `constrained_by` | This page constrains the target's design | Rate Limits constrains Retry Strategy |
| `part_of` | `has_part` | This page is a component of the target (the whole) | Attention Mechanism is part of Transformer Architecture |

A reverse spelling is the same edge read from the other side: `used_by` means the target depends on this page.

**Forward-only (no reverse spelling):**

| Type | Meaning | Example |
|---|---|---|
| `derived_from` | This page is based on or adapted from the target | Fine-tuning is derived from Transfer Learning |
| `replaces` | This page supersedes or deprecates the target | GPT-4 replaces GPT-3 |

`derived_from` has no reverse spelling because origin is naturally declared on the derived page. The reverse of `replaces` is deliberately not a type — see Rules.

Alias spellings from before this enum (`relates_to`, `supersedes`, `depends_on`, …) are normalised mechanically; that mapping table lives in the `wiki-lint` skill, not here.

### Inferring the type from context

When you add a wikilink and want to type it, scan the sentence containing the mention (or, for `## Related` entries, the page title and shared-tag context):

| Sentence pattern | Inferred type |
|---|---|
| "X uses / relies on / depends on / requires Y" | `uses` |
| "X extends / builds on Y" | `extends` |
| "X implements / is an implementation of Y" | `implements` |
| "X details / drills into Y" — X covers the same subject as overview Y at finer granularity | `elaborates` |
| "X constrains / restricts / places limits on Y's design" | `constrains` |
| "X is part of / is a component of Y" | `part_of` |
| "X contradicts / opposes / refutes / is at odds with Y" | `contradicts` |
| "X is derived from / based on / adapted from Y" | `derived_from` |
| "X replaces / supersedes / deprecates Y" | `replaces` |
| "X is used by Y", "X is implemented by Y" — the sentence reads from the target's side | the matching reverse spelling (`used_by`, `extended_by`, `implemented_by`, `elaborated_by`, `constrained_by`, `has_part`) |
| "X generalises Y" — X is the broader concept, Y the specific case that builds on it | `extended_by` (the passive "X is generalised by Y" is the opposite direction: `extends`) |
| Shared tags or cross-category inference with no directional cue | `related_to` |

If the surrounding context is ambiguous, or the link came from shared-tag matching with no in-body mention, default to `related_to`.

**Writing the block:** if `relationships:` already exists, append new entries without duplicating existing targets. If absent, add it after `aliases:` (or after `tags:` when `aliases:` is missing). Only add entries for links you added in this pass — never rewrite typed entries that were already there.

### Rules

- **Optional field** — omit the block entirely if no typed relationships are known. Untagged wikilinks remain valid and count as `related_to`.
- **Don't duplicate** — if `[[foo]]` already appears as an inline wikilink, the `relationships:` entry just enriches it with a type; it is not a second link.
- **Direction matters** — the page declaring the entry is the *source*; `target` is the destination. Only declare relationships from this page's perspective.
- **Don't fabricate** — only add a typed entry when the source material makes the relationship direction and type clear. When in doubt, use `related_to` or omit.
- **One edge per relationship** — reverse spellings exist so the edge can be declared from whichever page you happen to be editing, not so it can be declared twice. Never write the mirror-image entry on the other page as well. Mirror pairs that predate this rule are left as they are — the redundancy is harmless; do not delete one side during maintenance.
- **This table is the single canonical list** — never copy the type list into a skill body. The moment a second copy exists the enum drifts (the same rule the Lifecycle section applies to its rank list). Skills point at this section instead.
- **No skill may instruct writing a type outside this enum** — changing the enum is a schema decision, made here, never in a skill.
- **The reverse of `replaces` is not a type — deliberately** — the superseded page's canonical marking is `lifecycle: archived` plus the top-level `superseded_by:` field (see Confidence and Lifecycle), which lives outside `relationships:`. Never write `replaced_by` or `type: superseded_by`.

`wiki-query` reads this block: it surfaces the type in answers and walks the typed-edge graph for multi-hop "how is X connected to Y" path queries (bounded BFS over the `relationships:` adjacency, frontmatter-only).

## Confidence and Lifecycle

Every page carries two orthogonal trust signals plus an optional supersession link.

### Required fields

```yaml
base_confidence: 0.65             # [0.0, 1.0] — time-independent quality estimate. Stored once, recomputed on content change.
lifecycle: draft                  # evidence level — values and how to pick one: ~/.claude/doc/doc_wiki_lifecycle_rubric.md
lifecycle_evidence: "§3 の追試表"  # where the evidence lives. Required for every rank above `draft`
evidence_at: 2026-08-06           # ISO date the evidence was obtained. Required for every rank above `draft`
lifecycle_changed: 2026-08-12     # ISO date the rank last changed
# lifecycle_reason: "..."         # optional free-text — why the state changed; surfaced by wiki-query
# superseded_by: "[[new-page]]"   # wikilink; only when lifecycle=archived
```

`lifecycle_reason` and `superseded_by` are optional. Never fabricate them.

`lifecycle_evidence` and `evidence_at` are **required whenever `lifecycle` is above `draft`** — a rank asserts an action was taken, and these two fields are where the action is pinned. If you cannot fill them, you have no grounds to promote: leave the page at `draft`.

### Lifecycle — 正典は 1 ファイルだけ

`lifecycle` records **what was done to check this page's claim** — an act, not a self-assessed confidence.
値の一覧・rank の序列・序列外の値・判定表・昇格規則は、次の 1 ファイルにしか無い:

> **`~/.claude/doc/doc_wiki_lifecycle_rubric.md`** — `lifecycle` を付ける / 変える前に必ず読む。

**この doc にも skill 本文にも値の一覧を書き写さないこと。** 2 つ目の写しができた瞬間に enum が漂流し、
新しいページが隣のページを真似て誤値を増やす（それが 66 ページの `active` の発生経路だった）。

`stale` は `lifecycle` の値ではなく、`evidence_at`（無ければ `updated`）に対する計算上のオーバーレイ。
rank が変わったときは `lifecycle_changed` を更新する。更新時は既存の rank を維持し、**新しい証拠が来たときだけ**
昇格して、その証拠を `lifecycle_evidence` / `evidence_at` に書く。隣のページに合わせて rank を選ばない。

### Confidence formula

```
base_confidence = source_count_score * 0.5 + source_quality_score * 0.5

source_count_score   = min(distinct_source_ids / 3, 1.0)
source_quality_score = avg(quality score per distinct source_id)
```

**Source-quality scores** (use the highest-matching bucket):

| Bucket | Score | Examples |
|---|---|---|
| `paper` | 1.0 | arXiv, conference proceedings |
| `official` | 0.9 | `*.gov`, vendor docs |
| `documentation` | 0.85 | well-maintained third-party docs |
| `book` | 0.8 | books, technical references |
| `repository` | 0.75 | GitHub READMEs, codebases |
| `blog` | 0.55 | personal blogs |
| `session_transcript` | 0.5 | conversation history |
| `forum` | 0.4 | Stack Overflow, HN, Reddit |
| `unknown` | 0.4 | catch-all |
| `llm_generated` | 0.3 | LLM self-reflections |

**A `source_id`** is a stable per-source identifier — prevents counting three copies of the same blog as three distinct sources:

| Source type | source_id rule |
|---|---|
| Academic paper | DOI > arXiv ID > `<author>-<year>-<slug>` |
| GitHub repo | `github.com/<owner>/<repo>` |
| Documentation site | `<canonical-host>/<product>` |
| Blog post | `<host>/<author>` |
| Session transcript | `<agent>/<session-id>` |
| Other | `<canonical-url>` |

**Per-skill defaults** (ingest skills compute this automatically):

The `lifecycle` column is a **floor, not a fixed value**. Every skill starts a new page at `draft`; if the evidence for the page's claim is already in the body, promote it in the same pass per the rubric and fill `lifecycle_evidence` / `evidence_at`. Leaving a well-evidenced page at `draft` is a lossy default, not a safe one — but it is still the correct default when you have not checked.

| Skill | base_confidence | lifecycle (floor) |
|---|---|---|
| `wiki-ingest` (URL) | `0.17 + 0.5 × classify(url)` | `draft` |
| `wiki-ingest` (single doc) | per-source classifier | `draft` |
| `wiki-ingest` (multi-doc) | `min(N/3,1)×0.5 + avg_q×0.5` | `draft` |
| `wiki-capture` | 0.42（source が会話 1 本のときの式の出力。source が増えたら式で再計算する） | `draft` |
| `claude-history-ingest` | 0.42（同上） | `draft` |
| `wiki-update` | 0.59（source が `documentation` 1 本のときの式の出力。同様に再計算する） | `draft` |

## Importance Tiering

The `tier:` field controls which pages get updated on each ingest pass and their priority in retrieval. As wikis grow, re-reading every page on every ingest wastes tokens — tiering lets ingest and query skills focus effort where it matters most.

### Three tiers

| Tier | Meaning | Ingest behavior | Query priority |
|---|---|---|---|
| `core` | Load-bearing pages — many other pages depend on them (high incoming-link count or bridge position). Always worth updating. | Always update if the source is even marginally relevant | Surfaced first in index and full-read passes |
| `supporting` *(default)* | Standard wiki pages with moderate connectivity | Update when the source has clear new claims for this page | Standard priority |
| `peripheral` | Low-connectivity pages — rarely linked, narrowly scoped | Skip unless the source is *primarily* about this topic | Last resort; skipped when trimming to context budget |

### Assignment rules

これがこのバンドルで**唯一**の閾値定義。他の場所に別の数字を書かないこと（`≤1` と `0` が別ファイルに併存していた
のを 2026-08-12 に統一した）。

- **New pages:** default to `tier: supporting`
- **Promote to `core`:** when a page accumulates ≥5 incoming wikilinks, or sits in a bridge position between clusters
- **Demote to `peripheral`:** when a page has **≤1 incoming link** and hasn't been updated in 90+ days
- **Human override always wins** — edit `tier:` manually to lock a page at any level
- Existing pages without `tier:` are treated as `supporting` (backward compatible — no migration needed)

### 事実: 昇格を書く主体は現状いない（降格は wiki-lint が書く）

**昇格**（`core` への引き上げ）を書く skill は無い。**降格**（`peripheral`）だけは
`wiki-lint --consolidate` が上の `≤1` / 90 日を条件に、dry-run と明示確認を経て書く
（`core` は手動設定とみなして自動降格しない）。**この閾値を持つ書き手は 1 つだけ。増やさないこと。**
新規ページの `supporting` 既定は ingest 側のテンプレが書く。
既存の `tier:` 値は規則の外で付与されたものも混ざるが、読む側（`wiki-ingest` の更新判定・
`wiki-query` の順序付け）は**そのまま信じて使う**。

## Retrieval Primitives

Reading the vault is the dominant cost of every read-side skill. Use the cheapest primitive that can answer the question and **escalate only when the cheaper one is insufficient**. Any skill that needs content from the vault should follow this table rather than jumping straight to full-page reads.

| Need | Primitive | Relative cost |
|---|---|---|
| Does a page exist? What's its title/category/tags? | Read `index.md`; `Grep` frontmatter blocks (scope with a pattern that targets `^---` blocks at file heads) | **Cheapest** |
| 1–2 sentence preview of a page | Read the `summary:` field in its frontmatter | **Cheap** |
| A specific claim or section inside a page | `Grep -A <n> -B <n> "<term>" <file>` — returns only the matching lines plus context | **Medium** |
| Whole-page content | `Read <file>` | **Expensive** — last resort |
| Relationships across pages | `Grep "\[\[.*?\]\]"` across the vault, or walk wikilinks from a known page | Case-by-case |

**The rule:** escalate only when the cheaper primitive can't answer the question. If you can answer from `summary:` fields alone, don't read page bodies. If a grepped section with `-A 10 -B 2` gives you the claim, don't read the whole page. A 500-line page opened to read 15 lines is 485 lines of wasted tokens.

**Why this matters:** a 20-page vault lets you get away with full-vault scans. A 200-page vault does not. The primitives above are how the skills framework scales to large vaults without a database.

## Link Format

All internal links connecting wiki pages are controlled by `OBSIDIAN_LINK_FORMAT` from the resolved config (default: `wikilink`).

| Setting | Syntax | Example |
|---|---|---|
| `wikilink` *(default)* | `[[path/to/page]]` or `[[path/to/page\|display text]]` | `[[concepts/foo\|foo]]` |
| `markdown` | `[display text](relative/path.md)` | `[foo](../concepts/foo.md)` |

### Generating markdown-format links

When `OBSIDIAN_LINK_FORMAT=markdown`:
1. Compute the path from the **current file's directory** to the **target `.md` file** using `..` to climb up as needed.
2. Use the page title or a natural phrase as display text.
3. Always include the `.md` extension.

| Current file | Target | Relative link |
|---|---|---|
| `index.md` | `concepts/foo.md` | `[foo](concepts/foo.md)` |
| `concepts/foo.md` | `entities/bar.md` | `[bar](../entities/bar.md)` |
| `projects/my-project/my-project.md` | `concepts/foo.md` | `[foo](../../concepts/foo.md)` |
| `projects/my-project/concepts/arch.md` | `entities/bar.md` | `[bar](../../../entities/bar.md)` |

The `[[path\|display text]]` wikilink form maps to `[display text](relative/path.md)` in Markdown mode.

**Scope:** this setting affects only newly written or updated links. Existing vault content is never migrated — no skill in this bundle converts old links in bulk, so a format switch leaves earlier links as they are.

Every write skill reads `OBSIDIAN_LINK_FORMAT` from the resolved config before generating links and applies the correct format. Frontmatter `relationships:` targets are the one exception: they always use wikilink syntax (see Typed Relationships).
