# Link graph — manual fallback

**Use this only when `scripts/linkgraph.py` cannot run** (no `python3`). It is the same
algorithm written out by hand, and it is a *degraded* version: every step below is a place
where two runs can disagree. Say in the report that you used the fallback.

The script is the definition. If this file and the script disagree, the script is right.

## 1. Collect the pages

Glob `**/*.md` under `$OBSIDIAN_VAULT_PATH`, then drop:

- anything under a directory starting with `_` (`_raw/`, `_archived/`, `_staging/`,
  `_source_docs/`, `_state/`, …) — staging areas and primary sources, not wiki pages
- anything under `.obsidian/`, `.git/`, `.claude/`
- anything matching a line in `$OBSIDIAN_VAULT_PATH/.wikilintignore` (one pattern per line,
  `#` starts a comment). A bare directory name excludes that whole directory; globs
  (`drafts/*.md`) work too. **This file is shared** — `wiki-dedup`'s candidate script reads
  the same list, so a path added here also stops being offered as a merge candidate. Keep it
  as the one place a vault says "this is not a wiki page"; do not add a private skip list.

Keep the excluded files in a separate list rather than forgetting them — a live page can
link *into* an excluded directory, and that link is not broken (step 5).

If a file cannot be read (dangling symlink, permissions), record it and carry on. Do not
let one bad file abort the pass, and do not silently treat it as absent.

For each remaining file record three keys:

| key | how | example for `project-a/Build Spec.md` |
|---|---|---|
| `path` | vault-relative path | `project-a/Build Spec.md` |
| `node` | path minus `.md`, each segment lowercased, spaces → hyphens | `project-a/build-spec` |
| `base` | filename minus `.md`, lowercased, spaces → hyphens | `build-spec` |

Also collect each page's frontmatter `aliases:` (both `aliases: [a, b]` and the block list
form), normalized the same way as `base`.

## 2. Strip code regions before extracting anything

The vault is full of literal link syntax used as *examples*. Those are documentation, not
edges. Scan each file line by line, keeping one piece of state (`inside a fence` + the
fence marker):

1. If inside a fence: the fence closes only on a line whose run is the **same character
   and at least as long** as the opening run. Either way **replace the line with an empty
   line** and move on.
2. If not inside a fence and the line starts with a run of 3+ backticks or 3+ tildes: open
   a fence, remember **the whole run** as the marker, replace the line with an empty line.
3. Otherwise remove inline code spans from the line.

Remembering the whole run matters: a ` ```` ` fence legally contains ` ``` `, so truncating
the marker to three characters closes the fence early and leaks the rest of the block.

An **unclosed fence strips to end of file**. That is deliberate — leaking the tail of a
file after someone forgot a closing fence is worse than losing the tail.

Inline code spans: a run of N backticks closes with **exactly N** backticks, and runs
shorter than N are legal *inside* the span. So `` `[[x]]` `` and ``` ``code with ` inside`` ```
must both be removed whole. A naive `` `[^`]*` `` gets the second case wrong.

**Do not strip frontmatter.** `relationships:` entries carry `target: "[[page]]"` and those
are real edges; dropping them turns pages that only have typed relationships into orphans.

## 3. Extract link targets — keep track of which notation each came from

Two notations, and **they do not mean the same thing**:

- **Wikilinks** `[[target]]`, `[[target|label]]`, `[[target#heading]]`, `![[embed]]`.
  Take the part before `|` and before `#`. Drop it if the target is empty (`[[#heading]]`),
  contains `{{` (a template placeholder), or ends in an asset extension
  (png jpg jpeg gif svg webp pdf canvas base excalidraw html htm mp3 mp4 mov zip).
- **Markdown links** `[label](path.md)`, optionally with `#anchor` and a `"title"`.
  **Only when the href is not a URL and ends in `.md` as a path component.** Matching
  "contains `.md`" pulls in `https://www.mdpi.com/…` and `https://…/docs/en/memory.md` —
  four such false positives existed across the two vaults on 2026-08-05.

## 4. Resolve each target — by notation

Strip a trailing `.md` and lowercase before matching, in every branch.

**Markdown link, or any target starting with `./` or `../`:** join it onto the *linking
file's directory* and normalize (`..` pops a segment; popping past the vault root means
the link points outside — broken). Look the result up as a `node`. If a markdown link
fails that way, retry it once as a vault-root path, then stop. If a `./`/`../` target
fails, it is broken.

**A markdown link never falls back to a bare name.** `[x](spec.md)` is a path; if no page
sits at that path, the link is broken. Searching the vault for some other `spec.md` finds
an unrelated page and reports a working graph over links that do not work.

**Wikilink containing `/`:** exact `node` match, else any page whose `node` ends with
`/<target>`.

**Bare wikilink:** `base` match, else `alias` match. This one *is* vault-wide — that is
what `[[spec]]` means in Obsidian.

**More than one match at any step → ambiguous, not resolved.** Never silently take the
first. On 2026-08-05 a live vault had three pairs of same-named pages across two sibling
project directories; taking the first match attributed 110 links to the wrong page.

## 5. Count and classify

- A link that resolves adds an edge. A link to the page itself counts as neither direction.
- **incoming** is *how many pages* link here, not how many links point here. Five links
  from one page is one incoming page — otherwise a single chatty page manufactures a hub.
  Keep the raw link count separately if you need it.
- **outgoing** is the number of resolved links out of the page.
- **broken** = did not resolve. **ambiguous** = matched several pages.
- **A link into an excluded directory is neither.** The target exists, so it is not broken;
  the target is not in the graph, so it is not an edge. Count them separately.
- **orphan** = incoming 0 **and** outgoing 0, excluding the reserved pages
  `index` / `log` / `hot` / `_insights`.
- Report every page's incoming and outgoing, **including the zeros**. A page missing from
  the list is indistinguishable from a page you forgot to scan.
