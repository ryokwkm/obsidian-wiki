---
name: wiki-lint
description: Obsidian wiki の健全性を監査する（孤立ページ・壊れた wikilink・矛盾・陳腐化）。「wiki を掃除して」「何を直すべき」「ノートを監査して」「wiki のヘルスチェック」や英語の "audit my notes" / "wiki health check" と言われたときに使う。`--consolidate` で報告のみから「修復して報告」（dream cycle）へ切り替わり、dry-run とユーザーの確認を経て直す。
---

# Wiki Lint — 健全性の監査

Obsidian wiki の健全性を点検する。目的は、時間とともに wiki の価値を下げていく構造上の問題を見つけて直すことである。

**何かを走査する前に:** `~/.claude/doc/doc_wiki_schema.md` の Retrieval Primitives の表に従う。ページ全体を読むより、frontmatter に絞った grep と節を狙った読み込みを優先する。大きな vault で lint のために全ページを闇雲に読むことこそ、この仕組みが避けるために作られたものだ。

## 着手前に

1. **vault のパスを解決する** —— `$OBSIDIAN_VAULT_PATH` が既に export されていればそれを使う。無ければ CWD から `$HOME` まで遡って `OBSIDIAN_VAULT_PATH=` を含む `.env` を探し、最初に見つかったものを採る。どちらも無ければ止まり、`.claude/settings.json`（`env`）・shell rc・direnv のどれかで `OBSIDIAN_VAULT_PATH` を設定するようユーザーに伝える。決め打ちのパスへ決して落ちない —— 1 リポジトリに 1 vault。
2. ページの一覧は `index.md` を丸ごと読まず、Check 0 のスクリプトから取る（Check 6 が `index.md` をそれと突き合わせる）
3. 最近の活動の文脈として `log.md` の末尾を読む —— `grep '^- \[' "$OBSIDIAN_VAULT_PATH/log.md" | tail -30`。**`log.md` を決して丸ごと読まない**: 追記専用で上限が無い（活発な vault では 100 kB 超 ≒ 25k トークン）。素の `tail` ではなくエントリの行を grep する —— ファイルには空行が混ざるので、素の `tail -N` では N 件より少ないエントリしか返らない。

## lint の検査

以下の検査を順に走らせる。成果物は「出力形式」の節に書いた 1 本のレポートである。

### 0. Build the link graph — run this first

Check 1・2・2a・7・11・13 はどれも同じグラフを読む。スクリプトで 1 回だけ作る:

```bash
python3 ~/.claude/skills/wiki-lint/scripts/linkgraph.py "$OBSIDIAN_VAULT_PATH"
```

孤立ページ・リンク切れ・曖昧なリンクを出力する。`--quiet` なら件数だけ、
`--json` ならグラフ全体を足す。**JSON は vault をキーにしている** —— スクリプトは
`vault [vault ...]` を受け取るので、最上位は `{"<basename of the path you passed>": {…}}` で、
引数 1 つにつきキー 1 つ、ほかはすべてその中にある: `stats`、`orphans`、`broken`、
`ambiguous`、`pages`、`edges`（`[{from, to}]`）、`incoming`（ここへリンクしているページ数、
0 も含む）、`incoming_links`（リンクの素の数）、`outgoing`、`links_to_excluded`、
`unreadable`。どれを読むにも、先にその 1 段を剥がす。例:
`… --json | python3 -c 'import json,sys; g=json.load(sys.stdin).popitem()[1]; print(len(g["edges"]))'`。
`jq '.edges | length'` に手を伸ばさ**ない**: 存在しない最上位キーは
`null | length` = `0` になるので、検査はエラーを一切出さずに「何も見つからない」と報告する。
Check 7 と 11 には `--json` の形が要る。

そのうち 2 つは、指摘ではないが対処が要る:
- **`unreadable`** —— 読めなかったファイル（リンク先の無い symlink、権限）。グラフから
  抜けているので報告する。黙って存在しないものとして扱わない。
- **`links_to_excluded`** —— 走査から除外したディレクトリへのリンク。リンク先は
  存在するのでリンク切れではないが、辺でもない。触れる価値があるのは
  件数が多いときだけ —— あるディレクトリが、リンク先（wiki の一部）としても走査の除外対象としても扱われている印だ。

**数字はスクリプトから取る。手で数え直さず、指摘を grep し直して「検証」
したりもしない —— スクリプトと食い違う grep は、grep の方が間違っている。**

リンクを数えるのは grep のレシピに見えるが、そうではない: 解決の意味が*異なる* 2 つのリンク記法、
コード例の中に書かれたリンク構文そのもの、別のディレクトリにある
同名のページ。手で数えると毎回違う答えになる（実測: 同じ
指示が、ある vault では孤立ページ 5 件、別の vault では 87 件を出した）。

**代替手順。** `python3` が使えなければ `references/link-graph.md` に従い、
手作業の代替手順を使ったことをレポートに書く —— スクリプトと食い違うことが分かっている。

### 1. Orphaned Pages

スクリプトが `orphans` に挙げるページ: **入ってくるリンクが無く、解決できる出ていくリンクも
無い**。外へリンクしているページは孤立ページではない —— それが指す先のどこからでも、グラフを
逆向きに辿れば到達できる。

**報告する前に、よくある 2 つの誤検知を確かめる:**
- **空ファイル**（0 バイト）。frontmatter 欠落・summary 欠落・lifecycle の検査にも
  引っかかるので、1 つの空ファイルが 4 件の指摘として現れる。`qmd` も 0 バイトのファイルは
  インデックスしない。中身を埋めるのではなく、削除を提案する。
- **意図して wiki ページにしていないディレクトリ**（レポート、一度きりのエクスポート、参照用に
  取っておいた生のソース）。相互リンクを張るのではなく、そのディレクトリを vault ルートの
  `.wikilintignore`（1 行に 1 つの glob、`#` でコメント）に足す。`_` で始まる
  ディレクトリは既に除外されている。

**本物の孤立ページの直し方:**
- どの既存ページからそこへリンクすべきかを特定する
- そのページが既に使っている記法で、適切な節にリンクを足す

### 2. Broken Links

スクリプトが `broken` に挙げるリンク: リンク先がどのページにも解決しない。

**直し方:**
- リンク先が改名されていたら、リンクを更新する
- リンク先が存在すべきものなら、作る
- リンクが誤りなら、消すか直す

### 2a. Ambiguous Links

スクリプトが `ambiguous` に挙げるリンク: リンク先が**複数の**ページに一致するので、
どれを指したのか知る術がない。これはリンク切れより悪い —— vault の中で何もおかしく
見えず、最初の一致を黙って選ぶツールはどれも、その参照を
間違ったページに帰属させる。

**直し方:** リンクをディレクトリで修飾する（`[[project-a/build-spec]]`
のように書き、`[[build-spec]]` とは書かない）か、衝突しているページの一方を改名する。

### 3. Missing Frontmatter

すべてのページは次を持つこと: title, category, tags, sources, created, updated。

**確かめ方:**
- 全ページを丸ごと読まず、frontmatter のブロックを grep する（ファイル先頭の `^---` に範囲を絞る）
- 必須フィールドが欠けているページを指摘する

**直し方:**
- 欠けたフィールドを妥当な既定値で足す

指摘は `Missing Frontmatter` の節へ（見本の行は `references/output-format.md`）、その合計は `LINT` の log エントリの `missing_frontmatter=N` へ書く。

### 3a. Missing Summary (soft warning)

すべてのページは `summary:` frontmatter フィールドを*持つのが望ましい* —— 1〜2 文、200 字以内。安価な検索（例: `wiki-query` の index だけを読むモード）は、ページ本文を開かずに済ませるためにこれを読む。

**確かめ方:**
- vault 全体の frontmatter を `^summary:` で grep する
- それが無いページを指摘する。**ただしエラーではなく警告（soft）として** —— このフィールドより前からある古いページは問題ない。この検査は、ingest 系の skill が新しく書くときに埋めるよう促すためにある。
- summary が 200 字を超えるページも指摘する: metrics スクリプトの実行結果の `summary_over_limit` から取る（Check 7 —— 1 回だけ走らせて出力を使い回す）。文字数を手で数えない。

**直し方:**
- ページを取り込み直すか、短い summary（ページの内容を 1〜2 文で）を手で書く。

### 4. Stale Content

`updated` のタイムスタンプが、出典に比べて古いページ。

**確かめ方:**
- ページの `updated` タイムスタンプを、出典ファイルの更新時刻と比べる
- ページが最後に更新された後で出典が変更されているページを指摘する

### 5. Contradictions

ページ間で食い違う主張。

**確かめ方:**
- 関連するページを読んで主張を比べる必要がある
- タグを共有しているページや、相互参照の多いページに絞る
- "however", "in contrast", "despite" のような言い回しを探す。既に認識されて書かれている矛盾を、認識されていない矛盾と分ける手がかりになりうる

**直し方:**
- 矛盾を記す "Open Questions" 節を足す
- 両方の出典とその主張を参照する

### 6. Index Consistency

`index.md` が実際のページ一覧と一致しているかを確かめる。

**確かめ方:**
- `index.md` に載っているページを、ディスク上の実際のファイルと比べる
- 各エントリは、ページの `summary:` をそのまま写したものでなければならない（後ろに `( #tag)` の接尾辞を付けてもよい）。metrics スクリプトの実行結果が、そうなっていないエントリを `index.entry_not_verbatim` に挙げる（vault に `index.md` が無ければ `null`）—— 目で比べない。エントリが summary より長く育つことで、`index.md` は過去に 2 回膨れ上がった。
- 挙がったエントリが 3 件を超えるときは、全行ではなく件数と 3 例を報告する。
- `index.entries` は、スクリプトがページに対応づけられたエントリの数。これがページ数を大きく下回るなら、スクリプトはエントリの書式を認識できていない —— そう書く。その場合、空の `entry_not_verbatim` は「問題なし」ではなく「未検査」を意味する。

**直し方:** ページの `summary:` をエントリへ写す —— 逆向きには決してしない。summary が 200 字を超えているなら、先に summary を短くする（Check 3a）。

指摘は `Index Issues` の節へ（見本の行は `references/output-format.md`）、その合計は `LINT` の log エントリの `index_issues=N` へ書く。

### 7. Provenance Drift

ページが、内容のどれだけが inferred でどれだけが extracted かを正直に示しているかを確かめる。マーカーの規約（`^[extracted]` / `^[inferred]` / `^[ambiguous]` —— すべての主張がどれか 1 つを持つ）と、任意の `provenance:` frontmatter ブロックは `~/.claude/doc/doc_wiki_schema.md` で定義されている。

**確かめ方:** 割合は metrics スクリプトから取る —— マーカーを手で数えない（手で数えると数え手ごとに食い違う）:

```bash
python3 ~/.claude/skills/wiki-lint/scripts/frontmatter_metrics.py "$OBSIDIAN_VAULT_PATH"
```

JSON を出力する。`pages` の下の各エントリは `provenance` = `{extracted, inferred, ambiguous, n_markers, stored, drift_flag}` を持つ（ページにマーカーが無ければ `null`）。分母はマーカーの総数で、コードの中のマーカーは除く。同じ実行結果が Check 3a（`summary_over_limit`）・Check 6（`index`）・Check 8（`clusters`）・Rule 12e（`base_confidence`）にも使われるので、1 回だけ走らせる。

- 次の閾値を当てはめる:
  - **AMBIGUOUS > 15%**: "speculation-heavy"（推測が多い）として指摘する —— 主張の 7 件に 1 件が本当に不確かなだけでも、ページの出典をもっと固めるか、`synthesis/` へ移すべきだという合図だ
  - **frontmatter に `sources:` が無く INFERRED > 40%**: "unsourced synthesis"（出典の無い統合）として指摘する —— ページはつながりを作っているが、引ける出典が何も無い
  - INFERRED > 40% の**ハブページ**（incoming の上位 10 件 —— Check 0 のグラフから取り、導き直さない）: "high-traffic page with questionable provenance"（参照が多いのに provenance が怪しいページ）として指摘する —— ハブページの誤りは、そこへリンクするすべてのページへ広がる。上流（移植元）の 20% ではなく 40%: ページは主張の一部にしかマーカーを付けず、付いていない残りの大半は extracted なので、マーカー総数を分母にした割合は主張単位の割合のおよそ 2 倍になる。基準にした vault では、20% だとハブ 10 件中 9 件が指摘された。40% なら、付いていない主張を extracted として数えたときに 20% が指摘したのと同じ 2 件を指摘する
  - **ドリフト**: `drift_flag` が true —— 保存された `provenance:` ブロックが、どれかのフィールドで再計算値から 0.20 を超えてずれている
- `provenance:` frontmatter もマーカーも無いページは**飛ばす** —— 規約上、すべて extracted とみなす

**直し方:**
- ambiguous が多いもの: ソースから取り込み直す、不確かな主張を解消する、または推測の内容を `synthesis/` のページへ切り出す
- 出典の無い統合（unsourced synthesis）: frontmatter に `sources:` を足すか、そのページが synthesis であることをはっきり示す
- INFERRED > 40% のハブページ: 取り込み直しを優先する —— ここの誤りは影響範囲が最も広い
- ドリフト: `provenance:` frontmatter を再計算値に合わせて更新する

### 8. Fragmented Tag Clusters

タグを共有するページが、実際に互いにリンクしているかを確かめる。タグは話題のまとまり（クラスタ）を示す。それらのページが互いを参照していなければクラスタは断片化している —— 編み合わせるべき知識の孤島である。

**確かめ方:** Check 7 のスクリプトの実行結果から `clusters` を読む。5 ページ以上に付いているタグをすべて、`n`、`linked_pairs`（グループ内でどちらかの向きにリンクしているページの組 —— 1 組は 1 回だけ数える）、`cohesion = linked_pairs / (n × (n−1) / 2)` とともに挙げる。結束度（cohesion）が 0.15 未満のタグを指摘する。

**直し方:**
- クラスタを結束度のスコアとともに報告する。編み合わせるとはグループ内のページ間にリンクを足すことで —— それは本文への書き込みなので、慎重に行う: 各ページが既に使っている記法を使い、すべての組を相互リンクするのではなく、1 ページあたり数本のリンクを足す
- タグのグループが大きく（n > 15）、それでも断片化しているなら、より具体的なサブタグへの分割を検討する

### 8a. Over-Tagged and Malformed Tags

タグの規則は `~/.claude/doc/doc_wiki_schema.md` にある: **1 ページあたりタグは最大 5 個**、
小文字、ハイフン区切り、できるだけ既存のタグを使い回す。`visibility/` タグは
予約されたグループで、5 個に数え**ない**。

書き込み時に上限を検査するものは何も無いので、監査なしで育った vault は
未処理分（backlog）を抱えている。上限と語彙の唯一の典拠は上の doc である。

**確かめ方:**
- frontmatter を `^tags:` で grep する —— インラインの `[a, b]` 形式と、
  ブロックリスト形式（`tags:` の後に `- a` の行が続く）の**両方**を扱う。ここのページは両方を使っており、
  一方の形式しか知らない正規表現は、黙って小さい数を報告する
- `visibility/*` のエントリを除き、残りのタグが **6 個以上**のページを指摘する
- それとは別に、小文字とハイフンだけでできていないタグを指摘する —— 大文字、
  アンダースコア、空白のいずれかをタグの中に含むもの

**件数と最もひどいものだけを報告し、ページごとに 1 件ずつ報告しない。** ページ単位の
指摘が何十件も並ぶと他の節がすべてレポートから押し出されるし、未処理分は
この検査より前からある。節の中身は:
- 件数と分布の 1 行（`27 pages over 5 tags — 26 at 6, 1 at 7`）
- **タグ数の上位 5 件**を、ひどい順に 1 件 1 行で
- 形式の崩れたタグの*名前*ごとに 1 行（ページごとではない）、それを持つページ数を添えて

**件数が横ばいなのは想定どおりの状態で、指摘ではない。** 情報を持つのは
`log.md` にある前回の `over_tagged=` との差分だ: 件数が増えたなら、
どこかの書き込み経路が上限を超えてタグを足したということで、それはレポートで名指しする価値がある。

**直し方:** `--fix` では n/a。どのタグを落とすかはページが何についてのものかで決まり、
lint はページ本文を読まないので、6 個目のタグを消すと、たまたま最後に並んだものが
消えるだけになる。形式の崩れたタグの改名は、それを持つすべてのページの書き換えを意味する ——
vault 全体への書き込みだ。どちらも、ユーザーか、本文を文脈に入れてそのページを開く
次の skill に向けて示す。

指摘は `Over-Tagged and Malformed Tags` の節へ（見本の行は
`references/output-format.md`）、その合計は `LINT` の log エントリの 2 つのキーへ書く:
`over_tagged=N`（上限を超えたページ数）と `malformed_tags=N`（ページ数ではなく、
異なるタグ名の数）。単位が 2 つだからキーも 2 つ —— 1 つにまとめると差分が読めなくなる。

### 9. Visibility Tag Consistency

`visibility/` タグが正しく付いているか、必要な場所で黙って欠けていないかを確かめる。

**確かめ方:**

- **タグの無い PII のパターン:** 機微なデータをよく示すパターンでページ本文を grep する —— `password`、`api_key`、`secret`、`token`、`ssn`、`email:`、`phone:` の後に実際の値（フィールドの説明ではない）が続く行。ページが一致し、`visibility/pii` も `visibility/internal` も無ければ、分類の誤りの疑いとして指摘する。
- **`sources:` の無い `visibility/pii`:** `visibility/pii` を付けたページは、必ず `sources:` frontmatter フィールドを持つべきである —— provenance が無ければ、分類を検証する術がない。`sources:` の無い `visibility/pii` のページはすべて指摘する。

**直し方:**
- タグの無い PII のパターン: ページの frontmatter のタグに `visibility/pii` を足す（個人データではなくチーム内の文脈なら `visibility/internal`）
- `sources:` の欠落: provenance を足すか、ユーザーへ上げる —— 自動で埋めない

### 10. Misc Promotion Candidates (only when `misc/` exists)

**最初に `$OBSIDIAN_VAULT_PATH/misc/*.md` を Glob する。一致が無ければ、この検査を
丸ごと飛ばす —— 指摘もレポートの節も出さない。** そこへページを置くのは URL 取り込みの経路だけなので、
それを一度も使っていない vault には `misc/` がそもそも無く、毎回「候補 0 件」と報告する検査は
誰も読まない 1 行になる。

**確かめ方:** `misc/` の各ページの `affinity` frontmatter フィールドを読み、
どれか 1 つのプロジェクトのスコアが 3 以上のものを指摘する。

**直し方:** ページを `projects/<project-name>/references/`（または別の
適切なカテゴリ）へ移し、`category` frontmatter を更新し、`promotion_status` を消し、
vault を grep して被リンクを見つけて更新する。wikilink を多く持つページで `affinity` が
空なら、スコアは低いのではなく古い —— それを根拠に昇格させず、そう書く。

### 11. Synthesis Gaps

wiki に欠けている、価値の高い統合（synthesis）の機会を見つける —— 多くのページで共起しているのに、それらをつなぐ `synthesis/` ページが無い概念の組。

**確かめ方:**
- `synthesis/` のページをすべて挙げる —— それぞれが既に扱っている概念の組を（リンクかタイトルから）集める
- `concepts/` と `entities/` から、よくリンクされる概念を 10〜15 個選ぶ —— Check 0 のグラフの
  incoming の数で順位づけする
- 各組について、**両方**へリンクしているページを数える。`--json` の `edges` のリストを
  使う: 解決したリンクについての `[{from, to}]` なので、ある概念へリンクしているページは、
  `to` がその概念のパスである辺の `from` の値だ。2 つの集合の共通部分を取る。

  `grep -rl "\[\[ConceptA\]\]"` で数え**ない**。このパターンは
  `[[concepts/ConceptA]]`・`[[ConceptA|label]]`・`[label](concepts/ConceptA.md)` を取りこぼし、
  コードフェンスの中の構文の例まで数える。ここの 2 つの vault では、本当の共起のうち
  一方でおよそ 3 分の 1 しか、もう一方ではほとんど何も見つけられないはずだ。
- 共起が 3 以上で、既存の synthesis ページが無い組を指摘する

**直し方:** その組を報告する。穴を埋めるとは、関わるページの本文から新しい `synthesis/` ページを
書くことで —— 内容を文脈に入れての書き込みであり、lint はそれを持って
いない。穴を塞ぐためだけにスタブのページを作らない。

### 12. Confidence and Lifecycle Schema

confidence と lifecycle の frontmatter スキーマを守らせる。**許される値の集合、各値がどの段に位置するか、段の決め方の唯一の典拠はルーブリックである: `~/.claude/doc/doc_wiki_lifecycle_rubric.md`。** 許される値の集合や段の割り当てを、このファイルにも他のどの skill にも決して写さない。値の名前ではなく段で指す。

モードは 2 つ:
- **`--check`**（既定・読み取りのみ）—— エラーと警告を報告する
- **`--fix`** —— ドリフトを検出したときに限り `base_confidence` を書き換えてよい（Rule 12e）。`lifecycle` は決して書き換えない

#### Rule 12a — `lifecycle` enum validation

**確かめ方:** 全ページの frontmatter を `^lifecycle:` で grep し、値を取り出し、ルーブリックにある許される値の集合と**集合として**比べる。

**個々の値で決して grep しない。** そうすると 2 通りの失敗が起き、どちらも黙って起きる:
- `grep 'lifecycle: verified'` は `verified` にしか一致しない —— 接頭辞が付いた値や同義語を見ないので、新しい段がエラーも出ずに飛ばされる
- 素の `grep verified` は、`log.md` のエントリやページ本文のどこに出てきてもその語に一致するので、その件数はそもそもページ数ではない

許される値の集合は —— 序列内も序列外も —— ルーブリックにある（§序列 / §序列外）。そこで読み、値をこのファイルへ写さない。

**旧値（まだルーブリックへ移行していない vault）:** `{active, stable}` はルーブリックより前の値だ。**件数を添えた 1 行の警告**として報告し、ページごとに 1 件ずつ報告しない —— ページ単位の指摘はレポート全体を埋もれさせる。

**直し方:** n/a —— `--fix` は `lifecycle` を決して書かない: 段はページ本文の証拠で決まり（ルーブリックの R1–R4）、lint は本文を読まない。それを設定してよいのは、本文を文脈に持っている skill だけだ。

#### Rule 12b — `base_confidence` range

**確かめ方:** 全ページの frontmatter を `^base_confidence:` で grep する。`[0.0, 1.0]` の外にある値と、このフィールドがまったく無いページを指摘する。

**直し方:** n/a（値が誤っているのは skill の計算が誤っていたということ —— 手で直すよう示す）

#### Rule 12c — Stale page report (computed overlay)

陳腐化は決して保存しない —— 読むときに `evidence_at` から計算する（ページに `evidence_at` が無ければ `updated:` へ落ちる）: `is_stale = (today − date) > 90 days`。

**確かめ方:** ページごとに `is_stale` を計算し、その `lifecycle` の値が位置する**段**で分岐する（段はルーブリックの §序列、はしごの外の値は §序列外）。値は集合として照合し、決して部分文字列として照合しない:

| 対象 | 陳腐化したときの扱い |
|---|---|
| rank 5–6（人間が承認した段） | より強い注記 —— 人間がこれを保証しており、その後に前提が動いたかもしれない |
| rank 3–4（AI が確かめた段） | 標準の警告で、**再検証**として書く。決して降格として書かない —— AI の検査を走らせ直すのは安く、ルーブリックは lint が `lifecycle` を書くことを禁じている |
| rank 1–2（はしごの最下部） | **飛ばす。** 古さは情報を足さない |
| `index`（序列外） | 標準の警告 —— 90 日誰も触れていない索引こそ、それが防ぐために存在する失敗そのものだ |
| その他の序列外の値すべて | 飛ばす —— はしごの外にあり、鮮度についての主張ではない |

**直し方:** `--fix` は `lifecycle` を書き換え**ない**。陳腐化は、再確認で `evidence_at` が更新されたときに解消する。

#### Rule 12d — Supersession integrity

**確かめ方:** `superseded_by: "[[target]]"` を持つ各ページについて:
- 指す先のページが存在することを確かめる
- 指す先のページ自体が `archived` でないことを確かめる（循環や連鎖した後継関係がない）
- 循環が無いことを確かめる（A が B を置き換え、その B が A を置き換える）
- `superseded_by` が設定されているのに `lifecycle != archived` なら警告する（不整合な状態）

**直し方:** n/a —— 人間が解決するよう指摘する

#### Rule 12e — Confidence drift

**確かめ方:** Check 7 のスクリプトの実行結果から `base_confidence` を読む（ページが `base_confidence:` と `sources:` の両方を持たなければ `null`）。各エントリは `stored`、`recomputed`、`drift`、`drift_flag`（|drift| > 0.05）、そして `sources` —— 各行が `~/.claude/doc/doc_wiki_schema.md` の既定に従ってどの `source_id` とバケットへまとめられたか —— を持つ。指摘する前に、指摘するページの `sources` を読む: ある出典に対してバケットが明らかに誤っているとき（ベンダーの doc が `unknown` に分類されている等）は、数字を受け入れず `--bucket <source_id>=<bucket>` を付けて走らせ直す。

**直し方（`--fix` のときだけ）:** `--fix-confidence` を付けてスクリプトを走らせ直す（同じ `--bucket` の上書きも付ける）。ドリフトしたページの `base_confidence:` の行だけを書き換える。frontmatter を自動で書き換えるのは、これが**唯一のルール**だ。

#### Rule 12f — Evidence requirements for ranked pages

段は、ある行為がなされたことを主張する（ルーブリック: *この軸は自己評価の信頼度ではなく、行為を記録する*）。このルールは、ページがその行為への手がかりをまだ持っているかを確かめる。**このルールが無ければ、はしごは散文でしかない** —— そして検査の無い散文はずれていく。

**確かめ方:** rank 2–6 のページについて（ルーブリックの §序列 —— ルーブリックが証拠を要求する段）:

- `lifecycle_evidence` があり、空でない → でなければ**エラー**
- `evidence_at` があり、ISO 日付として解釈できる → でなければ**エラー**
- `lifecycle_evidence` が名指す節か表が、まだ本文にある → でなければ**警告**（「証拠が編集で消された。この段はもう裏付けが無い」）

rank 3–4 では加えて、ルーブリックがその段に要求する形を本文が 1 つも持たないとき**警告**する —— それは §序列 の *証拠として本文にあるべきもの* の列にある。形はそこで読み、このファイルへ写さない。

rank 1 と序列外の集合全体は飛ばす（ルーブリックの §序列外）。

**この最後の検査は散文に対するヒューリスティックで、誤検知を出す。** 警告に留めて決してエラーにせず、`--fix` にも決して手を出させない。ノイズになるほど頻繁に鳴るなら、直すべきはルーブリックの決定表を引き締めることで —— 受け入れる形を広げることではない。

**直し方:** n/a —— 本文を文脈に持ってそのページに触れる次の skill に向けて示す。

Rule 12a–12f の指摘は `Confidence/Lifecycle Issues` の節へ（見本の行は `references/output-format.md`）、その合計は `LINT` の log エントリの `lifecycle_issues=N` へ書く。

### 13. Typed Relationships Validity

`relationships:` frontmatter ブロックを検証する。`relationships:` ブロックの無いページは飛ばす —— このフィールドは任意だ。

**許される型:** 唯一の正典は **`~/.claude/doc/doc_wiki_schema.md` の
Typed Relationships の表**だ —— 10 の概念・16 の綴り。向きのある型は
順方向と逆方向の両方の綴りで有効。検査する前にその表を読む。
その集合をこのファイルへ決して写さない。

**確かめ方:**
- vault の全ページの frontmatter を `^relationships:` で grep する
- `relationships:` ブロックを持つ各ページについて、その frontmatter を読む（ページ本文全体は読まない）
- ブロックの各エントリについて:
  1. **型の検証** —— schema doc の表に無い `type:` の値を、**失敗ではなく
     警告として**報告する（下を参照）
  2. **リンク切れの target** —— Check 0 のリンクグラフがこれらを既に解決している。その `broken` か
     `ambiguous` のリストに出てくる `target:` が指摘だ。手で解決し直さない。
  3. **自己参照** —— 解決した target がそのページ自身の node id と等しいエントリを指摘する

**enum 外の型は警告である。** これまでに見つかった enum 外の型は、どれも
`wiki-update` / `wiki-ingest` が書いたもの —— enum を定義しているのと同じバンドル —— なので、
enum 外の型はたいてい、ユーザーの誤りではなく 1 つのシステムの中で語彙が割れていることを
意味し、target も問題なく解決する。それらを失敗として報告すると、本当に壊れている
指摘が埋もれる。失敗とするのは、解決しない target と必須の frontmatter の欠落だけだ。

**既知の別名 —— 見つけ次第正規化する。** 向きも意味も同じで、置き換え先の型は
enum の中にあるので、置き換えは純粋に機械的だ。**この表の置き場はここ
wiki-lint である** —— schema doc は意図して写しを持たず、このファイルを指している:

| 書かれた値 | 正規化先 |
|---|---|
| `relates_to` | `related_to` |
| `supersedes` | `replaces` |
| `depends_on` | `uses` |
| `enables` | `used_by` |
| `generalizes` | `extended_by` |
| `complements` | `related_to` |
| `applies` | `uses` |
| `applied_by` | `used_by` |

**enum に無い概念: 報告し、書き換えない。** schema doc の表にも別名の表にも無い型には、
正規化する先が無い —— それを
`related_to` に寄せると、誰かがそれを書いた理由である区別を捨てることになる。エントリは
そのまま残して報告する。enum を広げるのは schema の判断であって、lint の修正ではない。

**直し方:**
- 別名の型: 上の表に従って正規化する
- `type: superseded_by` / `type: replaced_by`: 関係の型ではない —— そのページは
  `lifecycle: archived` にし、**最上位の** `superseded_by:` フィールドを持たせるべきだ（別の名前空間。
  schema doc の Confidence and Lifecycle の節を参照）。その案内を添えて報告する
- 未知の型: そのまま残して報告する。enum を広げるのは schema の判断だ
- リンク切れの target: エントリを更新するか消す。target のページが存在すべきなら、先にそれを作る
- 自己参照: エントリを消す

指摘は `Typed Relationship Issues` の節へ（見本の行は `references/output-format.md`）、その合計は `LINT` の log エントリの `relationship_issues=N` へ書く。

## 出力形式

指摘は `## Wiki Health Report` として書き、検査ごとに `###` の節を 1 つずつ、検査の
順に並べる。**雛形と、すべての節の見本の行は
`references/output-format.md` にある —— レイアウトを作り出さず、それに従う**。何も見つからなかった検査の
節は省く。

## lint の後で

`log.md` に **1 行だけ**追記する —— これが書式のすべてで、毎回すべてのキーを書く:
```
- [TIMESTAMP] LINT issues_found=N orphans=X broken_links=Y ambiguous_links=A missing_frontmatter=FM missing_summary=S stale=Z contradictions=W index_issues=I prov_issues=P fragmented_clusters=F over_tagged=T malformed_tags=MT visibility_issues=V promotion_candidates=C synthesis_gaps=G lifecycle_issues=L relationship_issues=R graph=script|manual
```

キーの順は検査の順。`issues_found` は他のキーの合計では**ない** —— 過去の実行では
キーの合計 151 に対して 111、103 に対して 71 が記録された —— だから専用のキーを持たない件数は、
合計から逆算できず、そのまま失われる。レポートの節を持つ検査がすべてここにキーを
持つのはそのためだ。節を足すのと同じ編集でキーも足す。

前提条件が無かったために飛ばした検査（`misc/` の無い Check 10）は `0` を報告する。代わりにキーを落とすと、その行は以前の実行と照らし合わせて解析できなくなる。

`[TIMESTAMP]` は `date -u +%Y-%m-%dT%H:%M:%SZ` の出力 —— 実行して結果をそのまま貼る。手で書かない（理由: schema doc の `log.md`）。

`graph=` は、Check 0 がスクリプトを走らせたか、手作業の代替手順を使ったかを記録する。両者の
件数は比べられないので、これが無ければ実行間の差分は何の意味も持たない。

問題を自動で直すことを申し出るか、どれに対処するかをユーザーに決めてもらう。

---

## consolidate モード（`--consolidate`）

呼び出しに `--consolidate` が付いているときだけ: wiki-lint を報告のみから
修復して報告（"dream cycle"）へ切り替える。**`references/consolidate-mode.md` を読み、それに
従う** —— アクション、レポートのページ、dry-run の関門を定義している。

そこにあるルールのうち、そもそも書いてよいかを決める 3 つ:

- **必ず、まず dry-run。** 予定しているすべてのアクションを出力し、それから `"Apply these N changes? [yes / no / select]"` と尋ねる。明示的な答えの前には、どのページも書かない。
- 確認の要らない書き込みは、最後の `log.md` への 1 回の追記だけだ。
- ページを決してマージしない（それは `wiki-dedup` の仕事）。`lifecycle` も決して書かない —— consolidate はページ本文を読まないので、何かを段づけする根拠を持たない。