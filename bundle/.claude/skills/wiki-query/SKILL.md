---
name: wiki-query
description: コンパイル済みの Obsidian wiki を検索し、ページからの引用付きで統合した答えを返す。「◯◯について何を知ってる」「◯◯に関するものを全部出して」「X と Y はどう繋がってる」や英語の "what do I know about X" / "find everything related to Y" と言われたときに使う。型付きエッジを複数ホップ辿るマルチホップの質問にも答える。「ざっと答えて」/ "quick answer" で index だけ読む高速モード。どのプロジェクトからでも使える。
---

# Wiki Query — 知識を引き出す

生のソース文書ではなく、コンパイル済みの Obsidian wiki を相手に質問へ答える。wiki には、あらかじめ統合され、相互参照された知識が入っている。

## この skill は読み取り専用

`wiki-query` は質問に答え、wiki の中身は変えない: 唯一の書き込みは Step 6 の `log.md` への追記だけ。ページ・`index.md`・`hot.md`・`_insights.md`・`.manifest.json` は、変更が役立ちそうに見えても触らない。これらのファイルの不変条件は書き手の skill が受け持っているからだ。

ユーザーのメッセージに新しい知見、行動の依頼（"save this"・"ban X"・"record that"）、その他の変更を含意するものが入っていても、**実行しない。** 質問に答え、変更は提案だけにとどめ、ユーザーを適切な skill へ案内する:
- 短いメモ・落とし穴 → `wiki-capture --quick`
- 新しいページを丸ごと 1 枚 → `wiki-capture`
- プロジェクトの知識の同期 → `wiki-update`

## 着手前に

1. **設定を解決する。** `$OBSIDIAN_VAULT_PATH` が既に export されていればそれを使う（shell rc / direnv / 親プロセス）—— それが優先する。未設定なら CWD から `$HOME` まで遡って `OBSIDIAN_VAULT_PATH=` を含む最初の `.env` を探し、その値を使う。どちらからもパスが得られなければ止まり、ユーザーに伝える: `No vault config found. Set OBSIDIAN_VAULT_PATH in .claude/settings.json (env), a shell rc, or direnv.` vault のパスを決め打ちせず、他のプロジェクトの vault を決して借りない。どのプロジェクトのディレクトリからでも動く。
2. **同じ設定から QMD の変数を読む** —— `QMD_WIKI_COLLECTION`・`QMD_TRANSPORT`・`QMD_CLI_SEARCH_MODE`・`QMD_PAPERS_COLLECTION`・`QMD_EXTRA_COLLECTIONS` を、検索の戦略を決める前に読む。`QMD_WIKI_COLLECTION` が設定されていれば、Step 2b の transport の確認だけを条件として、QMD を使えるものとして扱う。空か未設定なら、QMD を飛ばす理由を短く述べて grep の経路を取る。grep の経路でも十分に機能する。
3. **まだ vault からは何も読まない。** まず質問を分類し（Step 1）、それからはしごを安い端から登る（Step 2 以降）。特に次の 2 つのファイルはただでは読めず、反射的に開いてはならない:
   - **育った vault では `index.md` は数十 KB になる。** 質問の語で grep する（Step 2）。丸ごと読むのは、質問が wiki の*形*についてのとき —— "what's in here"、"what areas do I cover" —— だけ。
   - **`hot.md` には蒸留した知識が無い。** 直近の数回の操作と進行中のスレッドのキャッシュなので、*話題*についての質問ではバイトを食うだけで何も答えない。はしごの最初ではなく最後の段だ —— Step 4c を参照。

## 可視性フィルタ（任意）

既定では、可視性タグにかかわらず**すべてのページを返す**。これは既存の挙動を保つ —— ユーザーが求めない限り何も変わらない。

ユーザーの質問に **"public only"**・**"user-facing"**・**"no internal content"**・**"as a user would see it"**・**"exclude internal"** のような言い回しが含まれていれば、**フィルタモード**を有効にする:

- **遮断タグの集合**を作る: `{visibility/internal, visibility/pii}`
- 「index で絞る」（Step 2）では、frontmatter のタグに遮断タグを含む候補を飛ばす
- 「節だけ読む」「全文を読む」「グラフ走査」「直近の動きを読む」（Step 3–4c）では、遮断されたページを読まず、引用もしない
- 回答は**許可されたページだけから**統合する —— 除外したページがあることには触れない

`visibility/` タグが無いページと、`visibility/public` が付いたページは、常に含める。

フィルタモードでは、Step 6 のログのエントリにフィルタを記す: `mode=filtered`。

## 検索の手順

vault を読むことがこの skill のコストの大半を占める。**質問に答えられる最も安いプリミティブを使い、それで答えられないときだけ一段上げる** —— プリミティブそのもののコスト表は `~/.claude/doc/doc_wiki_schema.md` の「Retrieval Primitives」の節にある。下の Step は、その表を質問への回答に当てはめたもので、安い段から並べてある:

> `index.md` のエントリ（grep）→ ページの `summary:` frontmatter → grep した節（`-A`/`-B`）→ ページ全体の読み込み → `hot.md`

下の各 Step には、その段で何が得られなかったら次の段へ登ってよいかを書いてある。決していきなりページ全体を読まない。また、`hot.md` はその左にある段がすべて失敗するまで決して開かない —— 唯一の例外は明示的に最近のことを尋ねる質問で、そのときは `hot.md` が答えを持つ唯一のファイルだ（Step 4c）。

### Step 1: 質問を把握する

質問の種類を分類する:
- **事実の確認** —— "What is X?" → 関係するページを探す
- **関係の質問** —— "How does X relate to Y?" / "What contradicts X?" → 両方のページ、その相互参照、型付きの辺を持つ `relationships:` frontmatter ブロックを探す
- **経路・マルチホップの質問** —— "How is X connected to Y?" / "What links X to Y?" / "Trace the chain from X to Z" / "What does X depend on transitively?" → X と Y は直接リンクしておらず、つながりは中間のページを通る。Step 4b のマルチホップのグラフ走査を使う。
- **統合の質問** —— "What's the current thinking on X?" → X に触れるページをすべて探し、統合する
- **欠落の質問** —— "What don't I know about X?" → 欠けているものを探し、open questions の節を確かめる

**モード**も決める:
- **index-only モード** —— "quick answer"・"just scan"・"don't read the pages"・"fast lookup" で発動する。Step 2 の後で止まる。frontmatter と `index.md` のエントリだけから答える。
- **通常モード** —— 下の段階的なパイプライン全体。

### Step 2: index で絞る（安い）

*ページ本文を 1 つも開かずに*候補の集合を作る:

- **`index.md` が最初のフィルタ —— grep し、読まない。** すべてのページが 1 行の説明とタグ付きで並んでいる。`Grep -n "<query-term>" $OBSIDIAN_VAULT_PATH/index.md` なら、関係するひと握りのエントリ行が数百バイトで返る。丸ごと読むのは、質問が wiki の全体の範囲についてのときか、grep が何も返さず、言い換える前にどんなカテゴリがあるかを見る必要があるときだけ。
- `Grep` でページの **frontmatter だけ**を走査し、title・tag・alias・summary の一致を探す。vault の `.md` ファイルに絞った `^(title|tags|aliases|summary):` のようなパターンは、本文の grep よりはるかに安い。
- 上位 5〜10 件の候補ページのパスを集め、次の順で並べる:
  1. title か alias の完全一致
  2. タグの一致
  3. summary フィールドが質問の語を含む
  4. `index.md` のエントリが質問の語を含む
- **同じ順位の区分の中では tier の順を当てる:** 2 つの候補のスコアが等しければ、`tier: core` → `tier: supporting` → `tier: peripheral` の順に優先する。`tier:` frontmatter フィールドは、他のフィールドと同じ安い grep で読む。
- **`tier:` が無いことは降格ではない。** ページを `tier: core` へ昇格させる skill は無いので、ほとんどのページはこのフィールドをそもそも持たない —— 無いことの意味は「誰も分類していない」であって「価値が低い」ではない。タグの無いページは `supporting` であるかのように順位を付け、フィールドが無いこと*を理由に*候補を落としたり、順位を下げたり、読むのを飛ばしたりは決してしない。ページが候補の座を失ってよいのは、明示された `tier: peripheral` があるときだけ。

**index-only モード**なら、ここで止まる。`summary:` フィールド・タイトル・`index.md` の説明だけから答える。回答にははっきりラベルを付ける: **「（index-only の回答 —— ページ本文は読んでいません。以下の事実はページの summary からのもので、細かな含みを落としている可能性があります）」**。そのあと Step 5 へ飛ぶ。

### Step 2b: QMD による意味検索（任意 —— 解決した設定に `QMD_WIKI_COLLECTION` が必要）

**ガード: 設定の解決後に `$QMD_WIKI_COLLECTION` が空か未設定なら、この Step 全体を飛ばして Step 3 へ進む。作業の途中経過の報告で、変数が無いことに触れる。**

> **QMD が無い？** Step 3 へ飛び、vault に対して `Grep` を直接使う。QMD のほうが速く概念も汲み取れるが、grep の経路でも十分に機能する。

`QMD_WIKI_COLLECTION` が設定されていれば、質問が `index.md` のメタデータで既に完全に答えられている場合を除き、`Grep` に手を伸ばす前に QMD を走らせる。QMD が特に優先されるのは、質問が意味的なとき、プロジェクト固有のとき、関連する文脈を求めるとき、またはタイトルや frontmatter にそのままは現れないかもしれない語を使うときだ。

QMD の transport は `$QMD_TRANSPORT` から選ぶ:

- `mcp`（既定）: エージェントに設定された QMD の MCP ツールを使う。
- `cli`: ローカルの qmd CLI を実行する。素の名前 `qmd` で呼び、`${QMD_CLI:-qmd}` は決して使わない: コマンドの許可リスト（allowlist）は変数展開の*前*のコマンド名で照合するので、変数の形では権限が黙って失われる。

🔴 **選んだ transport が使えなければ、諦める前にもう一方の transport を試す。** `qmd` の CLI は動くのに QMD の MCP サーバーが登録されていない環境もある —— この Step を飛ばさず CLI へ落ちる。どちらの transport も動かないとき（MCP ツールが無く、*かつ*使える `qmd` も無い、またはコマンドがエラーになる）に限り、QMD を飛ばして Step 3 へ進む。

CLI へ落ちずに飛ばすのは小さな損失ではない: **意味検索のすべて** —— `vec:` による recall、HyDE による展開、reranking —— を捨て、字面どおりの `Grep` だけが残る。それでは "what is X like" に答えられず、概念を名前で呼ばずに説明しているページも見つけられない（日本語の vault では字面だけの経路の取りこぼしがさらに増える —— 拠り所となる語の境界が無い）。

MCP transport では:

```
mcp__qmd__query:
  collections: [<QMD_WIKI_COLLECTION>]   # 例: ["knowledge-base-wiki"]。配列で、OR で照合する
  intent: <the user's question>
  searches:
    - type: lex    # キーワードの一致 —— 正確な名前・ファイルパス・エラーメッセージに向く
      query: <key terms>
    - type: vec    # 意味の一致 —— 概念・パターン・"what is X like" に向く
      query: <question rephrased as a description>
```

CLI transport では、`$QMD_CLI_SEARCH_MODE` からコマンドを選ぶ:

`no-sudo`・`ansible_become=false`・`~/.local/bin` のような、演算子に似たトークンや句読点の多いトークンは `lex:` の行に置く。`vec:` の行は、ハイフン付きの `-term` 形の語を含まない平易な自然文に書き直す。QMD は `-term` を否定として扱い、否定は `vec`/`hyde` のクエリでは使えない。

🔴 `lex:` / `vec:` の行は、下のように本物の改行を含む 1 つのダブルクォート文字列に入れる —— `$'…\n…'` は決して使わない。ANSI-C クォートは `${QMD_CLI:-qmd}` と同じくコマンドを許可リストから外す。すると embedding が GPU の初期化で失敗し、それでも qmd は正常終了して **lex だけの結果**を返すので、意味検索の半分が黙って消える。

- `quality`（既定）: 関連度が最も高い。CPU では遅い。
  ```bash
  qmd query "lex: <key terms>
  vec: <question rephrased as a description>" -c "$QMD_WIKI_COLLECTION" -n 8 --files
  ```
- `balanced`: LLM の reranking を省いたハイブリッド検索。`quality` が遅すぎるときに使う。
  ```bash
  qmd query "lex: <key terms>
  vec: <question rephrased as a description>" -c "$QMD_WIKI_COLLECTION" -n 8 --no-rerank --files
  ```
- `fast`: 意味だけの recall。正確な名前・ファイルパス・エラーメッセージが重要なときは代わりに `search`。
  ```bash
  qmd vsearch "<question rephrased as a description>" -c "$QMD_WIKI_COLLECTION" -n 8 --files
  ```

CLI の出力に docid があれば、`qmd get "#docid"` で順位付きの文書を docid から取り出す。

返ってきた抜粋や順位付きのファイルは、節の要約を先読みしたものとして使える。それで質問に完全に答えられるなら Step 3 を飛ばして Step 4 へ直行する（QMD が上位にしたページだけを読む）。そうでなければ、順位付きのファイル一覧を手がかりに、Step 3 でどのファイルを grep するか読むかを決める。

**鮮度:** SessionStart hook がインデックスを更新するので、インデックスはこのセッション開始時点の vault を映している —— このセッションの*最中に*書かれたページはまだインデックスに入っていないかもしれない。この skill は読み取り専用で、自分でインデックスを更新することは決してない。いま書かれたと分かっているものが返ってこなければ、無いと結論づけずに `Grep` で探す。

**質問の元資料が `_raw/` にありそうなときは `papers` も検索する:**

`QMD_PAPERS_COLLECTION` が設定されていて、ユーザーの質問が取り込んだ論文の扱っていそうな話題（研究・理論・背景）なら、papers の collection に対しても並行して検索する。回答では、生のソースをコンパイル済みの wiki ページとは分けて引用する。

**`QMD_EXTRA_COLLECTIONS` が設定されていれば、読み取り専用の追加 collection も検索する:**

`QMD_EXTRA_COLLECTIONS` は、このプロジェクトが読むが決して書かない*他の* vault の collection 名を空白区切りで並べたもの（例: 共有のベースの上に作ったプロジェクトが、ベースの vault を読む）。話題からの推測で絞らず、この Step に達したすべての質問で検索する —— この vault だけでは不完全だと分かっているからこそ存在するものだ。

- **CLI:** 並んだ名前ごとに `-c <name>` を 1 つずつ、同じコマンドの `-c "$QMD_WIKI_COLLECTION"` の後ろに足し、各名前は文字どおりに書き出す（値は「着手前に」で読んである）。そうすれば 1 回のクエリで、この vault と追加の vault をまとめて順位付けできる:
  ```bash
  qmd query "lex: <key terms>
  vec: <question rephrased as a description>" -c "$QMD_WIKI_COLLECTION" -c <extra-1> -c <extra-2> -n 8 --files
  ```
  フラグを組み立てるのにループや `$(...)` は決して使わない —— `qmd` の周りにそのどれかがあるとコマンドが許可リストから外れる。`${QMD_CLI:-qmd}` と同じ罠だ。
- **MCP:** `collections: [<QMD_WIKI_COLLECTION>, <extra-1>, …]`（配列で、OR で照合する）を渡し、CLI と同じく 1 回のクエリでまとめて順位付けする。
- **追加 collection のヒットを読む** —— `qmd://` のホスト部が collection 名を示す。それは `$OBSIDIAN_VAULT_PATH` の外にあるので、Step 3–4 の `Grep` と `Read` は届かない: `qmd get qmd://<collection>/<path>`（ページ全体）か `qmd get qmd://<collection>/<path>:<from>:<count>`（節。Step 3 に相当）で取り出す。`--files` の出力には行番号が無い。`<from>` を知るには、`--files` を付けずに `qmd search "<key terms>" -c <collection>` を走らせる —— 各ヒットの見出しが `qmd://<collection>/<path>:<line>` になっている。そのページの `[[wikilinks]]` は辿らない —— リンクはこの vault ではなく、そのページ自身の vault の中で解決される。
- **引用するとき** —— `qmd://<collection>/<path>` と書き、決して `[[...]]` と書かない（wikilink はこの vault の中を指し、そこにそのページは無い）。
- QMD が使えなければ、追加 collection はまったく検索できない（grep の経路はこの vault しか覆わない）—— 何も無かったかのように匂わせず、回答でそう述べる。

### Step 3: 節だけ読む（中程度のコスト —— Step 2/2b で決着しないときだけ）

上位の候補それぞれについて、*ページ全体を読まずに*関係する節を引き出す:

- `Grep -A 10 -B 2 "<query-term>" <candidate-file>` で、一致の前後の行だけを取る。
- これでたいてい、ヒット 1 件あたり 100〜500 行ではなく 15〜30 行で済む。
- 節の grep ではっきり答えが出れば、Step 5 へ直行する。

### Step 4: 全文を読む（高い —— 最後の手段）

Step 2 と 3 で質問に答えられないときだけ:

- 上位 **3** 件の候補を `Read` で全文読む。どの 3 件を読むかを選ぶときは、同順位の決め手として tier の順を当てる: `tier: core` のページを先に読み、明示された `tier: peripheral` は唯一の一致でない限り最後に回す。タグの無いページは `supporting` として競う —— フィールドが無いからといって決して見送らない（Step 2 を参照）。
- 答えに相互参照が要るなら、それらのページから `[[wikilinks]]` を最大 1 ホップだけ辿る。
- **候補の `sources:` が `_source_docs/` を指していて**、質問が蒸留で落ちるもの —— 正確な引用・数値・参考文献 —— を要するときは、そのファイルを `Read` する。それは vault が持つ原本の逐語コピーで、意図して検索インデックスから外してあるので、このホップが唯一の到達手段だ。両者が食い違うときは蒸留したページを優先する: 蒸留が原本を訂正しているかもしれない。
- **関係の質問では**（"How does X relate to Y?" / "What contradicts X?"）: 候補ページの `relationships:` frontmatter ブロックも読む。各エントリは型付きで向きのある辺を与える —— 正規の型の集合は **`~/.claude/doc/doc_wiki_schema.md` の Typed Relationships の表**にある（10 の概念・16 の綴り。向きのある型には順方向と逆方向の両方の綴りがある）。記憶にある一覧で作業しない。回答ではこれらを明示的に示す —— 「ページ A *contradicts* ページ B（型付きの辺）」のほうが「ページ A はページ B にリンクしている」より役に立つ。
- 既知の欠落について "Open Questions" の節を確かめる。
- それでも足りなければ、**そのときに初めて** vault 全体への広い本文 grep へ落ちる。上の段へ進んだことをユーザーに伝える —— これは高くつく経路で、ユーザーは知っておくべきだ。

### Step 4b: マルチホップのグラフ走査（型付きの辺）

普通の検索は、質問の語に*言及する*ページを浮かび上がらせる。X と Y が同じページに一度も現れないとき、それでは**経路・マルチホップの質問** —— "How is X connected to Y?"、"What does X depend on transitively?"、"Trace the chain from X to Z" —— に答えられない。答えはどれか 1 つのページ本文ではなく、型付きの辺のグラフの*形*にある。それを辿るのがこの Step だ。

この Step は経路・マルチホップの質問のとき（または関係の質問で 2 ページの間に直接の辺が返らないとき）**だけ**走らせる。すべて frontmatter から組み立てる —— ここではページ本文を決して読まない。

1. **型付きの辺の隣接リストを作る（安い）。** すべてのページの `relationships:` ブロックを 1 回で grep する —— `Grep -A 20 "^relationships:" <vault>/**/*.md`（frontmatter だけ）。各エントリから、向きと型を持つ辺 `source —type→ target` が 1 本得られる。逆方向も辿れる辺として加える（`(reverse)` と印を付ける）。型付きの主張には向きがあっても、「つながっている」は対称だからだ。向きのある型は公式に両方の綴り（順方向と逆方向 —— `~/.claude/doc/doc_wiki_schema.md` の Typed Relationships の表を参照）で存在するので、辺を型で絞るとき、または回答の根拠を型に置くときは、2 つの綴りを 1 つの概念として扱う: `uses` で絞るなら、source と target を入れ替えた `used_by` の辺にも一致させなければならない。片方の綴りだけで絞ると、一致する辺の半分が黙って落ちる。本文の普通の `[[wikilinks]]` は、経路を完成させるのに必要な場合に限り、型の無い `related_to` の辺として数える —— まず型付きの辺を優先する。

2. **端点を特定する。** X（質問が 2 つ挙げていれば Y も）を、Step 2 で作った一覧（registry）を使ってページのパスへ解決する。端点があいまいなら、tier の最も高い候補を選び —— タグの無いページも Step 2 のとおり競う —— その仮定を書き留める。

3. **範囲を限った BFS。** X から隣接リストをたどって外へ広げる:
   - **最大深さは既定で 3 ホップ**（それを超えるつながりに意味があることはまれ）。ユーザーが "deep" / "however many hops it takes" と言ったときだけ 4 に上げる。
   - **フロンティアの上限:** 訪問済みの集合が約 60 ページを超えたら、ノードの展開をやめる —— vault 全体へ広げず、途中までの結果を報告する。
   - **端点が 2 つの質問**（X→Y）では: 最短経路が見つかった時点で止め、そのあと少しだけ続けて、別の経路があれば最大 2 本まで示す。
   - **端点が 1 つの質問**（X から推移的に）では: 深さの上限内で到達できるすべてのノードを、ホップ数ごとにまとめて集める。

4. **経路を辺の型とともに報告する。** 端点だけでなく鎖を示す —— 型付きの辺*こそが*答えだ:

   ```
   [[concepts/transformers]] —uses→ [[concepts/attention]] —derived_from→ [[concepts/rnn-seq2seq]] —uses (reverse)→ [[concepts/lstm]]
   ```

   ホップ数を述べ、型の無い `related_to` で代用したホップには印を付ける（そうした鎖は弱い）。`(reverse)` の印は弱さではない —— 向きのある辺を逆から読んでも同じ関係で、schema の逆方向の綴りによって両方の読み方が同格に扱われる —— が、読み手が保存された向きを見られるよう印は残す。深さの上限内に経路が無ければ、はっきりそう述べる: 「X から Y への型付きの辺の経路は 3 ホップ以内にありません —— グラフ上で切り離された領域にあります。」それ自体が役に立つ知見（グラフの欠落）だ。

**コストのガード:** この Step は grep で frontmatter だけを読む。隣接リストの grep が何も返さなければ（`relationships:` を使っているページがまだ無い）、グラフに辿れる型付きの辺が無いこと —— vault のページがこのフィールドより古いこと —— を報告し、本文の `[[wikilinks]]` を使った通常の 1 ホップの検索へ落ちる。

### Step 4c: 直近の動きを読む（`hot.md` —— はしごの最後の段）

`hot.md` は、中身が蒸留ではなく*運用上の*ものである唯一の vault のファイルだ: 直近の数回の操作と、進行中のスレッド。読むのはちょうど次の 2 つの場合だけ:

1. 質問が明示的に最近のことを尋ねている —— "what did I just work on"、"what changed"、"where did I leave off"。このときは `hot.md` を*最初に*読む。それを記録している唯一のファイルだからだ。
2. 上のどの段も失敗し、質問が進行中の作業（ページへ蒸留されるにはまだ新しすぎるもの）に関わっていそうに聞こえる。

*話題*についての質問では飛ばす。たまたまその話題に触れていても、中身はそれが指すページにある —— リンクを辿ってそれらのページを引用し、`hot.md` は引用しない。主張の出典として `hot.md` を決して引用しない。

### Step 5: 回答を統合する

wiki の中身から回答を組み立てる:
- `[[page-name]]` 記法で具体的な wiki ページを引用する
- 回答がどの Step から来たかを書き添える（「summary で見つけた」か「grep した節」か「ページ全体を読んだ」か）—— ユーザーが確度をつかむ助けになる
- wiki に矛盾があれば、両方の側を示す
- wiki が扱っていないことは、はっきりそう言う
- 欠落を埋めそうなソースを提案する

**ページの信頼度の注記:** 引用するすべてのページについて `lifecycle` フィールドを読み —— あれば `evidence_at`・`lifecycle_changed`・`lifecycle_reason`・`superseded_by` も —— 引用にその場で注記を付け、読み手がそれぞれがどれだけ強く裏付けられているかを見分けられるようにする。

**これこそが、はしごの存在意義のすべてだ。** 何かを測ったページと推測したページは、どちらがどちらかを言わない限り、統合した回答の中では同じに見える。

**正典は `~/.claude/doc/doc_wiki_lifecycle_rubric.md`** —— 値、その序列、各値が「誰が主張を確かめたか」について何を表明するか、陳腐化の閾値は、すべてそこに、そこに*だけ*ある。注記する前に読む。記憶で注記せず、その値をここで決して再掲しない。

注記の仕方:

- **`lifecycle` は値全体で照合し、決して部分文字列で照合しない。** どの値も他の値の接頭辞にならないよう設計されており、部分文字列で照合するとページに黙って誤ったラベルが付く。
- **主張を何が裏付けているかを、`[[wikilink]]` の直後の短い括弧書きで述べる** —— 誰かが実行したのか、読んだだけか、推論しただけか、まったく確かめていないか。意味はルーブリックから取り、文言は一句に収める。
- **証拠の弱いページには、目に見える但し書きを必ず付ける。** これは任意ではない: 注記の無い推測は事実として読まれる。
- **置き換えられたページ: 代わりに後継を引用し**、その名前を挙げる。disputed のページは disputed と示し、印が付いた日付と、frontmatter に理由が記録されていればその理由を添えなければならない。
- **古くなった証拠は段を保ったまま、再検証の注記が付く。** 古さは `evidence_at`（ページに無ければ `updated:` へ落ちる）からルーブリックの閾値に照らして計算し、注記には再確認のコストを反映させる —— 人間の承認を更新するのは高くつき、AI の再実行は安い。
- **新しく、よく裏付けられたページには注記を付けない。** はしごはまさにこの場合をそっとしておくためにある。すべての引用に注記を付けると、読み手は注記を全部読み飛ばすよう慣らされる。
- 理由や `evidence_at` を**決してでっち上げない**。フィールドが無ければ、注記のその部分を落とす。`lifecycle` がまったく無いページは schema より古い —— ルーブリックの既定である最下段として扱い、未確認と注記する。

統合した回答の中での形（書式の例示であって、値の一覧ではない）:
```
[[concept-page]] (reasoning only — no measurement behind this) — Claims X follows from Y.
[[spec-page]] (sourced, evidence from 2026-02-01 — cheap to re-run) — The current implementation does X.
```

**プロジェクトのソースのパスを示す（プロジェクト単位の質問）。** 引用したページがプロジェクト単位のもの —— パスが `projects/<name>/...` の下にあるか、frontmatter に `source_path` フィールドを持つ —— なら、実際のコードがどこにあるかを解決し、提案する修正が実在のファイルを名指しでき、次のターンでそれを編集できるようにする:

1. `$OBSIDIAN_VAULT_PATH/.manifest.json` を読み、`.projects.<name>.source_cwd` を引く —— これが正となるパス。
2. 代替: プロジェクトが manifest に無ければ、ページの `source_path` frontmatter を使う。

その絶対パスを書いた **`Source code:`** の行を回答に入れる。質問がコードの修正を望んでいることを含意するなら、そのパスを使って編集すべき具体的なファイルを名指しし（例: `<source_cwd>/src/lib/auth.js`）、**明示的な、別の次の一手として実装を申し出る** —— ただし質問への回答の最中には決して編集しない（上の「この skill は読み取り専用」のガードを参照）。

### Step 6: 質問をログに残す

`log.md` に追記する。この `log.md` への追記が、この skill の行う*唯一の*書き込み —— それ以外は何も編集しない。
```
- [TIMESTAMP] QUERY query="the user's question" result_pages=N mode=normal|index_only|filtered escalated=true|false
```

`[TIMESTAMP]` は `date -u +%Y-%m-%dT%H:%M:%SZ` の出力 —— 実行して結果をそのまま貼る。手で書かない（理由: schema doc の `log.md`）。

## 回答の形式

回答は次のように組み立てる:

> **Based on the wiki:**
>
> [ソースのページへの [[wikilinks]] を付けた、統合した回答]
>
> **Pages consulted:** [[page-a]], [[page-b]], [[page-c]]
>
> **Other vaults consulted:** `qmd://<collection>/<path>` —— 追加の collection が寄与したときだけ（Step 2b）
>
> **Gaps:** [関係しそうだが wiki が扱っていないこと]
>
> **Source code:** `<source_cwd>` —— 実装するなら、関係するファイルは `…`。
> （言ってもらえれば query モードを抜けて変更します。）

**Source code** の行は任意 —— `source_cwd` を解決できたプロジェクト単位の質問のときだけ入れる（Step 5 を参照）。
