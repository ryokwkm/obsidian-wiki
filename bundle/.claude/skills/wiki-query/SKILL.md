---
name: wiki-query
description: コンパイル済みの Obsidian wiki を検索し、ページからの引用付きで統合した答えを返す。「◯◯について何を知ってる」「◯◯に関するものを全部出して」「X と Y はどう繋がってる」や英語の "what do I know about X" / "find everything related to Y" と言われたときに使う。型付きエッジを複数ホップ辿るマルチホップの質問にも答える。「ざっと答えて」/ "quick answer" で index だけ読む高速モード。どのプロジェクトからでも使える。
---

# Wiki Query — Knowledge Retrieval

You are answering questions against a compiled Obsidian wiki, not raw source documents. The wiki contains pre-synthesized, cross-referenced knowledge.

## This skill is READ-ONLY

`wiki-query` answers questions. It MUST NOT create or modify any wiki content. The ONLY write it may perform is the single Step 6 append to `log.md`.

Never, even when a change seems obviously helpful:
- create or edit pages under `concepts/`, `entities/`, `skills/`, `references/`, `synthesis/`, `journal/`, or `projects/`
- modify `index.md`, `hot.md`, `_insights.md`, or `.manifest.json`

If the user's message contains a new finding, an action request ("save this", "ban X", "record that"), or anything implying a change, **do not perform it.** Answer the question, PROPOSE the change, and route the user to the right skill:
- quick note / gotcha → `wiki-capture --quick`
- a full new page → `wiki-capture`
- a project-knowledge sync → `wiki-update`

## Before You Start

1. **Resolve config.** Use `$OBSIDIAN_VAULT_PATH` if it is already exported (shell rc, direnv, parent process) — that wins. If it is unset, walk up from CWD to `$HOME` for the first `.env` containing `OBSIDIAN_VAULT_PATH=` and use that value. If neither yields a path, stop and tell the user: `No vault config found. Set OBSIDIAN_VAULT_PATH in .claude/settings.json (env), a shell rc, or direnv.` Never hard-code a vault path and never borrow another project's vault. This works from any project directory.
2. **Read the QMD variables from the same config** — `QMD_WIKI_COLLECTION`, `QMD_TRANSPORT`, `QMD_CLI_SEARCH_MODE`, `QMD_PAPERS_COLLECTION` — before deciding a retrieval strategy. If `QMD_WIKI_COLLECTION` is set, treat QMD as available subject only to the transport check in Step 2b. If it is empty or unset, say briefly why QMD is being skipped and take the grep path; it is fully functional.
3. **Read nothing from the vault yet.** Classify the question first (Step 1), then climb the ladder from its cheap end (Step 2 onward). Two files in particular are not free and must not be opened reflexively:
   - **`index.md` runs 40–50 kB in a mature vault.** Grep it for the query terms (Step 2). Read it whole only when the question is about the wiki's *shape* — "what's in here", "what areas do I cover".
   - **`hot.md` holds no distilled knowledge.** It is a cache of the last few operations and open threads, so for a question about a *topic* it costs bytes and answers nothing. It is the last rung, not the first — see Step 4c.

## Visibility Filter (optional)

By default, **all pages are returned** regardless of visibility tags. This preserves existing behavior — nothing changes unless the user asks for it.

If the user's query includes phrases like **"public only"**, **"user-facing"**, **"no internal content"**, **"as a user would see it"**, or **"exclude internal"**, activate **filtered mode**:

- Build a **blocked tag set**: `{visibility/internal, visibility/pii}`
- In the Index Pass (Step 2), skip any candidate whose frontmatter tags contain a blocked tag
- In the Section, Full Read, traversal, and recency passes (Steps 3–4c), do not read or cite any blocked page
- Synthesize the answer **only from allowed pages** — do not mention that excluded pages exist

Pages with no `visibility/` tag, or tagged `visibility/public`, are always included.

In filtered mode, note the filter in the Step 6 log entry: `mode=filtered`.

## Retrieval Protocol

Reading the vault is the dominant cost of this skill. **Use the cheapest primitive that can answer the question and escalate only when it can't** — the cost table for the primitives themselves is the "Retrieval Primitives" section of `~/.claude/doc/doc_wiki_schema.md`. The steps below are that table applied to answering a question, cheapest rung first:

> `index.md` entry (grep) → page `summary:` frontmatter → grepped section (`-A`/`-B`) → full page read → `hot.md`

Each step below states what has to be missing before you climb. Never jump straight to full-page reads, and never open `hot.md` before the rungs to its left have failed — the one exception is a question explicitly about recency, where `hot.md` is the only file that holds the answer (Step 4c).

### Step 1: Understand the Question

Classify the query type:
- **Factual lookup** — "What is X?" → Find the relevant page(s)
- **Relationship query** — "How does X relate to Y?" / "What contradicts X?" → Find both pages, their cross-references, and their `relationships:` frontmatter blocks for typed edges
- **Path / multi-hop query** — "How is X connected to Y?" / "What links X to Y?" / "Trace the chain from X to Z" / "What does X depend on transitively?" → X and Y don't link directly; the connection runs through intermediate pages. Use the multi-hop graph traversal in Step 4b.
- **Synthesis query** — "What's the current thinking on X?" → Find all pages that touch X, synthesize
- **Gap query** — "What don't I know about X?" → Find what's missing, check open questions sections

Also decide the **mode**:
- **Index-only mode** — triggered by "quick answer", "just scan", "don't read the pages", "fast lookup". Stops after Step 2. Answers from frontmatter + `index.md` entries only.
- **Normal mode** — the full tiered pipeline below.

### Step 2: Index Pass (cheap)

Build a candidate set *without opening any page bodies*:

- **`index.md` is the first filter — grep it, don't read it.** It lists every page with a one-line description and tags, and it is the largest single file in the vault. `Grep -n "<query-term>" $OBSIDIAN_VAULT_PATH/index.md` returns the handful of entry lines that matter for a few hundred bytes. Read it in full only when the question is about the wiki's overall scope, or when grep returns nothing and you need to see which categories exist before rephrasing.
- Use `Grep` to scan page **frontmatter only** for title, tag, alias, and summary matches. A pattern like `^(title|tags|aliases|summary):` scoped to vault `.md` files is far cheaper than content grep.
- Collect the top 5–10 candidate page paths ranked by:
  1. Exact title or alias match
  2. Tag match
  3. Summary field contains the query term
  4. `index.md` entry contains the query term
- **Apply tier ordering within each rank bucket:** when two candidates score equally, prefer `tier: core` over `tier: supporting` over `tier: peripheral`. Read the `tier:` frontmatter field with the same cheap grep as the other fields.
- **A missing `tier:` is not a demotion.** No skill promotes a page into `tier: core`, so most pages never acquire the field at all — its absence means "nobody classified this", not "low value". Rank an untagged page as if it were `supporting`, and never drop, downrank, or skip reading a candidate *because* the field is missing. Only an explicit `tier: peripheral` may cost a page its place.

If you're in **index-only mode**, stop here. Answer from `summary:` fields, titles, and `index.md` descriptions only. Label the answer clearly: **"(index-only answer — page bodies not read; facts below are from page summaries and may miss nuance)"**. Then skip to Step 5.

### Step 2b: QMD Semantic Pass (optional — requires `QMD_WIKI_COLLECTION` in resolved config)

**GUARD: If `$QMD_WIKI_COLLECTION` is empty or unset after config resolution, skip this entire step and proceed to Step 3. Mention the missing variable in your working update.**

> **No QMD?** Skip to Step 3 and use `Grep` directly on the vault. QMD is faster and concept-aware but the grep path is fully functional.

If `QMD_WIKI_COLLECTION` is set, run QMD before reaching for `Grep` unless the question is already fully answered by `index.md` metadata. QMD is especially preferred when the question is semantic, project-specific, asks for related context, or uses terms that may not appear verbatim in titles/frontmatter.

Choose the QMD transport from `$QMD_TRANSPORT`:

- `mcp` (default): use the QMD MCP tool configured in the agent.
- `cli`: run the local qmd CLI. Invoke it as the bare name `qmd` — never `${QMD_CLI:-qmd}`: command allowlists match the command name *before* variable expansion, so the variable form silently loses its permissions.

🔴 **If the selected transport is unavailable, try the other one before giving up.** An environment may have no QMD MCP server registered even though the `qmd` CLI works — fall through to the CLI rather than skipping the step. Only when neither transport works (no MCP tool *and* no usable `qmd`, or the command errors) skip QMD and continue with Step 3.

Skipping instead of falling through is not a small loss: it drops **every semantic query** — `vec:` recall, HyDE expansion, reranking — and leaves only literal `Grep`, which cannot answer "what is X like" or find pages that describe a concept without naming it (in a Japanese vault the lexical-only path misses even more — no word boundaries to anchor on).

For MCP transport:

```
mcp__qmd__query:
  collection: <QMD_WIKI_COLLECTION>   # e.g. "knowledge-base-wiki"
  intent: <the user's question>
  searches:
    - type: lex    # keyword match — good for exact names, file paths, error messages
      query: <key terms>
    - type: vec    # semantic match — good for concepts, patterns, "what is X like"
      query: <question rephrased as a description>
```

For CLI transport, pick the command from `$QMD_CLI_SEARCH_MODE`:

Keep operator-like or punctuation-heavy tokens such as `no-sudo`, `ansible_become=false`, and `~/.local/bin` in the `lex:` line. Rewrite the `vec:` line as plain natural language without hyphenated `-term` words; QMD treats `-term` as negation, and negation is not supported in `vec`/`hyde` queries.

- `quality` (default): best relevance; slower on CPU.
  ```bash
  qmd query $'lex: <key terms>\nvec: <question rephrased as a description>' -c "$QMD_WIKI_COLLECTION" -n 8 --files
  ```
- `balanced`: hybrid search without LLM reranking; use when `quality` is too slow.
  ```bash
  qmd query $'lex: <key terms>\nvec: <question rephrased as a description>' -c "$QMD_WIKI_COLLECTION" -n 8 --no-rerank --files
  ```
- `fast`: semantic-only recall, or `search` instead when exact names, file paths, or error messages matter.
  ```bash
  qmd vsearch "<question rephrased as a description>" -c "$QMD_WIKI_COLLECTION" -n 8 --files
  ```

Use `qmd get "#docid"` to retrieve a ranked document by docid when CLI output provides one.

The returned snippets or ranked files act as pre-read section summaries. If they answer the question fully, skip Step 3 and go straight to Step 4 (reading only the pages QMD ranked highest). If not, use the ranked file list to guide which files to grep or read in Step 3.

**Freshness:** a SessionStart hook refreshes the index, so it reflects the vault as of this session's start — pages written *during* this session may not be indexed yet. This skill is read-only and never refreshes the index itself. If something you know was just written does not come back, `Grep` for it instead of concluding it isn't there.

**Also search `papers` when the question may have source material in `_raw/`:**

If `QMD_PAPERS_COLLECTION` is set and the user is asking about a topic likely covered by ingested papers (research, theory, background), run a parallel search against the papers collection. Cite raw sources separately from compiled wiki pages in your answer.

### Step 3: Section Pass (medium cost — only if Steps 2/2b are inconclusive)

For each of the top candidates, pull the relevant section *without reading the whole page*:

- Use `Grep -A 10 -B 2 "<query-term>" <candidate-file>` to get just the lines around the match.
- This usually returns 15–30 lines per hit instead of 100–500.
- If the section grep gives a clear answer, go straight to Step 5.

### Step 4: Full Read (expensive — last resort)

Only when Steps 2 and 3 don't answer the question:

- `Read` the top **3** candidates in full. When choosing which 3 to read, apply tier ordering as a tie-breaker: read `tier: core` pages first, and leave an explicit `tier: peripheral` for last unless it is the only match. An untagged page competes as `supporting` — never pass one over for lacking the field (see Step 2).
- Follow at most one hop of `[[wikilinks]]` from those pages if the answer requires cross-references.
- **For relationship queries** ("How does X relate to Y?" / "What contradicts X?"): also read the `relationships:` frontmatter block of the candidate pages. Each entry gives a typed, directional edge — the canonical type set is the **Typed Relationships table in `~/.claude/doc/doc_wiki_schema.md`** (10 concepts, 16 spellings; directional types have both a forward and a reverse spelling). Do not work from a remembered list. Surface these explicitly in your answer — "Page A *contradicts* Page B (typed edge)" is more useful than "Page A links to Page B".
- Check "Open Questions" sections for known gaps.
- If you're still short, **then** fall back to a broad content grep across the vault. Tell the user you escalated — this is the expensive path and they should know.

### Step 4b: Multi-hop Graph Traversal (typed edges)

Plain retrieval surfaces pages that *mention* the query terms. It cannot answer **path / multi-hop queries** — "How is X connected to Y?", "What does X depend on transitively?", "Trace the chain from X to Z" — when X and Y never appear on the same page. The answer lives in the *shape* of the typed-edge graph, not in any single page body. This is the step that walks it.

Run this step **only** for path/multi-hop queries (or when a relationship query returns no direct edge between the two pages). It is built entirely from frontmatter — never read page bodies here.

1. **Build the typed-edge adjacency (cheap).** Grep every page's `relationships:` block in one pass — `Grep -A 20 "^relationships:" <vault>/**/*.md` (frontmatter only). Each entry yields a directed, typed edge `source —type→ target`. Add the reverse direction as a traversable edge too (mark it `(reverse)`), since "connected to" is symmetric even though the typed assertion is directional. Directional types officially exist in both spellings (forward and reverse — see the Typed Relationships table in `~/.claude/doc/doc_wiki_schema.md`), so when you filter edges by type, or ground an answer on a type, treat the two spellings as one concept: a filter on `uses` must also match `used_by` edges with source and target swapped. Filtering on a single spelling silently drops half the matching edges. Plain body `[[wikilinks]]` count as untyped `related_to` edges only if you need them to complete a path — prefer typed edges first.

2. **Locate the endpoints.** Resolve X (and Y, if the query names two) to page paths using the registry from Step 2. If an endpoint is ambiguous, pick the highest-tier candidate — an untagged page still competes, per Step 2 — and note the assumption.

3. **Bounded BFS.** Walk outward from X over the adjacency:
   - **Max depth 3 hops** by default (the connection is rarely meaningful beyond that). Raise to 4 only if the user says "deep" / "however many hops it takes".
   - **Frontier cap:** stop expanding a node once the visited set exceeds ~60 pages — report partial results rather than fanning out across the whole vault.
   - For a **two-endpoint query** (X→Y): stop as soon as you find the shortest path; then continue briefly to surface up to 2 alternate paths if they exist.
   - For a **one-endpoint query** (X transitively): collect all nodes reachable within the depth limit, grouped by hop distance.

4. **Report the path(s) with edge types.** Show the chain, not just the endpoints — the typed edges *are* the answer:

   ```
   [[concepts/transformers]] —uses→ [[concepts/attention]] —derived_from→ [[concepts/rnn-seq2seq]] —uses (reverse)→ [[concepts/lstm]]
   ```

   State the hop count, and flag any hop that is an untyped `related_to` fallback (those chains are weaker). A `(reverse)` mark is not a weakness — a directional edge read backwards is the same relationship, and the schema's reverse spellings make both readings first-class — but keep the mark so the reader can see the stored direction. If no path exists within the depth limit, say so explicitly: "No typed-edge path from X to Y within 3 hops — they are in disconnected regions of the graph." That is itself a useful finding (a graph gap).

**Cost guard:** this step reads only frontmatter via grep. If the adjacency grep returns nothing (no page uses `relationships:` yet), report that the graph has no typed edges to traverse — the vault's pages predate the field — and fall back to ordinary one-hop retrieval over body `[[wikilinks]]`.

### Step 4c: Recency Pass (`hot.md` — the last rung)

`hot.md` is the only vault file whose content is *operational* rather than distilled: the last few operations and the open threads. Read it in exactly two situations:

1. The question is explicitly about recency — "what did I just work on", "what changed", "where did I leave off". Here `hot.md` is the *first* thing to read, because it is the only file that records it.
2. Every rung above failed and the question sounds like it concerns work in flight (something written too recently to have been distilled into a page yet).

For any question about a *topic*, skip it. Even when it happens to mention the topic, the substance lives on the pages it points at — follow the links and cite those pages, not `hot.md`. Never cite `hot.md` as the source of a claim.

### Step 5: Synthesize an Answer

Compose your answer from wiki content:
- Cite specific wiki pages using `[[page-name]]` notation
- Note which step the answer came from ("found in summary" vs "grepped section" vs "full page read") — helps the user understand confidence
- If the wiki has contradictions, present both sides
- If the wiki doesn't cover something, say so explicitly
- Suggest which sources might fill the gap

**Page trust annotations:** For every page you cite, read its `lifecycle` field — plus `evidence_at`, `lifecycle_changed`, `lifecycle_reason`, and `superseded_by` where present — and annotate the citation inline, so the reader can tell how strongly each one is backed.

**This is the whole point of the ladder.** A page that measured something and a page that guessed it look identical in a synthesized answer unless you say which is which.

**The canon is `~/.claude/doc/doc_wiki_lifecycle_rubric.md`** — the values, their ranking, what each one asserts about who checked the claim, and the staleness thresholds all live there and *only* there. Read it before annotating; do not annotate from memory and never restate its values here.

How to annotate:

- **Match `lifecycle` as a whole value, never as a substring.** No value is a prefix of another by design, and a substring match silently mislabels a page.
- **Say what backs the claim, in a short parenthetical right after the `[[wikilink]]`** — whether someone ran it, only read it, only reasoned about it, or has not checked it at all. Take the meaning from the rubric; keep the wording to a clause.
- **A low-evidence page must carry a visible caveat.** This is not optional: an unannotated guess reads as a fact.
- **A superseded page: cite its successor instead**, and name it. A disputed page must be marked as disputed, with the date it was marked and the recorded reason when the frontmatter has one.
- **Stale evidence keeps its rung but gains a re-verify note.** Compute staleness from `evidence_at` (fall back to `updated:` when the page has none) against the rubric's thresholds, and let the note reflect the cost of re-checking — a human sign-off is expensive to renew, an AI re-run is cheap.
- **Fresh, well-backed pages get no annotation.** That is the case the ladder exists to leave alone; a note on every citation trains the reader to skip them all.
- **Never fabricate** a reason or an `evidence_at`. If the field is absent, drop that part of the annotation. A page with no `lifecycle` at all predates the schema — treat it as the rubric's default lowest rung and annotate it as unchecked.

The shape in a synthesized answer (format illustration, not the value list):
```
[[concept-page]] (reasoning only — no measurement behind this) — Claims X follows from Y.
[[spec-page]] (sourced, evidence from 2026-02-01 — cheap to re-run) — The current implementation does X.
```

**Surface the project source path (project-scoped queries).** When the cited pages are project-scoped — their path is under `projects/<name>/...`, or their frontmatter carries a `source_path` field — resolve where the actual code lives so a proposed fix can name real files and a follow-up turn can edit them:

1. Read `$OBSIDIAN_VAULT_PATH/.manifest.json` and look up `.projects.<name>.source_cwd` — this is the authoritative path.
2. Fallback: if the project isn't in the manifest, use the page's `source_path` frontmatter.

Include a **`Source code:`** line in the answer with that absolute path. When the query implies a code fix is wanted, name the specific files to edit using that path (e.g. `<source_cwd>/src/lib/auth.js`) and **offer to implement it as an explicit, separate next step** — but never edit during the query itself (see the READ-ONLY guard above).

### Step 6: Log the Query

Append to `log.md`. This `log.md` append is the *only* write this skill performs — do not edit anything else.
```
- [TIMESTAMP] QUERY query="the user's question" result_pages=N mode=normal|index_only|filtered escalated=true|false
```

`[TIMESTAMP]` is the output of `date -u +%Y-%m-%dT%H:%M:%SZ` — run it and paste the result verbatim, never hand-write it (why: schema doc, `log.md`).

## Answer Format

Structure answers like this:

> **Based on the wiki:**
>
> [Your synthesized answer with [[wikilinks]] to source pages]
>
> **Pages consulted:** [[page-a]], [[page-b]], [[page-c]]
>
> **Gaps:** [What the wiki doesn't cover that might be relevant]
>
> **Source code:** `<source_cwd>` — to implement, the relevant files are `…`.
> (Say the word and I'll switch out of query mode to make the change.)

The **Source code** line is optional — include it only for project-scoped queries where you resolved a `source_cwd` (see Step 5).
