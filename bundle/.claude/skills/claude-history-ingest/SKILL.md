---
name: claude-history-ingest
description: Claude Code の会話履歴（~/.claude/projects のセッションログ）を Obsidian wiki へ取り込み、過去のセッションから知見を抽出する。「Claude の履歴を処理して」「会話を wiki に追加して」「Claude と何を話したっけ」や英語の "process my Claude history" / "add my conversations to the wiki" と言われたとき、.claude フォルダ・セッションデータ・過去の会話ログに言及されたときに使う。
---

# Claude History Ingest — 会話から知識を掘り出す

ユーザーの過去の Claude Code の会話から知識を抽出し、Obsidian wiki へ蒸留する。会話は情報が豊かだが雑然としている —— シグナルを見つけてまとめ上げるのがこの仕事だ。

## 着手前に

1. **設定を解決する** — `OBSIDIAN_VAULT_PATH` が既に export されていればそれを使う（shell rc / direnv / 親プロセス）。無ければ CWD から `$HOME` まで遡って `OBSIDIAN_VAULT_PATH=` を含む `.env` を探し、最初に見つかったものを採る。どちらも無ければ止まり、`.claude/settings.json`（`env`）・shell rc・direnv のどれかで設定するようユーザーに伝える —— パスを決め打ちしたり vault を推測したりしない。`CLAUDE_HISTORY_PATH` も同じ方法で読む（既定は `~/.claude`）
2. vault のルートにある `.manifest.json` を読み、何が取り込み済みかを確かめる
3. 既存のページを探すため、抽出する話題で vault のルートにある `index.md` を Grep する。丸ごと読むのは grep がすべて空で返ったときだけ
4. **プロジェクトの絞り込み** —— 環境変数から `WIKI_SKIP_PROJECTS` を読む: カンマ区切りの部分文字列で、未設定か空なら何も飛ばさない。名前にそのどれかを含むプロジェクトディレクトリを、下の**すべての**手順（スキャン・差分・サンプリング・manifest への書き込み）から除外する。ユーザーがこの回だけ飛ばすプロジェクトを追加で挙げたら、それも加える。除外は**1 回だけ、一律に**かける —— 個々のコマンドに `grep -v` のフィルタを手書きしない。手書きするとスキャンと manifest の手順の間で食い違っていく。

## 取り込みモード

### 追記モード（既定）

ソースファイル（会話の JSONL・メモリファイル）ごとに `.manifest.json` を確かめる。処理するのは次のものだけ:

- manifest に無いファイル（新しい会話・新しいメモリファイル・新しいプロジェクト）
- 更新時刻が manifest の `ingested_at` より新しいファイル

たいていはこれでよい —— ユーザーは新しいセッションをいくつか走らせ、その差分を取り込みたいのだから。

> **manifest とパスを突き合わせる。** *この* skill のソースは
> `~/.claude/` の下にあるので、ファイルを「新規」と判断する前に `~` と環境変数を展開する。
> **manifest そのものを「正規化」しない** —— プロジェクト相対のキーはそのままで正しい。
> 完全一致のキーで引いて外れたら、basename で引き直してパスの末尾一致も同じソースと認め、
> そのうえで初めてソースを新規と結論する。規則と理由:
> `~/.claude/doc/doc_wiki_schema.md`。

### 生の JSONL を読む

生の JSONL ファイルは 80〜90% がノイズである: バイト数では `tool_use` ブロック・`thinking` ブロック・`progress` イベント・
`file-history-snapshot` エントリが大半を占める。読みながらノイズを除き（方法は Step 3 にある）、
大きなファイルに備えて予算を見積もる: 1 回の実行で特徴をつかめるセッションは、下の会話のサンプリングの目安が
示すより少ないと見込む。

### 会話のサンプリングの目安

履歴のパスには会話の JSONL が数百本入っていることもある —— 全部を読もうとしない。プロジェクトごとに:

- **プロジェクトに既にメモリファイルがあれば**（`memory/*.md`）、まずそれを取り込み（蒸留済みの
  シグナルである）、そのうえで **manifest にまだ無い会話も処理する** —— メモリが豊富なプロジェクトでも、
  新しい会話は取り込む。
- **プロジェクトにメモリファイルが無ければ**、特徴をつかむために**最新の 3 件**の会話（mtime 順）だけを
  読む。生の JSONL は高くつくので、3 はノルマではなく上限として扱う ——
  大きなセッション 1 件で予算を使い切ることもある。
- サンプリングしたものとスキップしたものを必ず報告する（例: 「agenttower: メモリファイル 7 件 + 新しい会話 4 件を
  取り込み、変更の無い会話 14 件をスキップ」）。取り込めていない範囲が黙って残らず、見えるようにするため。

### 全量モード

manifest にかかわらずすべてを処理する。vault を手で空にした後か、ユーザーが明示的に求めたときに使う。

## Claude Code のデータ配置

Claude Code はデータを 2 か所に保存する。**両方**をスキャンする。

### Source 1: `~/.claude/`（CLI セッション）

```
~/.claude/
├── projects/                          # プロジェクトごとのディレクトリ
│   ├── -Users-name-project-a/         # パスから作った名前（スラッシュ → ダッシュ）
│   │   ├── <session-uuid>.jsonl       # 会話のデータ（JSONL）
│   │   └── memory/                    # 構造化されたメモリ
│   │       ├── MEMORY.md              # メモリの索引
│   │       ├── user_*.md              # ユーザーのプロフィールのメモリ
│   │       ├── feedback_*.md          # 作業の進め方へのフィードバックのメモリ
│   │       └── project_*.md           # プロジェクトの文脈のメモリ
│   ├── -Users-name-project-b/
│   │   └── ...
├── sessions/                          # セッションのメタデータ（JSON）
│   └── <pid>.json                     # {pid, sessionId, cwd, startedAt, kind, entrypoint}
├── history.jsonl                      # 全体のセッション履歴
├── tasks/                             # サブエージェントのタスクのデータ
├── plans/                             # 保存されたプラン
└── settings.json
```

### Source 2: `~/Library/Application Support/Claude/local-agent-mode-sessions/`（デスクトップアプリのエージェントセッション）

> **まず事前確認する。** 多くのユーザーは CLI しか使わず、デスクトップのセッションを持たない。下の構造を辿る前に、空でないことを確かめる:
> ```bash
> DESKTOP_SESSIONS="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"
> [ -d "$DESKTOP_SESSIONS" ] && find "$DESKTOP_SESSIONS" -name "audit.jsonl" | head -1
> ```
> 何も出力されなければ、この節全体（Source 2 + Step 3b）を飛ばし、飛ばしたことを語らない。

Claude デスクトップアプリは、ローカルのエージェントモードのセッションをここに保存する。構造は深く入れ子になっている:

```
~/Library/Application Support/Claude/local-agent-mode-sessions/
└── <outer-uuid>/
    └── <inner-uuid>/
        ├── local_<session-uuid>.json          # セッションのメタデータ
        └── local_<session-uuid>/
            ├── audit.jsonl                    # 監査ログ —— ツール呼び出し・ファイルの読み取り・実行したコマンド
            └── .claude/
                └── projects/
                    └── <path-encoded-name>/   # ~/.claude/projects/ と同じパスのエンコード
                        └── <uuid>.jsonl       # 会話ログ（CLI と同じ JSONL 形式）
```

**local-agent-mode のセッションをすべて見つける方法:**

```bash
# セッションのメタデータファイルをすべて探す
find ~/Library/Application\ Support/Claude/local-agent-mode-sessions -name "local_*.json" -maxdepth 4

# 監査ログをすべて探す
find ~/Library/Application\ Support/Claude/local-agent-mode-sessions -name "audit.jsonl"

# 会話ログをすべて探す
find ~/Library/Application\ Support/Claude/local-agent-mode-sessions -name "*.jsonl" -path "*/.claude/projects/*"
```

**セッションのメタデータ（`local_<uuid>.json`）** —— `sessionId`・`cwd`・`startedAt`・`model`・`title` などのフィールドを持つ JSON ファイル。会話ログを開く前にまずこれを読み、セッションの文脈をつかむ。

**監査ログ（`audit.jsonl`）** —— 各行が、エージェントの 1 つの操作を記録した JSON レコード: ツール呼び出し（Read・Write・Bash・Edit）、ファイルへのアクセス、実行したシェルコマンド、MCP 呼び出し。*エージェントが実際に何をしたか*を理解するのに役立つ —— 会話の本文だけより豊かなシグナルになることが多い。フィールド: `type`・`toolName`・`input`・`output`・`timestamp`・`sessionId`。

**会話ログ（`.claude/projects/.../<uuid>.jsonl`）** —— CLI の会話 JSONL と同一の形式。`~/.claude/projects/*/*.jsonl` と同じように解析する。

### 価値の高い順に並べた主なデータソース（両方の場所を合わせて）:

1. **メモリファイル**（`~/.claude/projects/*/memory/*.md`）—— 蒸留済みで、既に wiki に載せやすい形。最上の素材。
2. **会話の JSONL**（`~/.claude/projects/*/*.jsonl` とデスクトップアプリの会話ログの両方）—— 会話の全記録。豊かだがノイズが多い。
3. **監査ログ**（デスクトップのセッションの `audit.jsonl`）—— 何が行われたかをツール呼び出しの粒度で記録したもの。会話が乏しいときでも、具体的な操作・ファイルのパターン・コマンドのパターンを抽出するのに役立つ。
4. **セッションのメタデータ**（`sessions/*.json` と `local_*.json`）—— どのプロジェクトか、いつか、CWD は何かが分かる。

## Step 1: 全体を調べて差分を求める

両方のデータの場所をスキャンし、`.manifest.json` と突き合わせる:

```bash
# --- Source 1: CLI セッション（~/.claude） ---
# プロジェクトをすべて探す
Glob: ~/.claude/projects/*/

# メモリファイルを探す（最も価値が高い）
Glob: ~/.claude/projects/*/memory/*.md

# 会話の JSONL ファイルを探す
Glob: ~/.claude/projects/*/*.jsonl

# --- Source 2: デスクトップアプリの local-agent-mode セッション ---
DESKTOP_SESSIONS="$HOME/Library/Application Support/Claude/local-agent-mode-sessions"

# セッションのメタデータ
find "$DESKTOP_SESSIONS" -name "local_*.json" -maxdepth 4

# 監査ログ
find "$DESKTOP_SESSIONS" -name "audit.jsonl"

# 会話ログ
find "$DESKTOP_SESSIONS" -name "*.jsonl" -path "*/.claude/projects/*"
```

1 つにまとめた一覧を作り、ファイルごとに分類する:

- **新規** —— manifest に無い → 取り込みが要る
- **変更あり** —— manifest にあるが、ファイルの方が新しい → 取り込み直しが要る
- **変更なし** —— manifest にあり、変更されていない → 追記モードでは飛ばす

ユーザーに報告する: 「CLI のプロジェクトを X 件、デスクトップのセッションを Y 件見つけました。メモリファイル: A。会話: B。監査ログ: C。差分: 新規 D・変更あり E。」

## Step 2: まずメモリファイルを取り込む

メモリファイルは既に YAML frontmatter で構造化されている:

```markdown
---
name: memory-name
description: one-line description
type: user|feedback|project|reference
---

ここにメモリの本文。
```

メモリファイルごとに:

- 読んで frontmatter を解析する
- `user` 型 → ユーザーについての entity ページか、ユーザーの領域についての concept ページの材料になる
- `feedback` 型 → skills ページの材料になる（作業の進め方のパターン・うまくいくこと・いかないこと）
- `project` 型 → そのプロジェクトの entity ページの材料になる
- `reference` 型 → 外部の資料を指す reference ページの材料になる

各プロジェクトの `MEMORY.md` は索引ファイルで、手早く読める要約である —— まずこれを読み、どの個別のメモリファイルを全文読む価値があるかを決める。

## Step 3: 会話の JSONL を解析する

入力は `~/.claude/projects/<proj>/<uuid>.jsonl` にある生の JSONL。

**生の JSONL を読む:** 各行が 1 つの JSON オブジェクト:

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

アシスタントのメッセージでは、`content` が content ブロックの配列のことがある:

```json
{
  "content": [
    {"type": "thinking", "thinking": "..."},
    {"type": "text", "text": "The actual response..."},
    {"type": "tool_use", "name": "Read", "input": {...}}
  ]
}
```

- `type: "user"` と `type: "assistant"` のエントリだけに絞る
- アシスタントのエントリからは `text` ブロックを抽出する（`thinking` と `tool_use` は飛ばす —— ノイズである）
- `cwd` フィールドで、この会話がどのプロジェクトのものかが分かる
- `type: "progress"` は飛ばす —— エージェント内部の進捗の更新
- `type: "file-history-snapshot"` は飛ばす —— ファイルの状態の追跡
- サブエージェントの会話（`subagents/` サブディレクトリの下）は飛ばす —— ユーザーが求めない限り

## Step 3b: 監査ログを解析する（デスクトップのセッションのみ）

`local-agent-mode-sessions/` の下で見つけた `audit.jsonl` ごとに、1 行ずつ読む。各行が、エージェントの 1 つの操作を記録した JSON レコード:

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

**監査ログから抽出するもの:**

- **ファイルへのアクセスのパターン** —— エージェントが繰り返し Read や Edit するのはどのファイルか？ それがプロジェクトの中で価値の高いファイルである。プロジェクトの参照として書き留める。
- **シェルコマンド** —— 繰り返し現れる Bash コマンドから、プロジェクトのビルド・テスト・デプロイの手順が分かる。これを `skills/` のページへ蒸留する（例: 「このプロジェクトのビルドとテストの方法」）。
- **ツール呼び出しの並び** —— エージェントがいつも Read → Edit → Bash を決まった順で行うなら、それは書き留める価値のある作業のパターンである。
- **エラーのパターン** —— 失敗したツール呼び出し（0 以外の終了コード・エラー出力）から、つまずきどころ・既知の粗い部分・繰り返すバグが分かる。
- **MCP ツールの呼び出し** —— MCP ツールの呼び出しから、プロジェクトがどの外部サービスや API と連携しているかが分かる。

**監査ログから飛ばすもの:**

- パターンの無い定型的なファイルの読み取り（例: 設定ファイルを 1 回読むだけ）
- ノイズでしかないツールの出力（長いスタックトレース・冗長なログ）—— 出力全体ではなく、エラーの種類を要約する
- コマンドの引数や出力の中にある、秘密情報・トークン・認証情報らしきものすべて

**会話ログと突き合わせる:** 監査ログは*何が起きたか*を、会話は*なぜか*を教えてくれる。同じセッションで両方が手に入るなら、組み合わせて使う —— 監査ログが会話を具体的な操作に結びつける。

監査ログを処理する前に、対になる `local_<uuid>.json` のセッションのメタデータを読む —— 操作の文脈をつかむための `cwd`・`startedAt`・`title` が得られる。

## Step 4: 話題ごとにまとめる

会話 1 つにつき wiki ページを 1 つ作らない。代わりに:

- 抽出した知識を、会話をまたいで**話題ごとに**まとめる
- 「認証のデバッグ + CI の構築」についての 1 つの会話 → 別々の 2 つの話題
- 別々の日の「React のパフォーマンス」についての 3 つの会話 → 1 つにまとめた話題
- プロジェクトのディレクトリ名が、自然な第 1 階層のまとまりになる

## Step 5: wiki ページへ蒸留する

Claude の各プロジェクトは、vault のプロジェクトディレクトリに対応する。`~/.claude/projects/` のプロジェクトディレクトリ名は元のパスをエンコードしている —— デコードして整ったプロジェクト名を得る:

```
-Users-name-Documents-projects-my-Project   → myproject
-Users-name-Documents-projects-Another-app  → anotherapp
```

`--claude-worktrees-` を含む名前は**新しいプロジェクトではなく、別のプロジェクトの git worktree** である: 名前をその目印で切って左側を使い、worktree のセッションが既存のプロジェクトページに入るようにする。詳細と実測した例は `references/claude-data-format.md` にある。

### プロジェクト固有の知識とグローバルな知識

| 見つけたもの | 置き場 | 例 |
|---|---|---|
| プロジェクトのアーキテクチャ上の判断 | `projects/<name>/concepts/` | `projects/my-project/concepts/main-architecture.md` |
| プロジェクト固有のデバッグ | `projects/<name>/skills/` | `projects/my-project/skills/api-rate-limiting.md` |
| ユーザーが学んだ一般的な概念 | `concepts/`（グローバル） | `concepts/react-server-components.md` |
| プロジェクトをまたいで繰り返す問題 | `skills/`（グローバル） | `skills/debugging-hydration-errors.md` |
| 使っているツール・サービス | `entities/`（グローバル） | `entities/vercel-functions.md` |
| 多くの会話にまたがるパターン | `synthesis/`（グローバル） | `synthesis/common-debugging-patterns.md` |

中身のあるプロジェクトごとに、`projects/<name>/<name>.md` のプロジェクト概要ページを作成・更新する —— **`_project.md` ではなく、プロジェクト名で付ける**（Obsidian のグラフビューはファイル名をノードのラベルに使う。理由は schema doc にある）。

**重要:** 会話ではなく*知識*を蒸留する。「3 月 15 日の会話で、ユーザーは X について尋ねた。」とは書かない。知識そのものを書き、会話は出典として示す。

**`summary:` frontmatter フィールドを書く。** 新規・更新したすべてのページに、1〜2 文・200 字以内で、ページを開いていない読み手に向けて「このページは何についてか？」に答える。`wiki-query` の安価な検索経路は、ページ本文を開かずに済ませるためにこのフィールドを読む。

新規ページすべての frontmatter に **confidence と lifecycle のフィールドを足す**:
```yaml
base_confidence: 0.42
lifecycle: draft                # 下限。セッションの会話ログは、その中の主張自体の証拠にならない ——
                                # 会話ログに確認が実際に走った様子が出ているときだけ昇格させる
lifecycle_changed: <ISO date today>
```

値・段・昇格の規則は 1 か所にだけある —— **`~/.claude/doc/doc_wiki_lifecycle_rubric.md`**。`lifecycle` の値を書いたり変えたりする前にそれを読む。その値の一覧をどこにも写さない。特に注意すること: 確認が通ったと言っている会話ログは確認そのものではない（メタ検証では昇格しない）。そして最上位の 2 つの段は人間だけのもので、AI は決して書かない。

更新時は、段を上げる確認が走った様子を会話ログそのものが示していない限り、`lifecycle` と `lifecycle_changed` を変えない —— 示しているなら、ルーブリックに従って段を付け直し、`lifecycle_evidence` / `evidence_at` も合わせて更新する。

**provenance を付ける。** `~/.claude/doc/doc_wiki_schema.md`（Provenance Markers）の規約に従う: すべての主張にマーカーを付ける —— ソースが言っていることの言い換えには `^[extracted]`、統合して導いた主張には `^[inferred]`、異論があるか不明瞭なものには `^[ambiguous]`。主張でないもの（見出し・表・コード）には付けず、数えない。

- **メモリファイル**はおおむね extracted —— ユーザーが手で書いたもので、既に蒸留されている。複数のメモリファイルの主張をつなぎ合わせているのでない限り、メモリ由来の主張は extracted として扱う。
- **会話からの蒸留**はおおむね inferred。多くのやり取りから筋の通った主張を組み立てており、暗黙の推論を補うことも多い。統合して得たパターン・セッションをまたぐ一般化・「ユーザーが本当に言いたかったこと」の解釈には、`^[inferred]` を惜しまず付ける。
- セッションをまたいでユーザーの考えが変わったとき、またはアシスタントとユーザーが食い違い、決着がはっきりしないときは `^[ambiguous]` を使う。
- 新規・更新したすべてのページに、マーカーの実数から `provenance:` frontmatter ブロックを書く（数え方のレシピは同じ schema の節にある。分母はマーカーの総数）。

## Step 6: manifest・ジャーナル・特殊ファイルを更新する

### `.manifest.json` を更新する

処理したソースファイルごとに、次の内容でエントリを追加・更新する:

- `ingested_at`, `size_bytes`, `modified_at`
- `source_type`: `"claude_conversation"`・`"claude_memory"`・`"claude_audit_log"`・`"claude_desktop_session"` のいずれか
- `project`: デコードしたプロジェクト名
- `pages_created` と `pages_updated` のリスト

manifest の `projects` 節も更新する。**キーの集合は
`~/.claude/doc/doc_wiki_schema.md`（`.manifest.json` 節）で定義されている —— それに従い、ここで独自の
フィールドを作り出さない。** `.projects["<name>"] += {…}` の形の 1 本の `jq` コマンドで書く。

⚠️ **キー単位でマージする —— エントリを決して置き換えない。** `wiki-update` も同じリポジトリのエントリを同じキーで
書いており、`source_cwd` / `last_commit_synced` はそちらから来る。
オブジェクトを丸ごと代入する（`jq '.projects["<name>"] = {…}'`）とそれらが落ち、`wiki-query` の
`Source code:` の行が出なくなり、次回の差分計算
（`git merge-base --is-ancestor <last_commit_synced> HEAD`）がプロジェクト全体の再スキャンになる。
同じリポジトリのエントリを綴りの違う名前で 2 つ目として足さず、manifest に既にあるキーを
使い回す。

この手順がエントリに書くもの —— これ以外は書かない:

- `last_synced` —— この実行での `date -u +%Y-%m-%dT%H:%M:%SZ` の出力。
- `pages_in_vault` —— 書いたページを、既に載っているものと重複しないように追記する。
- `note` —— 自由記述・任意。その実行で覚えておく価値のあることが残ったときに使う
  （例: どのセッションをサンプリングし、どれをスキップしたか）。
- `source_cwd` —— **エントリにまだ無いときだけ。** JSONL の各行の `cwd` フィールドから取る。
  プロジェクトのディレクトリ名をデコードして導くことは**しない** —— ディレクトリ名はそのときたまたまの CWD を
  エンコードしたもので、worktree の下ではリポジトリのルートより下を指す。`--claude-worktrees-` を含む
  ディレクトリ名なら、その目印で切り、親プロジェクトのリポジトリのルートを記録する
  （実測した例は `references/claude-data-format.md` にある）。
- `last_commit_synced` —— **書かない。** 履歴の取り込みは git リポジトリを一切見ないので、
  記録する SHA が無い。既にある値には手を付けない。

実行ごとの件数（会話・メモリファイル・デスクトップのセッション・監査ログ）は、ここには**書かない**。
それは下の `log.md` の行が既に持っており、ファイルごとの記録は `sources` のエントリが持つ。

### ジャーナルのエントリを作り、特殊ファイルを更新する

標準の手順どおりに `index.md` と `log.md` を更新する:

```
- [TIMESTAMP] CLAUDE_HISTORY_INGEST projects=N conversations=M desktop_sessions=D audit_logs=A pages_updated=X pages_created=Y mode=append|full
```

`[TIMESTAMP]` は `date -u +%Y-%m-%dT%H:%M:%SZ` の出力 —— 実行して結果をそのまま貼る。手で書かない（理由: schema doc の `log.md`）。

**`hot.md`** —— `$OBSIDIAN_VAULT_PATH/hot.md` を読む。`hot.md` はキャッシュで、1 エントリ 1 行。ここには何も溜めない。

⚠️ **変更は、その箇所を特定できる最小の範囲への `Edit` だけで行う —— 置き換える行であって、その周りの節ではない。
ファイルを丸ごと書かない**（理由: schema doc の Special Files）。

- **`## Recent Activity`** —— この実行について 1 行、新しい順。1 回の `Edit` で先頭に入れる —— 例: 「2 つのプロジェクトにまたがる Claude の会話 5 件を取り込み、API 設計とテスト戦略のパターンを掘り出した。」節が既に 3 件を持っていれば、最も古い行を**別の** `Edit` で消す（両方を一度にやると、節全体を `old_string` に入れることになる）。
- **`## Active Threads`** —— スレッド 1 つにつき 1 行、最大 3 件で置き換え、もう動いていないスレッドは落とす。**掘り出したパターンはここに書かない** —— それらはいま書いたページに置く。この節がファイルに無ければ、足さずに無いままにする。
- **frontmatter の `updated:` フィールドを現在のタイムスタンプに更新する** —— 忘れやすい。本文の編集と frontmatter の更新は必ず両方行う。

ファイルが無ければ、`~/.claude/doc/doc_wiki_schema.md` の雛形（Special Files → `hot.md`）どおりに作り、
それから各節を埋める。教訓の節は無い —— 意図的に置いていない。

## プライバシー

- 蒸留して統合する —— 会話の生のテキストをそのまま写さない
- 秘密情報・API キー・パスワード・トークンらしきものはすべて飛ばす
- 個人的な内容や機微な内容に出会ったら、含める前にユーザーに尋ねる
- ユーザーの会話は他の人に触れていることがある —— wiki に何を入れるかは慎重に考える

## 参照

データ構造の詳細は `references/claude-data-format.md` を参照。

