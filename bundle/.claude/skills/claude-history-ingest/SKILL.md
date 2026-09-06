---
name: claude-history-ingest
description: Claude Code の会話履歴（~/.claude/projects のセッションログ）を Obsidian wiki へ取り込み、過去のセッションから知見を抽出する。「Claude の履歴を処理して」「会話を wiki に追加して」「Claude と何を話したっけ」や英語の "process my Claude history" / "add my conversations to the wiki" と言われたとき、.claude フォルダ・セッションデータ・過去の会話ログに言及されたときに使う。
---

# Claude History Ingest — Conversation Mining

You are extracting knowledge from the user's past Claude Code conversations and distilling it into the Obsidian wiki. Conversations are rich but messy — your job is to find the signal and compile it.

## Before You Start

1. **Resolve config** — use `OBSIDIAN_VAULT_PATH` if it is already exported (shell rc / direnv / parent process). Otherwise walk up from CWD to `$HOME` for a `.env` containing `OBSIDIAN_VAULT_PATH=` and take the first match. If neither exists, stop and tell the user to set it in `.claude/settings.json` (`env`), shell rc, or direnv — never hard-code a path or guess a vault. Read `CLAUDE_HISTORY_PATH` the same way (defaults to `~/.claude`)
2. Read `.manifest.json` at the vault root to check what's already been ingested
3. Read `index.md` at the vault root to know what the wiki already contains
4. **Project Scoping** — read `WIKI_SKIP_PROJECTS` from the environment: comma-separated substrings, unset or empty means skip nothing. Exclude any project directory whose name contains one of them from **every** step below (scan, delta, sampling, manifest writes). If the user names extra projects to skip this run, add them. Apply the exclusion **once, uniformly** — don't hand-write `grep -v` filters into individual commands, which drifts between the scan and manifest steps.

## Ingest Modes

### Append Mode (default)

Check `.manifest.json` for each source file (conversation JSONL, memory file). Only process:

- Files not in the manifest (new conversations, new memory files, new projects)
- Files whose modification time is newer than their `ingested_at` in the manifest

This is usually what you want — the user ran a few new sessions and wants to capture the delta.

> **Comparing paths against the manifest.** Sources for *this* skill live under
> `~/.claude/`, so expand `~` and env vars before deciding a file is "new". **Do not
> "canonicalize" the manifest itself** — project-relative keys are correct as they stand.
> When a lookup by exact key misses, retry by basename and accept a path-suffix match
> before concluding the source is new. Rules and rationale:
> `~/.claude/doc/doc_wiki_schema.md`. Do this inline — this bundle has no manifest helper script.

### No Pre-extraction Step — Read the Raw JSONL

Raw JSONL files are 80-90% noise: `tool_use` blocks, `thinking` blocks, `progress` events, and
`file-history-snapshot` entries dominate by byte count. **This bundle ships no extractor** — filter
the JSONL yourself while reading it (Step 3 says how) and budget for the larger files: expect to
characterize fewer sessions per run than the sampling heuristic below suggests.

If a pre-extracted file happens to exist at `~/.claude/extracted/<project>/<session-id>.json`
— i.e. the user runs their own extractor — prefer it over the raw JSONL. Treat its absence as the
normal case, never as a failure to narrate.

### Conversation Sampling Heuristic

A history path can hold hundreds of conversation JSONLs — do not try to read them all. Per project:

- **If the project already has memory files** (`memory/*.md`), ingest those first (they are
  pre-distilled signal), then **also process conversations not yet in the manifest** — new
  conversations should still be captured even for memory-rich projects.
- **If the project has no memory files**, read only the **3 most recent** conversations (by mtime)
  to characterize it. Raw JSONL is expensive, so treat 3 as a ceiling rather than a quota — one
  large session may already exhaust the budget.
- Always report what you sampled vs skipped (e.g. "agenttower: 7 memory files + 4 new conversations
  ingested, 14 unchanged conversations skipped"), so the coverage gap is visible rather than silent.

### Full Mode

Process everything regardless of manifest. Use after the vault has been cleared by hand, or if the user explicitly asks.

## Claude Code Data Layout

Claude Code stores data in two locations. Scan **both**.

### Source 1: `~/.claude/` (CLI sessions)

```
~/.claude/
├── projects/                          # Per-project directories
│   ├── -Users-name-project-a/         # Path-derived name (slashes → dashes)
│   │   ├── <session-uuid>.jsonl       # Conversation data (JSONL)
│   │   └── memory/                    # Structured memories
│   │       ├── MEMORY.md              # Memory index
│   │       ├── user_*.md              # User profile memories
│   │       ├── feedback_*.md          # Workflow feedback memories
│   │       └── project_*.md           # Project context memories
│   ├── -Users-name-project-b/
│   │   └── ...
├── sessions/                          # Session metadata (JSON)
│   └── <pid>.json                     # {pid, sessionId, cwd, startedAt, kind, entrypoint}
├── history.jsonl                      # Global session history
├── tasks/                             # Subagent task data
├── plans/                             # Saved plans
└── settings.json
```

### Source 2: `~/Library/Application Support/Claude/local-agent-mode-sessions/` (Desktop app agent sessions)

> **Pre-check first.** Many users are CLI-only and have no desktop sessions. Before walking the structure below, confirm it's non-empty:
> ```bash
> DESKTOP_SESSIONS="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"
> [ -d "$DESKTOP_SESSIONS" ] && find "$DESKTOP_SESSIONS" -name "audit.jsonl" | head -1
> ```
> If that prints nothing, skip this entire section (Source 2 + Step 3b) and don't narrate it.

The Claude desktop app stores local agent mode sessions here. The structure is deeply nested:

```
~/Library/Application Support/Claude/local-agent-mode-sessions/
└── <outer-uuid>/
    └── <inner-uuid>/
        ├── local_<session-uuid>.json          # Session metadata
        └── local_<session-uuid>/
            ├── audit.jsonl                    # Audit log — tool calls, file reads, commands run
            └── .claude/
                └── projects/
                    └── <path-encoded-name>/   # Same path-encoding as ~/.claude/projects/
                        └── <uuid>.jsonl       # Conversation transcript (same JSONL format as CLI)
```

**How to find all local-agent-mode sessions:**

```bash
# Find all session metadata files
find ~/Library/Application\ Support/Claude/local-agent-mode-sessions -name "local_*.json" -maxdepth 4

# Find all audit logs
find ~/Library/Application\ Support/Claude/local-agent-mode-sessions -name "audit.jsonl"

# Find all conversation transcripts
find ~/Library/Application\ Support/Claude/local-agent-mode-sessions -name "*.jsonl" -path "*/.claude/projects/*"
```

**Session metadata (`local_<uuid>.json`)** — JSON file with fields like `sessionId`, `cwd`, `startedAt`, `model`, `title`. Read this first to understand the session context before opening the transcript.

**Audit log (`audit.jsonl`)** — Each line is a JSON record of one agent action: tool calls (Read, Write, Bash, Edit), file accesses, shell commands executed, MCP calls. Useful for understanding *what the agent actually did* — often richer signal than the conversation text alone. Fields: `type`, `toolName`, `input`, `output`, `timestamp`, `sessionId`.

**Conversation transcript (`.claude/projects/.../<uuid>.jsonl`)** — Identical format to CLI conversation JSONL. Parse the same way as `~/.claude/projects/*/*.jsonl`.

### Key data sources ranked by value (both locations combined):

1. **Memory files** (`~/.claude/projects/*/memory/*.md`) — Pre-distilled, already wiki-friendly. Gold.
2. **Conversation JSONL** (both `~/.claude/projects/*/*.jsonl` and desktop app transcripts) — Full conversation transcripts. Rich but noisy.
3. **Audit logs** (`audit.jsonl` in desktop sessions) — Tool-call level record of what was done. Useful for extracting concrete actions, file patterns, and command patterns even when the conversation is sparse.
4. **Session metadata** (`sessions/*.json` and `local_*.json`) — Tells you which project, when, and what CWD.

## Step 1: Survey and Compute Delta

Scan both data locations and compare against `.manifest.json`:

```bash
# --- Source 1: CLI sessions (~/.claude) ---
# Find all projects
Glob: ~/.claude/projects/*/

# Find memory files (highest value)
Glob: ~/.claude/projects/*/memory/*.md

# Find conversation JSONL files
Glob: ~/.claude/projects/*/*.jsonl

# --- Source 2: Desktop app local-agent-mode sessions ---
DESKTOP_SESSIONS="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"

# Session metadata
find "$DESKTOP_SESSIONS" -name "local_*.json" -maxdepth 4

# Audit logs
find "$DESKTOP_SESSIONS" -name "audit.jsonl"

# Conversation transcripts
find "$DESKTOP_SESSIONS" -name "*.jsonl" -path "*/.claude/projects/*"
```

Build a unified inventory and classify each file:

- **New** — not in manifest → needs ingesting
- **Modified** — in manifest but file is newer → needs re-ingesting
- **Unchanged** — in manifest and not modified → skip in append mode

Report to the user: "Found X CLI projects, Y desktop sessions. Memory files: A. Conversations: B. Audit logs: C. Delta: D new, E modified."

## Step 2: Ingest Memory Files First

Memory files are already structured with YAML frontmatter:

```markdown
---
name: memory-name
description: one-line description
type: user|feedback|project|reference
---

Memory content here.
```

For each memory file:

- Read it and parse the frontmatter
- `user` type → feeds into an entity page about the user, or concept pages about their domain
- `feedback` type → feeds into skills pages (workflow patterns, what works, what doesn't)
- `project` type → feeds into entity pages for the project
- `reference` type → feeds into reference pages pointing to external resources

The `MEMORY.md` index file in each project is a quick summary — read it first to decide which individual memory files are worth reading in full.

## Step 3: Parse Conversation JSONL

The raw JSONL at `~/.claude/projects/<proj>/<uuid>.jsonl` is the normal input. A `Glob` for
`~/.claude/extracted/<proj>/<uuid>.json` is worth one cheap check — if a user-run extractor left a
compact file there, iterate `turns[].{role, text}` from it instead and skip the filtering below.
**Expect that file to be absent** (nothing in this bundle produces it) and go straight to the raw
JSONL when it is.

**Reading raw JSONL:** Each line is a JSON object:

```json
{
  "type": "user|assistant|progress|file-history-snapshot",
  "message": {
    "role": "user|assistant",
    "content": "text string"
  },
  "uuid": "...",
  "timestamp": "2026-03-15T10:30:00.000Z",
  "sessionId": "...",
  "cwd": "/path/to/project",
  "version": "2.1.59"
}
```

For assistant messages, `content` may be an array of content blocks:

```json
{
  "content": [
    {"type": "thinking", "text": "..."},
    {"type": "text", "text": "The actual response..."},
    {"type": "tool_use", "name": "Read", "input": {...}}
  ]
}
```

- Filter to `type: "user"` and `type: "assistant"` entries only
- For assistant entries, extract `text` blocks (skip `thinking` and `tool_use` — those are noise)
- The `cwd` field tells you which project this conversation belongs to
- Skip `type: "progress"` — internal agent progress updates
- Skip `type: "file-history-snapshot"` — file state tracking
- Skip subagent conversations (under `subagents/` subdirectories) — unless the user asks

## Step 3b: Parse Audit Logs (desktop sessions only)

For each `audit.jsonl` found under `local-agent-mode-sessions/`, read it line by line. Each line is a JSON record of one agent action:

```json
{
  "type": "tool_call",
  "toolName": "Bash",
  "input": {"command": "npm test"},
  "output": "...",
  "timestamp": "2026-04-10T14:22:00Z",
  "sessionId": "..."
}
```

**What to extract from audit logs:**

- **File access patterns** — which files does the agent repeatedly Read or Edit? These are the high-value files in the project. Note them as project references.
- **Shell commands** — recurring Bash commands reveal the project's build/test/deploy workflow. Distill these into a `skills/` page (e.g. "how this project is built and tested").
- **Tool call sequences** — if the agent always does Read → Edit → Bash in a particular order, that's a workflow pattern worth capturing.
- **Error patterns** — failed tool calls (non-zero exit codes, error outputs) reveal pain points, known rough edges, or recurring bugs.
- **MCP tool calls** — calls to MCP tools reveal which external services and APIs the project integrates with.

**Skip from audit logs:**

- Routine file reads with no pattern (e.g. reading config files once)
- Tool outputs that are just noise (long stack traces, verbose logs) — summarize the error class, not the full output
- Anything that looks like secrets, tokens, or credentials in command arguments or outputs

**Cross-reference with the conversation transcript:** The audit log tells you *what happened*; the conversation tells you *why*. When both are available for the same session, use them together — the audit log grounds the conversation in concrete actions.

Read the paired `local_<uuid>.json` session metadata before processing the audit log — it gives you `cwd`, `startedAt`, and `title` to contextualize the actions.

## Step 4: Cluster by Topic

Don't create one wiki page per conversation. Instead:

- Group extracted knowledge **by topic** across conversations
- A single conversation about "debugging auth + setting up CI" → two separate topics
- Three conversations across different days about "React performance" → one merged topic
- The project directory name gives you a natural first-level grouping

## Step 5: Distill into Wiki Pages

Each Claude project maps to a project directory in the vault. The project directory name from `~/.claude/projects/` encodes the original path — decode it to get a clean project name:

```
-Users/Documents/projects/my-Project   → myproject
-Users/Documents/projects/Another-app  → anotherapp
```

A name containing `--claude-worktrees-` is a **git worktree of another project, not a new project**: cut the name at that marker and use the left side, so the worktree's sessions land in the existing project page. Details and the measured examples are in `references/claude-data-format.md`.

### Project-specific vs. global knowledge

| What you found                     | Where it goes               | Example                                             |
| ---------------------------------- | --------------------------- | --------------------------------------------------- |
| Project architecture decisions     | `projects/<name>/concepts/` | `projects/my-project/concepts/main-architecture.md` |
| Project-specific debugging         | `projects/<name>/skills/`   | `projects/my-project/skills/api-rate-limiting.md`   |
| General concept the user learned   | `concepts/` (global)        | `concepts/react-server-components.md`               |
| Recurring problem across projects  | `skills/` (global)          | `skills/debugging-hydration-errors.md`              |
| A tool/service used                | `entities/` (global)        | `entities/vercel-functions.md`                      |
| Patterns across many conversations | `synthesis/` (global)       | `synthesis/common-debugging-patterns.md`            |

For each project with content, create or update the project overview page at `projects/<name>/<name>.md` — **named after the project, not `_project.md`** (Obsidian's graph view uses the filename as the node label; rationale in the schema doc).

**Important:** Distill the _knowledge_, not the conversation. Don't write "In a conversation on March 15, the user asked about X." Write the knowledge itself, with the conversation as a source attribution.

**Write a `summary:` frontmatter field** on every new/updated page — 1–2 sentences, ≤200 chars, answering "what is this page about?" for a reader who hasn't opened it. `wiki-query`'s cheap retrieval path reads this field to avoid opening page bodies.

**Add confidence and lifecycle fields** to every new page's frontmatter:
```yaml
base_confidence: 0.42
lifecycle: draft                # floor. A session transcript is not evidence for its own claims —
                                # promote only if the transcript shows the check actually being run
lifecycle_changed: <ISO date today>
```

The values, the ranks, and the promotion rules live in exactly one place — **`~/.claude/doc/doc_wiki_lifecycle_rubric.md`**. Read it before writing or changing any `lifecycle` value; never copy its value list anywhere. Note in particular that a transcript saying a check passed is not the check (meta-verification does not promote), and that the two highest ranks are human-only — AI never writes them.

On update, leave `lifecycle` and `lifecycle_changed` unchanged unless the transcript itself shows a check being run that raises the rank — then re-rank per the rubric and update `lifecycle_evidence` / `evidence_at` alongside.

**Mark provenance** per the convention in `~/.claude/doc/doc_wiki_schema.md` (Provenance Markers): unmarked text is extracted, `^[inferred]` marks a synthesized claim, `^[ambiguous]` marks a contested or unclear one.

- **Memory files** are mostly extracted — the user wrote them by hand and they're already distilled. Treat memory-derived claims as extracted unless you're stitching together claims from multiple memory files.
- **Conversation distillation** is mostly inferred. You're synthesizing a coherent claim from many turns of dialogue, often filling in implicit reasoning. Apply `^[inferred]` liberally to synthesized patterns, generalizations across sessions, and "what the user really meant" interpretations.
- Use `^[ambiguous]` when the user changed their mind across sessions or when assistant and user contradicted each other and the resolution is unclear.
- Write a `provenance:` frontmatter block on every new/updated page summarizing the rough mix.

## Step 6: Update Manifest, Journal, and Special Files

### Update `.manifest.json`

For each source file processed, add/update its entry with:

- `ingested_at`, `size_bytes`, `modified_at`
- `source_type`: one of `"claude_conversation"`, `"claude_memory"`, `"claude_audit_log"`, `"claude_desktop_session"`
- `project`: the decoded project name
- `pages_created` and `pages_updated` lists

Also update the `projects` section of the manifest. **Its key set is defined in
`~/.claude/doc/doc_wiki_schema.md` (`.manifest.json` 節) — follow it and do not invent fields
of your own here.** Write it as a single `jq` command in `.projects["<name>"] += {…}` form.

⚠️ **Merge key by key — never replace the entry.** `wiki-update` writes an entry for the same
repository under the same key, and `source_cwd` / `last_commit_synced` come from there.
Assigning the object whole (`jq '.projects["<name>"] = {…}'`) drops them, which kills the
`Source code:` line in `wiki-query` and forces the next delta computation
(`git merge-base --is-ancestor <last_commit_synced> HEAD`) into a full re-scan of the project.
Reuse the key that is already in the manifest rather than adding a second entry for the same
repo under a differently-spelled name.

What this step writes into the entry — and nothing beyond it:

- `last_synced` — the `date -u +%Y-%m-%dT%H:%M:%SZ` output from this run.
- `pages_in_vault` — append the pages you wrote, deduped against what is already listed.
- `note` — free text, optional. Use it when the run leaves something worth remembering
  (e.g. which sessions were sampled vs skipped).
- `source_cwd` — **only if the entry has none yet.** Take it from the `cwd` field on the JSONL
  lines; do **not** derive it by decoding the project directory name, which encodes whatever
  the CWD happened to be and under a worktree points below the repository root. For a
  directory name containing `--claude-worktrees-`, cut at the marker and record the parent
  project's repository root (`references/claude-data-format.md` has the measured examples).
- `last_commit_synced` — **do not write it.** History ingest never looks at a git repository,
  so there is no SHA to record. Leave any existing value untouched.

Per-run counts (conversations, memory files, desktop sessions, audit logs) do **not** go here.
The `log.md` line below already carries them, and the `sources` entries hold the per-file record.

### Create journal entry + update special files

Update `index.md` and `log.md` per the standard process:

```
- [TIMESTAMP] CLAUDE_HISTORY_INGEST projects=N conversations=M desktop_sessions=D audit_logs=A pages_updated=X pages_created=Y mode=append|full
```

`[TIMESTAMP]` is the output of `date -u +%Y-%m-%dT%H:%M:%SZ` — run it and paste the result verbatim, never hand-write it (why: schema doc, `log.md`).

**`hot.md`** — Read `$OBSIDIAN_VAULT_PATH/hot.md`. `hot.md` is a cache: one line per entry, nothing accumulates.

⚠️ **Change it only with `Edit` on the smallest span that identifies the spot — the line you are
replacing, not the section around it. Never write the file whole** (why: schema doc, Special Files).

- **`## Recent Activity`** — replace with one line for this run — e.g. "Ingested 5 Claude conversations across 2 projects; surfaced patterns in API design and testing strategy." — keeping the last 3 operations only.
- **`## Active Threads`** — replace with one line per thread, 3 max, dropping threads that are no longer active. **The patterns you surfaced do not go here** — they belong in the pages you just wrote. If the section is absent from the file, leave it out rather than adding it.
- **Update the `updated:` field in the frontmatter** to the current timestamp — this is easy to forget; the body edit and the frontmatter bump must both happen.

If the file does not exist, create it with exactly the skeleton in `~/.claude/doc/doc_wiki_schema.md`
(Special Files → `hot.md`) and then fill the sections. There is no takeaways section — deliberately.

## Privacy

- Distill and synthesize — don't copy raw conversation text verbatim
- Skip anything that looks like secrets, API keys, passwords, tokens
- If you encounter personal/sensitive content, ask the user before including it
- The user's conversations may reference other people — be thoughtful about what goes in the wiki

## Reference

See `references/claude-data-format.md` for more details on the data structures.

