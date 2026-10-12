# wiki スキーマ — vault へ書く / 引くときの規約

wiki バンドルの skill が共有する**データ規約**。ページの frontmatter、vault ルートの特殊ファイル、型付きリンク、
retrieval のコスト順序を定める。**vault へ書く直前**（ページ作成・frontmatter 更新・`index.md` / `log.md` /
`.manifest.json` の更新）と、**vault から引く直前**（どの primitive で読むかを決めるとき）に、
該当する節だけを読む。頭から通読する必要はない。

`lifecycle` の値・序列・判定手順だけはここに無い。唯一の正典は `~/.claude/doc/doc_wiki_lifecycle_rubric.md`
（→「confidence と lifecycle（Confidence and Lifecycle）」の節）。**値の一覧をこの doc や skill 本文へ書き写さないこと** —— 正典が 2 箇所に
分かれると skill ごとに違う値が書かれる。

## 見出し索引

| 節 | 何を決めるか |
|---|---|
| wiki の構成（Wiki Organization） | カテゴリ（何の知識か）・`projects/`（どこから来た知識か）・`_` 接頭辞の作業/原本ディレクトリ（`_source_docs/` = 一次資料の置き場） |
| 特殊ファイル（Special Files） | `index.md` / `log.md` / `.manifest.json` の形式・書き込み規約と、派生ビュー（`index.md` / `hot.md`）の同時更新の扱い |
| ページ雛形（Page Template） | 新規ページの frontmatter + 本文の雛形 |
| 予約システムタグ（Reserved System Tags） | `visibility/` 予約タグ 3 種とタグ語彙の置き場（枚数・形式に機械検査が無いことの注記付き） |
| provenance マーカー（Provenance Markers） | `^[extracted]` / `^[inferred]` / `^[ambiguous]` と frontmatter の `provenance:` |
| 型付きの関係（Typed Relationships） | `relationships:` の型（10 概念・16 綴り）と、文脈から型を推論する表 |
| confidence と lifecycle（Confidence and Lifecycle） | `base_confidence` の算出式と、lifecycle 正典へのポインタ |
| 重要度の tier（Importance Tiering） | `tier:` 3 段と昇格・降格の閾値（昇格に書き手がいないことの注記付き） |
| 読み取りプリミティブ（Retrieval Primitives） | vault を読むときのコスト順序（安い順に試す） |
| リンク形式（Link Format） | `OBSIDIAN_LINK_FORMAT` = `wikilink` / `markdown` の生成規則 |

## wiki の構成（Wiki Organization）

vault の構造は 2 段: **カテゴリ**（何の種類の知識か）と**プロジェクト**（その知識がどこから来たか）。

### カテゴリ

ページを次の既定カテゴリへ振り分ける（`OBSIDIAN_CATEGORIES` で変えられる）:

| カテゴリ | 用途 | 例 |
|---|---|---|
| `concepts/` | 考え方・理論・メンタルモデル | `concepts/transformer-architecture.md` |
| `entities/` | 人物・組織・ツール・プロジェクト | `entities/andrej-karpathy.md` |
| `skills/` | やり方の知識・手順 | `skills/fine-tuning-llms.md` |
| `references/` | 特定のソースの要約。学術論文は `wiki-ingest` が持つ、より詳しい論文深掘り用の雛形を使う | `references/attention-is-all-you-need.md` |
| `synthesis/` | ソースをまたぐ横断的な分析 | `synthesis/scaling-laws-debate.md` |
| `journal/` | タイムスタンプ付きの観察・セッションログ | `journal/2024-03-15.md` |

### プロジェクト

知識は特定のプロジェクトに属することが多い。`projects/` ディレクトリはそれを映す:

```
$OBSIDIAN_VAULT_PATH/
├── projects/
│   ├── my-project/
│   │   ├── my-project.md      ← プロジェクトの概要（プロジェクト名で付ける）
│   │   ├── concepts/          ← プロジェクト単位のカテゴリページ
│   │   ├── skills/
│   │   └── ...
│   ├── another-project/
│   │   └── ...
│   └── side-project/
│       └── ...
├── concepts/                   ← グローバル（プロジェクト横断）の知識
├── entities/
├── skills/
└── ...
```

**知識がプロジェクト固有のとき**（1 つのコードベースにしか当てはまらないデバッグ手法、プロジェクト固有のアーキテクチャ判断）は、`projects/<project-name>/<category>/` の下に置く。

**知識が一般的なとき**（"React Server Components" のような概念、"Andrej Karpathy" のような人物、広く使える技能）は、グローバルのカテゴリディレクトリに置く。

**相互参照:** プロジェクトのページはグローバルのページへ `[[wikilink]]` を張り、逆も同様にする。プロジェクトの概要ページは、そのプロジェクトに関わる主要な概念・技能・エンティティのページへリンクする —— プロジェクトの下にあるかグローバルにあるかを問わない。

**命名規則:** プロジェクトの概要ファイルは `_project.md` ではなく `<project-name>.md` と名付ける。Obsidian のグラフビューはファイル名をノードのラベルに使う —— `_project.md` だと全プロジェクトがグラフ上で `_project` と表示され、読めなくなる。だから `projects/my-project/my-project.md`、`projects/another-project/another-project.md` のようにする。

各プロジェクトのディレクトリには、次の構成の概要ページを置く:

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

このプロジェクトが何かを 1 段落で要約する。

## Key Concepts
- [[concepts/some-api]] — 中核機能に使う
- [[projects/my-project/concepts/main-architecture]] — プロジェクト固有のアーキテクチャ

## Related
- [[entities/some-service]] — デプロイ先のプラットフォーム
```

### 作業・原本ディレクトリ（`_` 接頭辞）

名前が `_` で始まるディレクトリは wiki ページではない: どの走査（`wiki-lint`・`wiki-dedup`・qmd のインデックス）もそこを飛ばす。現役のページがそこへリンクしてもよく、そのリンクはリンク切れではない。

| ディレクトリ | 置くもの | 書き手 |
|---|---|---|
| `_raw/` | 昇格待ちのクイックキャプチャの下書き | `wiki-capture --quick`（`wiki-ingest` が昇格させる） |
| `_staging/` | `WIKI_STAGED_WRITES=true` のときのレビュー待ちページ | `wiki-ingest` |
| `_archives/` | 作り直し・復元用の vault のスナップショット | アーカイブ操作 |
| `_source_docs/` | **一次資料** —— 取り込んだすべてのローカルファイルの逐語コピー（git に commit 済みでその後変更の無いファイルは除く。それはコピーの代わりにリポジトリ相対パスと `source_commit` で参照する）。名前は `<YYYY-MM-DD>-<元のファイル名>`。vault のコピーが記録上の原本で、`sources:` のエントリと manifest のキーはここを指し、ファイルを読んだ元のパスは決して指さない（ダウンロードフォルダは消される。上の git の例外は別）。置き場は `OBSIDIAN_SOURCES_DIR` で変えられる | `wiki-ingest`（Step 1） |

`_source_docs/` は**意図して検索インデックスから外してある**: 原本とそこから蒸留したページは近重複なので、両方をインデックスすると同じ結果の枠を奪い合い、蒸留で直した数字が同じ重みで再浮上する。原本へは、それを引用しているページを経由してたどる（`wiki-query` の Step 4）。

## 特殊ファイル（Special Files）

どの wiki もルートに次のファイルを持つ。

**派生ビュー（`index.md` / `hot.md`）は捨てて作り直せるキャッシュで、蒸留物の置き場ではない。** バイト上限は
env（`WIKI_INDEX_MAX_BYTES` / `WIKI_HOT_MAX_BYTES`）で測られる。超過したら上限を上げるのではなく、そこへ
書き足している側を直す。

**同時更新の前提**: vault は複数セッションが同時に触る。`index.md` / `hot.md` は**該当箇所だけを `Edit` で
書き換える**（`old_string` は直前に読んだテキストから採り、変更に必要な最小限のスパンに留める。ファイル全体を
`Write` で書き戻すと、読んでから書くまでの間に入った他セッションの追記が黙って消える。`Edit` は完全一致が要るので、
競合しても黙って消さずに失敗する —— それが望ましい挙動で、スパンが小さいほどその空振りも減る）。
`.manifest.json` は読んで考えてから書くのではなく、`jq` の 1 コマンドで読んで即書く（窓を秒未満にする）。

### `hot.md`
最近の活動を約 500 語に収めたキャッシュ —— 1 エントリ 1 行で、ここには何も溜めない。
気づき・教訓・判断はページ本文に置き、`hot.md` には決して書かない。ファイルが無ければ、
書き込む skill はどれも、必ずこの骨組みそのままで作る。**教訓の節は無い —— 書き漏れではなく
意図的に置いていない:**

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
内容を軸にした、カテゴリ別の目録。各エントリは 1 行の要約とタグを持つ。取り込み操作のたびに更新する。書式:

```markdown
# Wiki Index

## Concepts
- [[transformer-architecture]] — 系列モデリングの主流のアーキテクチャ ( #ml #architecture)
- [[attention-mechanism]] — transformer の中核の構成要素 ( #ml #fundamentals)

## Entities
- [[andrej-karpathy]] — AI 研究者・教育者、元 Tesla の AI ディレクター ( #person #ml)
```
**書式の規則**: 開き `(` とタグの間に空白を入れる。
❌ 誤: `description (#tag)` — タグの解析が壊れる
✅ 正: `description ( #tag)` — 空白が正しく、タグも解析できる

1 エントリは 1 行で、ページの `summary:` フィールドをそのまま写す（200 字以内）。エントリをそれより長くしない —— 文が長すぎるならページの `summary:` を直し、index のエントリはいじらない。

### `log.md`
すべての操作を記録する、時系列の追記専用の記録。各エントリは機械で解析できる:

```markdown
## Log

- [2024-03-15T10:30:42Z] INGEST source="papers/attention.pdf" pages_updated=12 pages_created=3
- [2024-03-15T11:04:07Z] QUERY query="How do transformers handle long sequences?" result_pages=4
- [2024-03-16T09:12:33Z] LINT issues_found=2 orphans=1 contradictions=1
- [2024-03-17T10:47:19Z] ARCHIVE reason="rebuild" pages=87 destination="_archives/..."
- [2024-03-17T10:52:08Z] REBUILD archived_to="_archives/..." previous_pages=87
```

**タイムスタンプはすべて `date -u +%Y-%m-%dT%H:%M:%SZ` の出力** —— 実行して結果をそのまま貼る。手で書かない: 手で丸めた値（秒が `:00`）は実際の値と並べると順序が狂い、`tail -N` が誤った集合を返す。上の例がそれらしい秒を持っているのは、まさにこの理由による。

⚠️ **上の例のキーの集合は一部だけ（完全ではない）。** 書き込む各 skill が自分の動詞の完全なキー集合を持ち、それを自分自身の `SKILL.md` に書いている —— 特に `wiki-lint` は毎回の実行で自分のキーをすべて要求し、上の `LINT` 行はそのうち 3 つしか見せていない。形（`- [TIMESTAMP] VERB key=value …`）はここから写し、キーはその行を書く skill から取る。

**読み返すとき**: `log.md` は追記専用で上限が無い（活発な vault では 100 kB 超 ≒ 25k トークン）ので、決して丸ごと読まない —— 末尾を `grep '^- \[' "$OBSIDIAN_VAULT_PATH/log.md" | tail -N` で取る。素の `tail` ではなくエントリ行を grep する: ファイルには空行が含まれるので、素の `tail -N` は N 件より少ないエントリしか返さない。期間で絞るときは先頭の `YYYY-MM-DD` だけを比べる —— エントリには `Z`・`+0900`・日付のみの形が混在するので、タイムスタンプ全体の比較は当てにならない。

### `.manifest.json`
何を取り込んだかを追跡する —— ソースファイル、プロジェクトごとの同期状態、各ソースがどの wiki ページを生んだか。これが delta の仕組みの背骨になる。

manifest があることで次ができる:
- **delta の計算** —— 前回の取り込み以降に何が新しく、何が変わったか
- **追記モード** —— 全部ではなく delta だけを処理する
- **監査** —— どのソースがどの wiki ページを生んだか
- **陳腐化の検出** —— ソースは変わったのに wiki ページが更新されていない

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
      "source_commit": "9a86051",
      "original_path": "/Users/you/projects/my-project/README.md",
      "project": "my-project",
      "pages_created": ["entities/my-project-repo.md", "synthesis/claude-config-hierarchy.md"],
      "pages_updated": []
    },
    "_source_docs/2026-09-12-market-report.md": {
      "ingested_at": "2026-09-12T02:10:07Z",
      "size_bytes": 48095,
      "modified_at": "2026-09-12T02:23:41Z",
      "content_hash": "sha256:1b7c40e2a9…",
      "source_type": "document",
      "original_path": "~/Downloads/market-report.md",
      "project": "my-project",
      "pages_created": ["references/market-report.md"],
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

- **ローカルファイルのキーは `_source_docs/` のコピーの vault 相対パス**（`wiki-ingest` Step 1）。渡された元の場所は
  `original_path` に残る。同じファイルを元の場所から再度渡されたときは、キーではなく `content_hash` / `original_path` で
  突き合わせる（キーだけ見ると「新規」に見えて二重に取り込む）。
- **git に commit 済みで変更の無いファイルは `_source_docs/` へコピーせず、リポジトリのルートからの相対パス
  （下の Source keys（ソースのキー）の節で project-relative と呼ぶもの）をキーにして、`source_commit`（そのファイルを最後に
  変えた commit）と `original_path`（読み込んだ絶対パス）を持つ**（`wiki-ingest` Step 1）。`source_commit` は
  任意のキーで、これを足す前に取り込んだエントリには無い。
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
- `source_cwd` を落とすと、`wiki-query` が答えに添える `ソースコード:` 行が永久に解決しなくなる
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

**Source keys（ソースのキー）: `~` は展開する。ただし相対キーを絶対パスへ書き換えてはならない。**

manifest は生の文字列をキーにするので、2 通りの綴りの*同じファイル*は 2 回追跡される。
すると delta の照合はもう一方の形を引き損ね、そのファイルを取り込み直してしまう。
気にすべき綴りは 2 つあり、扱いは正反対になる:

- **`~` と環境変数 —— 必ず展開する**（比べる前・書く前に）。`~/.claude/x.jsonl` と
  `/Users/me/.claude/x.jsonl` は同じファイルで、どちらかに決めても何も失わない。
- **プロジェクト相対（project-relative）のキー —— そのまま保つ。** これは欠陥ではなく普通の形だ:
  `README.md` や `.claude/doc/doc_dq.md` のようなキーが取り込みのルートからの相対なのは、
  取り込んだプロジェクトがそう渡したからだ。これを絶対パスへ書き換えると、既存のエントリが
  次の delta の照合ですべて外れ、vault 全体が取り込み直される。
  （実測した vault では、manifest のエントリはすべて相対だった。）

**相対キーで記録されているかもしれないパスを引くには:** 相対キーを basename で索引し、
キーが手元のパスの*末尾部分*（suffix）になっているエントリを採る。
`concepts/foo.md` はキー `foo.md` にもキー `concepts/foo.md` にも一致するが、
`other/foo.md` には一致しない。ソースを新規と判断する前にこれを行う。

既存の manifest を、片付けのつもりで絶対形へ「正規化」してはならない。*同じ*ファイルの
両方の形が見つかったら、その 2 エントリをマージして最も新しい `ingested_at` を残す ——
やる価値のある書き換えはそれだけだ。

**由来（provenance）を記録する。** manifest のエントリを書くときは、`pages_created` と `pages_updated` に、そのソースが寄与したページの vault 相対パスを入れる。これがあるから、（ソースが変わったときの）再取り込みが当て推量でなく、見直すべきページを見つけられる。

## ページ雛形（Page Template）

新しい wiki ページを作るときは、この構成を使う:

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
summary: 1〜2 文・200 字以内。読み手（や他の skill）がページを開かずに中身を下見できるようにする。
provenance:
  extracted: 0.72
  inferred: 0.25
  ambiguous: 0.03
base_confidence: 0.65
lifecycle: draft               # 下限。~/.claude/doc/doc_wiki_lifecycle_rubric.md に従って昇格させる —— draft より上の rank には lifecycle_evidence + evidence_at も要る
lifecycle_changed: 2024-03-15
tier: supporting
created: 2024-03-15T10:30:42Z
updated: 2024-03-15T10:30:42Z
---

# Page Title

このページが何を扱うかを 1 段落で要約する。

## Key Ideas

- ソースの中心となる主張を、そのまま言い換えたもの。 ^[extracted]
- ソースが含意しているが明言はしていない一般化。 ^[inferred]
- 2 つのソースで食い違う数字。 ^[ambiguous]

関連するページとは [[wikilinks]] でつなぐ。

## Open Questions

未解決のことや、もっとソースが要ること。

## Sources

- [[references/attention-is-all-you-need]] — 原論文
```

**`## Key Ideas` / `## Open Questions` はこの雛形（＝新規ページ）の中だけの見出しで、既存ページへの挿入位置として
参照してはならない**（実 vault にはほぼ存在しない見出し）。既存ページへ 1 行足すときは、**その主張が属する
箇所の直後**に置き（見つからなければ本文末尾）、特定の見出しの存在を前提にしないこと。

**`created` / `updated`** は `log.md` のエントリと同じく `date -u +%Y-%m-%dT%H:%M:%SZ` の出力 —— 実行して貼り、手で書かない。`updated` は編集のたびに設定する: これが無いページは陳腐化の検出から丸ごと外れ、陳腐化として報告されることが決してなくなる。

## 予約システムタグ（Reserved System Tags）

タグの規約（**1 ページ最大 5 タグ**・**lowercase / hyphen 区切り**・既存タグの再利用を優先）は
**この doc が正典**。新しいタグを付けるときは `index.md` の既存タグを見て揃える。

⚠️ **書き込み時に走る機械検査は無い。** 上限・形式の検出は `wiki-lint` の Check 8a
（タグ過多と形式の崩れたタグ）が**監査時に報告するだけ**で、書く瞬間には誰も止めてくれない。
検査されている前提で書かないこと（実 vault には検査導入前の超過が残っている）。

以下の `visibility/` は上の 5 タグ枠とは別枠の予約グループで、alias 正規化の対象にしない。

`visibility/` は特別な規則を持つ予約タググループ。これらのタグは領域や種別のタグでは**なく**、タグ語彙とは別に管理する:

| タグ | 用途 |
|---|---|
| `visibility/public` | 明示的に公開 —— すべてのモードで表示する（タグ無しと同じ） |
| `visibility/internal` | チーム内限定 —— フィルタモードの query/export では除外する |
| `visibility/pii` | 機微なデータ —— フィルタモードの query/export では除外する |

**`visibility/` タグの規則:**
- 5 タグの上限には数え**ない**
- 1 ページに付けられる `visibility/` タグは 1 つだけ
- 内容が明らかに公開してよいものなら丸ごと省く —— タグは要らない
- 内容が技術的だというだけで `visibility/internal` を付けない。本当にチーム内に限るべき知識にだけ使う
- タグを監査するときは `visibility/` の使用を別に報告する —— 未知のタグや非正規のタグとして指摘しない

## provenance マーカー（Provenance Markers）

wiki ページのすべての主張は、3 つの provenance 状態のいずれかを持つ。読み手（と今後の取り込み）が、ソースにある信号と、統合して足したものとを見分けられるよう、行内に印を付ける。

| 状態 | マーカー | 意味 |
|---|---|---|
| **Extracted** | 接尾辞 `^[extracted]` | ソースが実際に言っていることの言い換え。 |
| **Inferred** | 接尾辞 `^[inferred]` | LLM が統合して導いた主張 —— ソースが直接は述べていないつながり・一般化・含意。 |
| **Ambiguous** | 接尾辞 `^[ambiguous]` | ソース同士が食い違う、またはソースが不明瞭。 |

例:

```markdown
- Transformer は RNN と違い、位置をまたいで並列に処理する。 ^[extracted]
- だから現代のハードウェアでよりよくスケールする。 ^[inferred]
- GPT-4 はおよそ 13T トークンで学習された。 ^[ambiguous]
```

（`^[...]` は Obsidian できれいに描画され、`[[wikilinks]]` と決して衝突せず、1 つの箇条を 1 つの箇条のまま保つ。）

**三種とも明示的に打つ。分母がそれで確定する。** 無印を既定にすると `provenance` の分母が散文の
定義になり、数える実装ごとに比率がずれる。三種を打てば分母は「マーカーの総数」になる。

**主張でない行は打たない。** 見出し・表・コードフェンス・導入文・リンク集は無印のまま残し、分母にも
入れない。`provenance` を計算する側は 3 つのマーカーの出現数だけを数える。

**数え方は暗算しない。** 書き手はページを書いた後にこの 1 行を走らせ、出た数を合計で割って写す
（コードフェンスと inline code の中は例なので除く。wiki-lint の検査も同じ規則で数える）:

```bash
awk '/^[[:space:]]*(```|~~~)/{f=!f;next} !f' page.md | sed 's/`[^`]*`//g' \
  | grep -o '\^\[\(extracted\|inferred\|ambiguous\)\]' | sort | uniq -c
```

**frontmatter での要約:** 任意で、内訳をページ単位で表に出す。ユーザーが推測の多いページを、読まずに見渡して探せるようにするため:

```yaml
provenance:
  extracted: 0.72   # マーカーを付けた単位のうち ^[extracted] を持つものの割合（散文全体に対する割合ではない）
  inferred: 0.25
  ambiguous: 0.03
```

取り込みの skill が、作成・更新時に上の数え方からこれを書く。`wiki-lint` はスクリプトで再計算してドリフトを指摘する。このブロックは任意 —— ブロックもマーカーも無いページは、慣例として全部 extracted として扱う。

## 型付きの関係（Typed Relationships）

ページ本文の素の `[[wikilinks]]` は意味の重みを持たない —— 「関連がある」ことは示すが、*どう*関連するかは示さない。任意の `relationships:` frontmatter ブロックは、知識グラフに型と向きのある辺を足す。

### `relationships:` ブロック

```yaml
relationships:
  - target: "[[Transformer Architecture]]"
    type: extends
  - target: "[[LSTM]]"
    type: contradicts
  - target: "[[Attention Mechanism]]"
    type: implements
```

各エントリは必須のフィールドを 2 つ持つ:
- `target` —— 関係する先のページへの wikilink。**`OBSIDIAN_LINK_FORMAT` にかかわらず常に wikilink 記法（`[[path/to/page]]`）** —— その設定が決めるのは本文だけ。frontmatter を wikilink のままにしておくことで、マルチホップの探索が frontmatter への 1 回の grep から辺を解決できる。
- `type` —— 下の許される意味の型のいずれか

### 許される関係の型

この enum は **10 の概念・16 の綴り**を持つ: 対称な型が 2 つ、向きのある概念が 6 つ（それぞれ順方向と逆方向の綴りを持つ）、順方向だけの型が 2 つ。

**対称（向きなし）:**

| 型 | 意味 | 例 |
|---|---|---|
| `related_to` | 受け皿: 関係はあるが、より強い型が当てはまらない | 概念 A は概念 B に関係する |
| `contradicts` | このページの主張が対象と衝突する、または対象に反論する | 証拠 A は証拠 B と矛盾する |

**向きあり（順方向と逆方向の綴りがどちらも公式）:**

| 順方向（このページ → 対象） | 逆方向 | 順方向の意味 | 例 |
|---|---|---|---|
| `uses` | `used_by` | このページが対象に依存する・頼る | RAG は Vector Databases を使う |
| `extends` | `extended_by` | このページが対象の上に築かれている | GPT は Transformer Architecture を拡張する |
| `implements` | `implemented_by` | このページが対象の概念を具体的に実現したもの | BERT は Masked Language Modelling を実装する |
| `elaborates` | `elaborated_by` | このページが対象の詳細版 —— 主題は同じで粒度が細かい | Implementation Notes は Design Overview を詳述する |
| `constrains` | `constrained_by` | このページが対象の設計を制約する | Rate Limits は Retry Strategy を制約する |
| `part_of` | `has_part` | このページが対象（全体）の構成要素 | Attention Mechanism は Transformer Architecture の一部 |

逆方向の綴りは、同じ辺を反対側から読んだもの: `used_by` は対象がこのページに依存することを意味する。

**順方向のみ（逆方向の綴りなし）:**

| 型 | 意味 | 例 |
|---|---|---|
| `derived_from` | このページが対象に基づく、または対象を翻案したもの | Fine-tuning は Transfer Learning から派生した |
| `replaces` | このページが対象を置き換える、または廃止する | GPT-4 は GPT-3 を置き換える |

`derived_from` に逆方向の綴りが無いのは、由来は派生した側のページで宣言するのが自然だから。`replaces` の逆は意図して型にしていない —— 規則（Rules）を参照。

この enum 以前の別名の綴り（`relates_to`・`supersedes`・`depends_on` …）は機械的に正規化する。その対応表はここではなく `wiki-lint` の skill 本文にある。

### 文脈から型を推論する

wikilink を足して型を付けたいときは、言及を含む文を見る（`## Related` のエントリなら、ページのタイトルと共有タグの文脈を見る）:

| 文の型 | 推論する型 |
|---|---|
| 「X は Y を使う / に頼る / に依存する / を必要とする」 | `uses` |
| 「X は Y を拡張する / の上に築く」 | `extends` |
| 「X は Y を実装する / の実装である」 | `implements` |
| 「X は Y を詳述する / 掘り下げる」—— X が概要 Y と同じ主題をより細かい粒度で扱う | `elaborates` |
| 「X は Y の設計を制約する / 制限する / に限界を課す」 | `constrains` |
| 「X は Y の一部である / 構成要素である」 | `part_of` |
| 「X は Y と矛盾する / 対立する / に反論する / と食い違う」 | `contradicts` |
| 「X は Y から派生した / に基づく / を翻案した」 | `derived_from` |
| 「X は Y を置き換える / に取って代わる / を廃止する」 | `replaces` |
| 「X は Y に使われる」「X は Y に実装される」—— 文が対象の側から読まれている | 対応する逆方向の綴り（`used_by`・`extended_by`・`implemented_by`・`elaborated_by`・`constrained_by`・`has_part`） |
| 「X は Y を一般化する」—— X がより広い概念で、Y はその上に築かれる個別の事例 | `extended_by`（受動の「X は Y によって一般化される」は逆向き: `extends`） |
| 共有タグやカテゴリ横断の推論で、向きの手がかりが無い | `related_to` |

周りの文脈が曖昧なとき、または本文での言及が無く共有タグの一致から来たリンクなら、既定は `related_to`。

**ブロックの書き方:** `relationships:` が既にあれば、既存の target と重複させずに新しいエントリを追記する。無ければ `aliases:` の後（`aliases:` が無いなら `tags:` の後）に足す。足すのは、今回の作業で足したリンクのエントリだけ —— 既にある型付きのエントリを決して書き換えない。

### 規則（Rules）

- **任意のフィールド** —— 型付きの関係が分からないならブロックごと省く。型の無い wikilink はそのまま有効で、`related_to` として数える。
- **重複させない** —— `[[foo]]` が既に行内の wikilink として出ているなら、`relationships:` のエントリはそれに型を足すだけで、2 本目のリンクではない。
- **向きが重要** —— エントリを宣言するページが*起点*（source）で、`target` が行き先。このページの視点からの関係だけを宣言する。
- **作り出さない** —— 元の資料が関係の向きと型を明らかにしているときだけ型付きのエントリを足す。迷ったら `related_to` を使うか、省く。
- **1 つの関係に辺は 1 本** —— 逆方向の綴りがあるのは、たまたま編集しているどちらのページからでも辺を宣言できるようにするためで、2 回宣言するためではない。もう一方のページに鏡像のエントリを決して書き足さない。この規則より前からある鏡像の対はそのまま残す —— 冗長でも害は無い。保守のついでに片側を消さない。
- **この表が唯一の正典** —— 型の一覧を skill 本文へ決して写さない。2 つ目の写しができた瞬間に enum はドリフトする（Lifecycle の節が rank の一覧に課しているのと同じ規則）。skill は代わりにこの節を指す。
- **この enum の外の型を書かせる skill があってはならない** —— enum を変えるのはスキーマの決定で、ここで行い、skill では決して行わない。
- **`replaces` の逆は型ではない —— 意図的に** —— 置き換えられたページの正規の印は、`lifecycle: archived` とトップレベルの `superseded_by:` フィールド（「confidence と lifecycle（Confidence and Lifecycle）」を参照）で、これは `relationships:` の外にある。`replaced_by` や `type: superseded_by` を決して書かない。

`wiki-query` がこのブロックを読む: 回答に型を示し、「X は Y とどうつながるか」というマルチホップの経路の質問では型付きの辺のグラフをたどる（`relationships:` の隣接関係に対する深さ上限付きの BFS。frontmatter だけを読む）。

## confidence と lifecycle（Confidence and Lifecycle）

すべてのページは、互いに独立した信頼の信号を 2 つと、任意の置き換えリンクを持つ。

### 必須フィールド

```yaml
base_confidence: 0.65             # [0.0, 1.0] —— 時間に依存しない品質の見積もり。1 回保存し、内容が変わったら再計算する。
lifecycle: draft                  # 証拠のレベル —— 値と選び方: ~/.claude/doc/doc_wiki_lifecycle_rubric.md
lifecycle_evidence: "§3 の追試表"  # 証拠がどこにあるか。`draft` より上のすべての rank で必須
evidence_at: 2026-08-06           # 証拠を得た ISO 形式の日付。`draft` より上のすべての rank で必須
lifecycle_changed: 2026-08-12     # rank が最後に変わった ISO 形式の日付
# lifecycle_reason: "..."         # 任意の自由文 —— 状態が変わった理由。wiki-query が表に出す
# superseded_by: "[[new-page]]"   # wikilink。lifecycle=archived のときだけ
```

`lifecycle_reason` と `superseded_by` は任意。決して作り出さない。

`lifecycle_evidence` と `evidence_at` は **`lifecycle` が `draft` より上のときは常に必須** —— rank はある行為がなされたことを主張するもので、この 2 つのフィールドがその行為を固定する場所になる。これを埋められないなら昇格させる根拠が無い: ページを `draft` のままにする。

### Lifecycle — 正典は 1 ファイルだけ

`lifecycle` が記録するのは**このページの主張を確かめるために何をしたか** —— 自己評価の信頼度ではなく、行為である。
値の一覧・rank の序列・序列外の値・判定表・昇格規則は、次の 1 ファイルにしか無い:

> **`~/.claude/doc/doc_wiki_lifecycle_rubric.md`** — `lifecycle` を付ける / 変える前に必ず読む。

**この doc にも skill 本文にも値の一覧を書き写さないこと。** 2 つ目の写しができた瞬間に enum が漂流し、
新しいページが隣のページを真似て誤値を増やす。

`stale` は `lifecycle` の値ではなく、`evidence_at`（無ければ `updated`）に対する計算上のオーバーレイ。
rank が変わったときは `lifecycle_changed` を更新する。更新時は既存の rank を維持し、**新しい証拠が来たときだけ**
昇格して、その証拠を `lifecycle_evidence` / `evidence_at` に書く。隣のページに合わせて rank を選ばない。

### confidence の式（Confidence formula）

```
base_confidence = source_count_score * 0.5 + source_quality_score * 0.5

source_count_score   = min(distinct_source_ids / 3, 1.0)
source_quality_score = avg(quality score per distinct source_id)
```

**出典の品質スコア（Source-quality scores）**（最も高く当てはまるバケットを使う）:

| バケット | スコア | 例 |
|---|---|---|
| `paper` | 1.0 | arXiv、学会の論文集 |
| `official` | 0.9 | `*.gov`、ベンダーの公式 doc |
| `documentation` | 0.85 | よく保守された第三者の doc |
| `book` | 0.8 | 書籍、技術リファレンス |
| `repository` | 0.75 | GitHub の README、コードベース |
| `blog` | 0.55 | 個人ブログ |
| `session_transcript` | 0.5 | 会話履歴 |
| `forum` | 0.4 | Stack Overflow、HN、Reddit |
| `unknown` | 0.4 | 受け皿 |
| `llm_generated` | 0.3 | LLM 自身の振り返り |

**`source_id`** は出典ごとの安定した識別子 —— 同じブログのコピー 3 つを、別々の出典 3 つとして数えるのを防ぐ:

| 出典の種類 | source_id の規則 |
|---|---|
| 学術論文 | DOI > arXiv ID > `<author>-<year>-<slug>` |
| GitHub リポジトリ | `github.com/<owner>/<repo>` |
| ドキュメントサイト | `<canonical-host>/<product>` |
| ブログ記事 | `<host>/<author>` |
| セッションの書き起こし | `<agent>/<session-id>` |
| その他 | `<canonical-url>` |

**`sources:` の行をバケットへ当てる既定**（wiki-lint のスクリプトもこの規則で数える。外れる出典は
lint に `--bucket <source_id>=<bucket>` で上書きさせ、表そのものは変えない）:

- **リポジトリを読んだ出典は 1 リポジトリ ＝ 1 出典・`repository`**。`projects/<name>`・その
  リポジトリ内の相対パス（`lib/x.sh`、`tools/dq (write.go)` のような注記付きも）・`~/source/note/<repo>`
  は同じリポジトリなら 1 件に畳む。相対パスの持ち主は同じ `sources:` の `projects/<name>`、無ければ vault 名
- リポジトリの外の手元パス（`~/.gitconfig`・`~/.local/...`）はまとめて 1 出典・`repository`
- URL: arXiv / DOI は `paper`、`github.com/<owner>/<repo>` は `repository`（issues / discussions / pull は
  `forum`）、`*.gov` は `official`、`docs.` / `developer.` / `learn.` で始まるホストか `/docs/` 配下は
  `documentation`、Qiita / Zenn / Medium / note / dev.to / はてなブログは `blog`、Stack Overflow /
  HN / Reddit は `forum`、それ以外の URL は `unknown`
- vault 内の他ページ（`concepts/…md` 等）は `llm_generated`、会話・セッションを指す文は
  `session_transcript`、それ以外の文は `unknown`

**skill ごとの既定値（per-skill defaults）**（取り込みの skill はこれを自動で計算する）:

`lifecycle` の列は**固定値ではなく下限**。どの skill も新しいページを `draft` で始める。ページの主張の証拠が既に本文にあるなら、同じ作業の中でルーブリックに従って昇格させ、`lifecycle_evidence` / `evidence_at` を埋める。証拠の揃ったページを `draft` に留めるのは安全な既定ではなく情報を落とす既定だ —— ただし、確かめていないときはそれが正しい既定であることに変わりはない。

| skill | base_confidence | lifecycle（下限） |
|---|---|---|
| `wiki-ingest` (URL) | `0.17 + 0.5 × classify(url)` | `draft` |
| `wiki-ingest` (single doc) | 出典ごとの分類器 | `draft` |
| `wiki-ingest` (multi-doc) | `min(N/3,1)×0.5 + avg_q×0.5` | `draft` |
| `wiki-capture` | 0.42（source が会話 1 本のときの式の出力。source が増えたら式で再計算する） | `draft` |
| `claude-history-ingest` | 0.42（同上） | `draft` |
| `wiki-update` | 0.59（source が `documentation` 1 本のときの式の出力。同様に再計算する） | `draft` |

## 重要度の tier（Importance Tiering）

`tier:` フィールドは、取り込みのたびにどのページを更新するかと、読み取りでの優先度を決める。wiki が育つと、取り込みのたびに全ページを読み直すのはトークンの無駄になる —— tier があることで、取り込みと検索の skill は最も効くところへ労力を集中できる。

### 3 つの tier

| tier | 意味 | 取り込み時の挙動 | 検索での優先度 |
|---|---|---|---|
| `core` | 要（かなめ）になるページ —— 他の多くのページが依存している（被リンク数が多い、または橋渡しの位置にある）。常に更新する価値がある。 | ソースがわずかでも関係するなら常に更新する | index の読み取りと全文読みの段で最初に出す |
| `supporting` *(既定)* | 接続が中程度の標準的な wiki ページ | ソースにこのページへの明確な新しい主張があるとき更新する | 標準の優先度 |
| `peripheral` | 接続の少ないページ —— めったにリンクされず、範囲が狭い | ソースが*主として*この話題を扱うのでない限り飛ばす | 最後の手段。コンテキストの予算に収めるために削るときは飛ばす |

### 割り当て規則（Assignment rules）

これがこのバンドルで**唯一**の閾値定義。他の場所に別の数字を書かないこと（別ファイルに別の値が併存すると
読む側が割れる）。

- **新しいページ:** 既定は `tier: supporting`
- **`core` へ昇格:** ページの被リンクの wikilink が ≥5 本たまったとき、またはクラスタ間の橋渡しの位置にあるとき
- **`peripheral` へ降格:** ページの**被リンクが ≤1 本**で、90 日以上更新されていないとき
- **人間による上書きが常に勝つ** —— `tier:` を手で書き換えれば、ページをどの段にも固定できる
- `tier:` の無い既存ページは `supporting` として扱う（後方互換 —— 移行は要らない）

### 事実: 昇格を書く主体は現状いない（降格は wiki-lint が書く）

**昇格**（`core` への引き上げ）を書く skill は無い。**降格**（`peripheral`）だけは
`wiki-lint --consolidate` が上の `≤1` / 90 日を条件に、dry-run と明示確認を経て書く
（`core` は手動設定とみなして自動降格しない）。**この閾値を持つ書き手は 1 つだけ。増やさないこと。**
新規ページの `supporting` 既定は、ページを書く各 skill の雛形（wiki-ingest・URL 取り込み・wiki-update・wiki-capture・claude-history-ingest）が書く。
既存の `tier:` 値は規則の外で付与されたものも混ざるが、読む側（`wiki-ingest` の更新判定・
`wiki-query` の順序付け）は**そのまま信じて使う**。

## 読み取りプリミティブ（Retrieval Primitives）

vault を読むことが、読む側のどの skill でもコストの大半を占める。質問に答えられる最も安いプリミティブを使い、**安いほうで足りないときだけ一段上げる**。vault の内容が要る skill は、いきなりページ全体を読みにいかず、この表に従う。

| 要るもの | プリミティブ | 相対コスト |
|---|---|---|
| ページがあるか？ タイトル・カテゴリ・タグは？ | `index.md` をその語で `Grep` する。frontmatter のブロックを `Grep` する（ファイル先頭の `^---` ブロックを狙うパターンで範囲を絞る）。`index.md` を丸ごと読むのは vault の全体像についての質問のときだけ | **最も安い** |
| ページの 1〜2 文の下見 | frontmatter の `summary:` フィールドを読む | **安い** |
| ページ内の特定の主張や節 | `Grep -A <n> -B <n> "<term>" <file>` —— 一致した行と前後の文脈だけを返す | **中** |
| ページ全体の内容 | `Read <file>` | **高い** —— 最後の手段 |
| ページをまたぐ関係 | vault 全体に `Grep "\[\[.*?\]\]"` をかけるか、既知のページから wikilink をたどる | 場合による |

**規則:** 安いプリミティブで質問に答えられないときだけ一段上げる。`summary:` フィールドだけで答えられるならページ本文を読まない。`-A 10 -B 2` で grep した節から主張が取れるなら、ページ全体を読まない。15 行を読むために 500 行のページを開けば、485 行分のトークンが無駄になる。

**なぜ大事か:** 20 ページの vault なら vault 全体の走査でも済んでしまう。200 ページの vault ではそうはいかない。上のプリミティブこそが、この skill の仕組みがデータベース無しで大きな vault へスケールする方法だ。

## リンク形式（Link Format）

wiki ページをつなぐ内部リンクはすべて、解決した設定の `OBSIDIAN_LINK_FORMAT` で決まる（既定: `wikilink`）。

| 設定 | 記法 | 例 |
|---|---|---|
| `wikilink` *(既定)* | `[[path/to/page]]` または `[[path/to/page\|display text]]` | `[[concepts/foo\|foo]]` |
| `markdown` | `[display text](relative/path.md)` | `[foo](../concepts/foo.md)` |

### markdown 形式のリンクの生成

`OBSIDIAN_LINK_FORMAT=markdown` のとき:
1. **現在のファイルのディレクトリ**から**対象の `.md` ファイル**へのパスを、必要に応じて `..` で上がりながら計算する。
2. 表示テキストにはページのタイトルか自然な語句を使う。
3. 拡張子 `.md` を必ず付ける。

| 現在のファイル | 対象 | 相対リンク |
|---|---|---|
| `index.md` | `concepts/foo.md` | `[foo](concepts/foo.md)` |
| `concepts/foo.md` | `entities/bar.md` | `[bar](../entities/bar.md)` |
| `projects/my-project/my-project.md` | `concepts/foo.md` | `[foo](../../concepts/foo.md)` |
| `projects/my-project/concepts/arch.md` | `entities/bar.md` | `[bar](../../../entities/bar.md)` |

wikilink の `[[path\|display text]]` 形は、Markdown モードでは `[display text](relative/path.md)` に対応する。

**範囲:** この設定が効くのは新しく書く・更新するリンクだけ。vault の既存の内容は決して移行しない —— このバンドルに古いリンクを一括変換する skill は無いので、形式を切り替えても以前のリンクはそのまま残る。

書き込むどの skill も、リンクを作る前に解決した設定から `OBSIDIAN_LINK_FORMAT` を読み、正しい形式を当てる。frontmatter の `relationships:` の target だけは例外で、常に wikilink 記法を使う（「型付きの関係（Typed Relationships）」を参照）。
