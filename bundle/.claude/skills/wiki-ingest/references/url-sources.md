# URL ソースの取り込み

ソースがローカルファイルではなく **Web URL** のときの、`wiki-ingest` skill の参照資料。
`/ingest-url <url>`、"add this URL"、"ingest this link"、"save this page"、または "add this" / "save this to my wiki" を
添えて貼られた URL で起動する。

ページの置き場は、現在のプロジェクトを検出できるかで決まる —— できればそのプロジェクトのフォルダへ
直接入れる。できなければ `misc/` へ入れ、後でつながりの affinity に基づいて昇格させる。
設定の解決とコンテンツの信頼境界は skill 自身の
`SKILL.md` と同じ —— そちらに従う。このファイルは URL 固有の仕組みだけを扱う。

<!-- INDEX -->
**順に行う手順** —— すべて実行する。U5b と U6 はモードによってどちらか一方だけ。この表が
このファイルの見出し索引である（300 行を超えるので、頭から通して読まず、必要な手順へ
飛ぶ）。

| Step | 何をするか |
|---|---|
| U0 | 現在のプロジェクトを検出する（git remote → パッケージのメタデータ → ディレクトリ名 → なし） |
| U0.5 | きれいな抽出のための事前確認（使えるなら `defuddle`） |
| U1 | URL を取得する（失敗したらスタブページを作り、U7 へ飛ぶ） |
| U2 | manifest / vault に既にある重複を確かめる |
| U3 | 置き場を選び、スラッグを作る（U3a 既存のプロジェクト / U3b 新しいプロジェクト / U3c `misc/`） |
| U4 | 知識を抽出し、provenance を追う |
| U5 | ページを書く（frontmatter はモードごとに違う。`base_confidence` は URL のホストから） |
| U5b | affinity のスコア付け —— **misc モードのみ** |
| U6 | プロジェクトの概要を更新する —— その `## References` 節に新しいページを足す（無ければ作る）—— **プロジェクトモードのみ** |
| U7 | `.manifest.json`・`index.md`・`log.md`・`hot.md` を更新する |
| — | `## Quality Checklist (URL sources)` —— 完了を報告する前に実行する |

## Step U0: 現在のプロジェクトを検出する

何かを取得する前に、ユーザーが特定のプロジェクトの中で作業しているかを判定する。

**検出の順序（最初に当たったものを採る）:**

1. **git remote の名前** —— カレントディレクトリで `git remote get-url origin 2>/dev/null` を実行する。ホスト・org・`.git` の接尾辞を剥がしてリポジトリ名を得る。例: `https://github.com/acme/my-app.git` → `my-app`。
2. **パッケージのメタデータ** —— git remote が無ければ、`package.json`（`name` フィールド）、`pyproject.toml`（`[project] name`）、`Cargo.toml`（`[package] name`）、`go.mod`（module パスの最後の要素）をこの順に確かめる。
3. **ディレクトリ名** —— 上のどれも効かなければ、カレントディレクトリの basename を使う。
4. **プロジェクトの文脈が無い** —— カレントディレクトリが obsidian-wiki リポジトリそのものであるとき、または検出した名前が wiki の vault のディレクトリと一致するときは、「プロジェクトの文脈が無い」として扱い、`misc/` へ落ちる。

**プロジェクト名を正規化する:** 小文字にし、空白とアンダースコアを `-` に置き換え、先頭のドットを剥がす。

候補の名前が得られたら、`$OBSIDIAN_VAULT_PATH/projects/<project-name>/` があるかを確かめる:

| 状況 | 行うこと |
|---|---|
| プロジェクトを検出 ＋ フォルダが**ある** | 既存のプロジェクトにページを足す（Step U3a） |
| プロジェクトを検出 ＋ フォルダが**無い** | プロジェクトの構造を作ってからページを足す（Step U3b） |
| プロジェクトの文脈が無い | `misc/` へ落ちる（Step U3c） |

## Step U0.5: きれいな抽出のための事前確認

取得する前に、`defuddle` CLI が使えるかを確かめる:

```bash
which defuddle
```

- **使えるなら:** （Bash で）`defuddle <url>` を使い、ページから余計なものを剥がしたきれいな markdown 版を取る。広告・ナビバー・Cookie バナー・関連コンテンツのサイドバーが取り除かれ、典型的な記事でトークン消費が約 40〜60% 減る。Step U4 の中身の元には、素の WebFetch の結果ではなく `defuddle` の出力を使う。
- **使えないなら:** 通常どおり `WebFetch` へ落ちる。することは無い。

## Step U1: URL を取得する

渡された URL の中身を `WebFetch` で取得する（Step U0.5 で `defuddle` を使ったなら飛ばす）。

- ページがペイウォールの向こうにある・JS で描画される（本文が空）・エラーを返すときは、タイトル（URL から推測）・URL・frontmatter の `stub: true` を持つ**スタブページ**を作る。本文には `> [Stub] Page could not be fetched — enrich manually.` を足す。そのうえで Step U7 へ飛ぶ。
- ページを取得できたら: Step U2 へ進む。

## Step U2: 重複を確かめる

新しいページを作る前に、この URL が既に取り込まれていないかを確かめる:
- `.manifest.json` を grep し、いずれかの `source_url` フィールドにこの URL の文字列があるかを見る
- プロジェクトモードなら: `$OBSIDIAN_VAULT_PATH/projects/<project-name>/` をこの URL の文字列で grep する
- misc モードなら: `$OBSIDIAN_VAULT_PATH/misc/` をこの URL の文字列で grep する

見つかったら: どのページがそれを扱っているかを報告し、ユーザーが新しい中身を望むなら取り込み直す（更新する）ことを申し出る。重複したページは作らない。

## Step U3: 置き場を決めてスラッグを作る

URL からスラッグを作る:
1. `https://`・`http://`・末尾のスラッシュを剥がす
2. ホスト名＋意味のあるパスの最初の 2 要素を取る
3. すべて小文字にする。`/`・`.`・`?`・`=`・`&`・`#`・空白を `-` に置き換える
4. 連続する `-` を 1 つにまとめ、先頭・末尾の `-` を取り除く
5. 50 文字で切る
6. 先頭に `web-` を付ける

例:
- `https://martinfowler.com/articles/microservices.html` → `web-martinfowler-com-articles-microservices`
- `https://arxiv.org/abs/1706.03762` → `web-arxiv-org-abs-1706-03762`

### Step U3a: 既存のプロジェクト

置き場: `$OBSIDIAN_VAULT_PATH/projects/<project-name>/references/<slug>.md`

プロジェクトのフォルダの中に `references/` がまだ無ければ作る。これは統合や概念のページではなく参照のページである —— プロジェクトに関係する外部のソースを記録する。

### Step U3b: 新しいプロジェクト

まず、プロジェクトの骨組みを作る:

```
projects/<project-name>/
├── <project-name>.md          ← プロジェクトの概要（スタブ —— 分かっていることを書き込む）
├── concepts/
├── references/
└── skills/
```

プロジェクトの概要のスタブ（`<project-name>.md`）の frontmatter:
```yaml
---
title: "<Project Name>"
category: project
tags: []
sources: []
created: "<ISO-8601 timestamp>"
updated: "<ISO-8601 timestamp>"
summary: "Project wiki for <project-name>. Created automatically via URL ingest."
---
```

そのうえで、ページを `projects/<project-name>/references/<slug>.md` に足す。

ユーザーへ報告する: 「vault に新しいプロジェクト `<project-name>` を作成しました。」

### Step U3c: プロジェクトの文脈が無い（misc へ落ちる）

置き場: `$OBSIDIAN_VAULT_PATH/misc/<slug>.md`

`misc/` ディレクトリがまだ無ければ作る。

## Step U4: 知識を抽出する

取得した中身から、次を見極める:
- **タイトル** —— ページの実際のタイトル（`<title>` か `# heading` から）
- **中核の概念** —— このページは根本的に何についてのものか？
- **主要な主張** —— 最も重要な主張・知見を 3〜7 個
- 言及されている**エンティティ** —— 人物・ツール・ライブラリ・組織
- **関連する話題** —— どの分野・考えとつながるか？
- **未解決の問い** —— ページが提起しているが答えていないことは何か？

主張ごとに provenance を追う:
- *Extracted* —— ページがはっきり述べている → `^[extracted]`
- *Inferred* —— 一般化している、または外部の文脈とつないでいる → `^[inferred]`
- *Ambiguous* —— ページが曖昧、または内部で矛盾している → `^[ambiguous]`

## Step U5: ページを書く

frontmatter はモードによって少し違う:

**プロジェクトモード**（`projects/<project-name>/references/<slug>.md`）:
```yaml
---
title: "<page title>"
category: references
project: "<project-name>"
tags: [<ドメインのタグ 2〜4 個 —— 新しく作らず、index.md に既にあるタグを使い回す>]
sources:
  - "<URL>"
source_url: "<URL>"
created: "<ISO-8601 timestamp>"
updated: "<ISO-8601 timestamp>"
summary: "<このページが何についてのものかを 1〜2 文で。200 字以内>"
stub: false
provenance:
  extracted: 0.X
  inferred: 0.X
  ambiguous: 0.X
base_confidence: <computed — see below>
lifecycle: draft                # 下限 —— URL の取り込みが `sourced` になるのは、ソースの URL *と*
                                # 取得日の両方を記録したときだけ。そうでなければここに留まる
                                # (~/.claude/doc/doc_wiki_lifecycle_rubric.md)
lifecycle_changed: "<ISO date today>"
---
```

**misc モード**（`misc/<slug>.md`）:
```yaml
---
title: "<page title>"
category: misc
tags: [<ドメインのタグ 2〜4 個 —— 新しく作らず、index.md に既にあるタグを使い回す>]
sources:
  - "<URL>"
source_url: "<URL>"
created: "<ISO-8601 timestamp>"
updated: "<ISO-8601 timestamp>"
summary: "<このページが何についてのものかを 1〜2 文で。200 字以内>"
affinity: {}
promotion_status: misc
stub: false
provenance:
  extracted: 0.X
  inferred: 0.X
  ambiguous: 0.X
base_confidence: <computed — see below>
lifecycle: draft                # 上のプロジェクトモードの frontmatter と同じ規則
lifecycle_changed: "<ISO date today>"
---
```

**URL ソースの `base_confidence` を計算する:**

ホストから URL の品質のバケットを分類する:
- `arxiv.org`、`doi.org`、学会のサイト → `paper`（1.0）
- `*.gov`、ベンダーの公式 doc（例: `docs.python.org`、`developer.mozilla.org`）→ `official`（0.9）
- よく保守されたサードパーティの doc（例: `docs.docker.com`）→ `documentation`（0.85）
- GitHub の README（`github.com`）→ `repository`（0.75）
- 個人ブログ・Medium・Substack・dev.to → `blog`（0.55）
- Stack Overflow・Hacker News・Reddit → `forum`（0.4）
- それ以外 → `unknown`（0.4）

出典が 1 つのとき: `base_confidence = round(0.17 + 0.5 × quality_score, 2)`

例: `paper` → 0.67、`official` → 0.62、`documentation` → 0.60、`repository` → 0.55、`blog` → 0.45、`forum/unknown` → 0.37。

そのうえで本文を書く（両モードで同じ）:

- `## Overview` —— ページが扱う内容の 2〜4 文の要約
- `## Key Points` —— 主な主張・知見の箇条書き。provenance マーカーを付ける
- `## Concepts` —— 関連する概念ページへの wikilink（`[[concepts/...]]`）。まだ無い重要な概念には最小限のスタブを作る
- `## Entities` —— 言及された人物・ツール・組織のエンティティページへの wikilink（`[[entities/...]]`）
- `## Open Questions` —— ソースが提起する問い（無ければ節ごと省く）
- `## Related` —— これとつながる既存の wiki ページへの wikilink。プロジェクトモードでは、`[[projects/<project-name>/<project-name>]]` へ戻るリンクを必ず含める

中身がそれに値するなら `visibility/internal` か `visibility/pii` のタグを付ける。迷ったら付けない。

**wikilink の最低数:** どのページも、既存のページへ少なくとも 2 本リンクしなければならない。書く前に `index.md` を検索する。関連するページが 2 つ未満しか無ければ、言及された概念のうち最も重要なものについて最小限のスタブページを作る。

## Step U5b: affinity のスコア付け（misc モードのみ）

プロジェクトモードなら、この手順を丸ごと飛ばす。

ページを書いたら、置いた `[[wikilink]]` をすべて走査する。リンク先のページごとに:
1. `projects/<project-name>/` の下にあるかを確かめる
2. `project:` の frontmatter フィールドを持つかを確かめる
3. どちらかが真なら、そのプロジェクトの affinity スコアを 1 増やす

加えて: ページ本文を走査し、`index.md` に載っているプロジェクト名がそのまま言及されていないかを見る。リンクになっていない言及 1 つごとに、そのプロジェクトのスコアに +1 する。

結果を frontmatter の `affinity` ブロックへ書く。プロジェクトとのつながりが見つからなければ `affinity: {}` のままにする。

いずれかのプロジェクトのスコアが 3 以上なら、それを示す:

> ⚡ 強い affinity を検出しました: このページは `<project-name>` と **3 つ以上のつながり**を持っています。このページを
> `projects/<project-name>/references/` へ昇格させることを検討してください —— ファイルを移し、frontmatter に `project: <project-name>` と
> `promotion_status: <project-name>` を設定し、プロジェクトの概要の `## References`
> 節に足し、`index.md` のエントリを直します。

報告はするが、自分の判断で昇格させない —— 移動は別のプロジェクトの概要を書き換えるので、
判断はユーザーに任せる。

## Step U6: プロジェクトの概要を更新する（プロジェクトモードのみ）

misc モードなら、この手順を飛ばす。

`projects/<project-name>/<project-name>.md` にあるプロジェクトの概要を読む。概要がスタブであるか、まだこの参照に触れていなければ、新しいページを `## References` 節に足す:

```markdown
## References

- [[projects/<project-name>/references/<slug>]] — <one-line summary>
```

`## References` 節が既にあれば、そこに追記する。frontmatter の `updated` タイムスタンプを更新する。

## Step U7: manifest と特殊ファイルを更新する

**`.manifest.json`** —— エントリを追加または更新する:

```json
{
  "ingested_at": "TIMESTAMP",
  "source_url": "https://...",
  "source_type": "url",
  "stub": false,
  "project": "<project-name or null>",
  "promotion_status": "<project-name or misc>",
  "pages_created": ["projects/<project-name>/references/<slug>.md"],
  "pages_updated": ["projects/<project-name>/<project-name>.md"]
}
```

`stats.total_sources_ingested` と `stats.total_pages` を更新する。

**`index.md`** —— 新しいページを適切な節の下に足す:
- プロジェクトモード: `## Projects > <project-name>` の下
- misc モード: `## Misc` の下（その節が無ければ末尾に作る）

**`log.md`** —— 追記する:

プロジェクトモード:
```
- [TIMESTAMP] INGEST_URL url="<url>" page="projects/<project-name>/references/<slug>.md" project="<project-name>" mode=project
```

misc モード:
```
- [TIMESTAMP] INGEST_URL url="<url>" page="misc/<slug>.md" affinity={} promotion_status=misc mode=misc
```

`[TIMESTAMP]` は `date -u +%Y-%m-%dT%H:%M:%SZ` の出力 —— 実行して結果をそのまま貼る。手で書かない（理由: schema doc の `log.md`）。

**`hot.md`** —— いま取り込んだものについて **Recent Activity** の下へ 1 行を `Edit` で入れる。新しい順で、直近 3 件の操作だけ。1 回の `Edit` で先頭に入れ、節が既に埋まっていれば、最も古い行を**別の** `Edit` で消す。**変更は `Edit` だけで 1 行ずつ行い、ファイルを `Write` で書き戻さない**（理由: schema doc の Special Files）。**概念そのものはここに書かない** —— それはいま書いたページに置く。`updated` タイムスタンプは別の `Edit` で更新する。

## Quality Checklist (URL sources)

- [ ] プロジェクトの検出に基づいて置き場を正しく決めた
- [ ] モード（プロジェクト対 misc）に合った正しい frontmatter でページを書いた
- [ ] frontmatter の `source_url` が取り込んだ URL と一致する
- [ ] 既存のページへの wikilink が 2 本以上ある
- [ ] `summary:` フィールドがあり、200 字以内
- [ ] provenance マーカーを付けた。`provenance:` の frontmatter ブロックがある
- [ ] プロジェクトモードでは: プロジェクトの概要を更新し、新しい参照へのリンクを足した
- [ ] misc モードでは: `affinity` と `promotion_status` のフィールドがある
- [ ] `.manifest.json`・`index.md`・`log.md` を更新した
- [ ] 取得に失敗したなら、スタブページをユーザーに報告した
- [ ] `hot.md` を `Write` ではなく `Edit` で変え、各範囲を変わった行に絞った
