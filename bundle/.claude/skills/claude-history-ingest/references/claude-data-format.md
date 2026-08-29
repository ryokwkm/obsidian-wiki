# Claude Code Data Format — Detailed Reference

## Projects Directory

`~/.claude/projects/` contains one directory per project the user has opened with Claude Code. Directory names encode the absolute path:

```
/Users/name/Documents/projects/my-app → -Users/name/Documents/projects/my-app
```

To recover the original path: replace leading `-` with `/`, then replace remaining `-` cautiously (dashes also appear in directory names). The `cwd` field in session/conversation data gives you the canonical path.

### ⚠️ Entering a git worktree splits one session across two project directories

The project directory is derived from the session's CWD, so **moving into a git worktree moves the session's storage**. A session that starts in `~/source/note/<repo>` and then enters a worktree under `<repo>/.claude/worktrees/<name>` writes its later transcript and subagent logs to a *different* directory:

```
-Users-name-source-note-<repo>/                          # before entering the worktree
-Users-name-source-note-<repo>--claude-worktrees-<name>/ # after entering it
```

The doubled dash is not a separator convention — **dots collapse to dashes too**, so `<repo>/.claude/worktrees/<name>` encodes as `<repo>--claude-worktrees-<name>`. Observed 2026-08-12 in a live `~/.claude/projects/`:

```
-Users-name-projects-my-repo
-Users-name-projects-my-repo--claude-worktrees-fix-login
-Users-name-projects-my-repo--claude-worktrees-fix-login-sub-dir
```

Consequences for this skill:

- **A path captured before the move is stale.** Any transcript or subagent-log path recorded earlier in the session no longer resolves once the worktree is entered — re-derive it from the current CWD instead of reusing the old path.
- **One logical session can appear as two projects.** Because the scan walks `~/.claude/projects/` by directory, the first and second halves of the same session are found separately. Correlate them by `sessionId` (present on every JSONL line) rather than by directory.
- **Decoding the directory name gives a CWD, not the repository.** The suffix is whatever the CWD was, so it can descend past the worktree root (`…-fix-login-sub-dir` above was `…/worktrees/fix-login/sub/dir`). Cut the name at `--claude-worktrees-` and keep the left side as the project, or the vault gets extra project pages for what is one repository. `cwd` on the JSONL lines is still the authoritative path.
- Worktrees are frequently deleted after merging, so these directories accumulate as history for paths that no longer exist on disk. Do not treat a missing CWD as a reason to skip the transcript.

### Conversation JSONL Files

Located at `~/.claude/projects/<project-dir>/<session-uuid>.jsonl`.

Each line is one event. Relevant event types:

| `type`                  | What it is                  | Worth reading?                           |
| ----------------------- | --------------------------- | ---------------------------------------- |
| `user`                  | User message                | Yes — this is what the user asked/said   |
| `assistant`             | Assistant response          | Yes — extract `text` blocks from content |
| `progress`              | Tool execution progress     | No — internal plumbing                   |
| `file-history-snapshot` | File state at session start | No — just file listings                  |

#### User message structure

```json
{
  "type": "user",
  "message": { "role": "user", "content": "the user's message as a string" },
  "timestamp": "2026-03-15T10:30:00.000Z",
  "sessionId": "uuid",
  "cwd": "/Users/name/Documents/projects/my-app"
}
```

#### Assistant message structure

```json
{
  "type": "assistant",
  "message": {
    "role": "assistant",
    "content": [
      { "type": "thinking", "text": "internal reasoning (skip this)" },
      { "type": "text", "text": "The actual visible response" },
      {
        "type": "tool_use",
        "id": "...",
        "name": "Read",
        "input": { "file_path": "..." }
      }
    ]
  },
  "timestamp": "2026-03-15T10:30:05.000Z"
}
```

**Extraction strategy:** Only pull `text` type blocks from assistant content arrays. The `thinking` blocks are internal reasoning and `tool_use` blocks are mechanical actions — neither adds wiki-worthy knowledge.

### Memory Files

Located at `~/.claude/projects/<project-dir>/memory/`.

Each memory file has YAML frontmatter:

```markdown
---
name: descriptive-name
description: one-line summary used for relevance matching
type: user|feedback|project|reference
---

The memory content. For feedback/project types, structured as:
rule/fact, then **Why:** and **How to apply:** lines.
```

**Memory types and their wiki value:**

| Type        | Contains                                 | Maps to wiki                                           |
| ----------- | ---------------------------------------- | ------------------------------------------------------ |
| `user`      | User's role, preferences, expertise      | Entity page about the user, or context for other pages |
| `feedback`  | Workflow corrections and confirmations   | Skills pages — "how to work effectively"               |
| `project`   | Active work, goals, decisions, deadlines | Entity pages for projects                              |
| `reference` | Pointers to external resources           | Reference pages                                        |

`MEMORY.md` in each memory directory is an index with one-line summaries. Read it first to triage.

### Session Metadata

Located at `~/.claude/sessions/<pid>.json`. Light metadata:

```json
{
  "pid": 12345,
  "sessionId": "uuid",
  "cwd": "/Users/name/Documents/projects/my-app",
  "startedAt": "2026-03-15T10:30:00.000Z",
  "kind": "interactive",
  "entrypoint": "cli"
}
```

Useful for building a timeline of when the user worked on what.

### Global History

`~/.claude/history.jsonl` — append-only log of all sessions. Use for timeline reconstruction.

## Processing Order

For maximum efficiency:

1. **MEMORY.md indexes** — Quick triage of what each project knows
2. **Individual memory files** — Pre-distilled knowledge, highest signal-to-noise
3. **Conversation JSONL** — Rich but verbose, process selectively
4. **Session metadata** — Only if you need timeline context
