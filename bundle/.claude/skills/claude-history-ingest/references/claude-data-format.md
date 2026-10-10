# Claude Code のデータ形式 — 詳細リファレンス

## プロジェクトのディレクトリ

`~/.claude/projects/` には、ユーザーが Claude Code で開いたプロジェクトごとに 1 つのディレクトリがある。ディレクトリ名は絶対パスをエンコードしている:

```
/Users/name/Documents/projects/my-app → -Users/name/Documents/projects/my-app
```

元のパスを復元するには: 先頭の `-` を `/` に置き換え、残りの `-` は慎重に置き換える（ディレクトリ名そのものにもダッシュが現れる）。セッション・会話のデータにある `cwd` フィールドが正規のパスを与える。

### ⚠️ git worktree に入ると、1 つのセッションが 2 つのプロジェクトディレクトリに分かれる

プロジェクトディレクトリはセッションの CWD から導かれるので、**git worktree に移るとセッションの保存先も移る**。`~/source/note/<repo>` で始まり、その後 `<repo>/.claude/worktrees/<name>` の下の worktree に入ったセッションは、以降の会話ログとサブエージェントのログを*別の*ディレクトリに書く:

```
-Users-name-source-note-<repo>/                          # worktree に入る前
-Users-name-source-note-<repo>--claude-worktrees-<name>/ # 入った後
```

二重のダッシュは区切りの慣習ではない —— **ドットもダッシュに潰れる**ので、`<repo>/.claude/worktrees/<name>` は `<repo>--claude-worktrees-<name>` とエンコードされる。2026-08-12 に実際の `~/.claude/projects/` で観測した:

```
-Users-name-projects-my-repo
-Users-name-projects-my-repo--claude-worktrees-fix-login
-Users-name-projects-my-repo--claude-worktrees-fix-login-sub-dir
```

この skill にとっての帰結:

- **移る前に控えたパスは古くなっている。** セッションの前半で記録した会話ログやサブエージェントのログのパスは、worktree に入った時点で解決できなくなる —— 古いパスを使い回さず、現在の CWD から導き直す。
- **論理的には 1 つのセッションが、2 つのプロジェクトとして現れうる。** スキャンは `~/.claude/projects/` をディレクトリ単位で辿るので、同じセッションの前半と後半が別々に見つかる。ディレクトリではなく `sessionId`（JSONL のすべての行にある）で対応づける。
- **ディレクトリ名をデコードして得られるのは CWD であって、リポジトリではない。** 末尾はそのときの CWD そのままなので、worktree のルートより下まで降りることがある（上の `…-fix-login-sub-dir` は `…/worktrees/fix-login/sub/dir` だった）。名前を `--claude-worktrees-` で切って左側をプロジェクトとして残す。さもないと、1 つのリポジトリなのに vault に余分なプロジェクトページができる。正となるパスは、引き続き JSONL の各行の `cwd` である。
- worktree はマージ後に削除されることが多いので、これらのディレクトリは、もうディスク上に無いパスの履歴として溜まっていく。CWD が無いことを、会話ログを飛ばす理由にしない。

### 会話の JSONL ファイル

場所は `~/.claude/projects/<project-dir>/<session-uuid>.jsonl`。

各行が 1 つのイベント。関係するイベントの種類:

| `type` | 何か | 読む価値は？ |
|---|---|---|
| `user` | ユーザーのメッセージ | ある —— ユーザーが尋ねたこと・言ったこと |
| `assistant` | アシスタントの応答 | ある —— content から `text` ブロックを抽出する |
| `progress` | ツール実行の進捗 | ない —— 内部処理 |
| `file-history-snapshot` | セッション開始時のファイルの状態 | ない —— ファイルの一覧にすぎない |

#### ユーザーメッセージの構造

```json
{
  "type": "user",
  "message": { "role": "user", "content": "the user's message as a string" },
  "timestamp": "2026-03-15T10:30:00.000Z",
  "sessionId": "uuid",
  "cwd": "/Users/name/Documents/projects/my-app"
}
```

#### アシスタントメッセージの構造

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

**抽出の方針:** アシスタントの content 配列からは `text` 型のブロックだけを取り出す。`thinking` ブロックは内部の推論で、`tool_use` ブロックは機械的な操作 —— どちらも wiki に載せる価値のある知識を足さない。

### メモリファイル

場所は `~/.claude/projects/<project-dir>/memory/`。

各メモリファイルは YAML frontmatter を持つ:

```markdown
---
name: descriptive-name
description: one-line summary used for relevance matching
type: user|feedback|project|reference
---

メモリの本文。feedback/project 型では次の構造をとる:
ルール・事実、続いて **Why:** と **How to apply:** の行。
```

**メモリの型と wiki にとっての価値:**

| 型 | 中身 | wiki での対応先 |
|---|---|---|
| `user` | ユーザーの役割・好み・専門知識 | ユーザーについての entity ページ、または他のページの文脈 |
| `feedback` | 作業の進め方への訂正と確認 | skills ページ —— 「効果的に作業する方法」 |
| `project` | 進行中の作業・目標・判断・締め切り | プロジェクトの entity ページ |
| `reference` | 外部の資料へのポインタ | reference ページ |

各メモリディレクトリの `MEMORY.md` は、1 行の要約を並べた索引。まずこれを読んで仕分ける。

### セッションのメタデータ

場所は `~/.claude/sessions/<pid>.json`。軽いメタデータ:

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

ユーザーがいつ何に取り組んだかの時系列を組み立てるのに役立つ。

### グローバルな履歴

`~/.claude/history.jsonl` —— 全セッションの追記専用のログ。時系列の再構成に使う。

## 処理の順序

効率を最大にするために:

1. **MEMORY.md の索引** —— 各プロジェクトが何を知っているかを手早く仕分ける
2. **個別のメモリファイル** —— 蒸留済みの知識で、S/N 比が最も高い
3. **会話の JSONL** —— 豊かだが冗長なので、選んで処理する
4. **セッションのメタデータ** —— 時系列の文脈が要るときだけ
