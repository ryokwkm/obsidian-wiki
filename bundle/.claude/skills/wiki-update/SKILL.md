---
name: wiki-update
description: 現在のプロジェクトで得た知識（外部ツールの仕様・設計判断とその理由・落とし穴）を Obsidian wiki へ蒸留・同期する。「wiki を更新して」「wiki に保存して」「obsidian を更新して」や英語の "update wiki" / "sync to wiki" と言われたとき、タスク完了時・コミット時に蒸留が要ると判断したとき、「〜の仕様書を作って」「ドキュメント化して」と言われたとき（独立した `doc_*.md` を作らず wiki へ蒸留する）に使う。どのプロジェクトからでも使える。
---

# Wiki Update — どのプロジェクトからでも wiki へ同期する

現在のプロジェクトで得た知識を、ユーザーの Obsidian wiki へ蒸留する。この skill は obsidian-wiki リポジトリに限らず、どのプロジェクトのディレクトリからでも動く。

## 着手前に

1. **設定を解決する** — `OBSIDIAN_VAULT_PATH` が既に export されていればそれを使う（shell rc / direnv / 親プロセス）。無ければ CWD から `$HOME` まで遡って `OBSIDIAN_VAULT_PATH=` を含む `.env` を探し、最初に見つかったものを採る。どちらも無ければ止まり、`.claude/settings.json`（`env`）・shell rc・direnv のどれかで設定するようユーザーに伝える —— パスを決め打ちしたり vault を推測したりしない。**どの vault に書くかはプロジェクトごとの設定で、グローバルな設定ではない** —— リポジトリ単位で設定されるので、セッションが最初から持っていると仮定しない。`OBSIDIAN_LINK_FORMAT` も同じ方法で読む（既定は `wikilink`、もう一方は `markdown`）。どのプロジェクトのディレクトリからでも動く。
2. `$OBSIDIAN_VAULT_PATH/.manifest.json` を読み、このプロジェクトが以前に同期されたかを確かめる。
3. wiki に既に何があるかを、**`index.md` を丸ごと読まずに**調べる。育った vault では `index.md` は数十 KB になり、闇雲に全部読むのがこの skill で最も高くつく操作になる。`~/.claude/doc/doc_wiki_schema.md` の Retrieval Primitives の表に従い、`index.md` をプロジェクト名とこれから書く各概念で `Grep` し、ヒットした数ページの `summary:` を読む。`index.md` を全部読むのは、その grep が空で、なお vault の全体像が要るときだけ。

Step 4–5 で内部リンクを書くときは、解決した `OBSIDIAN_LINK_FORMAT` が選ぶ形式を使う —— `~/.claude/doc/doc_wiki_schema.md` の Link Format の節を参照。

## 運用ルール

この skill が*何を*書くかではなく、*どう*動くかを決めるルール。

1. **委譲して、報告は 1 行にする。** 別のタスクの終わりにこの skill を走らせるときは、メインセッションが先に回答を書き切り、skill は `fork` サブエージェントで走らせる（fork は文脈を引き継ぐので説明し直しが要らず、vault の作業がメインの文脈に入らない）。ユーザーに届くのは Step 7 の 1 行だけ。順序を逆にすると、回答が直前の vault 作業に引っぱられる。
2. **vault は独立したリポジトリとして commit する。** vault が別の git リポジトリなら、パスを明示して stage し —— `git -C "$OBSIDIAN_VAULT_PATH" add <paths you wrote>` —— そちらで commit する。プロジェクト側で素の `git add` を叩かない: 親リポジトリを巻き込む。誰も commit しない vault の変更は誰にも回収されず、いずれ無関係な commit に紛れ込む。
3. **サイズメーターの超過は書き手のバグであって、上限の問題ではない。** SessionStart のメーターが `hot.md` か `index.md` の上限超過を報告しても、`WIKI_HOT_MAX_BYTES` / `WIKI_INDEX_MAX_BYTES` を上げない。増えた節を突き止め（`git -C "$OBSIDIAN_VAULT_PATH" log -p -- hot.md index.md`）、それを書いた skill を直す。派生ビューは捨てて作り直せるキャッシュで、蒸留した知識はページに置く。
4. **他のセッションが並行して書いている。** `hot.md` / `index.md` は作業中にも変わる —— だから Step 6 では `Edit` しか許していない。`.manifest.json` は 1 本の `jq` コマンドで読んで書き換える。Read → 考える → Write の往復をすると数秒〜数分の窓が開き、その間の別セッションの更新が失われる。

## Step 1: プロジェクトを把握する

カレントディレクトリを見て、このプロジェクトが何かをつかむ:

- `README.md`、docs/、その他の markdown ファイル
- ソースの構造（フレームワーク・言語・主要な抽象）
- `package.json`、`pyproject.toml`、`go.mod`、`Cargo.toml` など、プロジェクトを定義しているもの
- git log（「fix typo」の類ではなく、判断を示すコミットメッセージに注目する）
- Claude のメモリファイルがあればそれも（プロジェクト内の `.claude/`）

プロジェクト名はディレクトリ名から整えて決める。

## Step 2: 差分を求める

`.manifest.json` でこのプロジェクトのエントリを確かめる:

- **初回か？** 全体をスキャンする。すべてが新規。
- **同期済みか？** `last_commit_synced` を見る。差分を求める前に、記録された SHA にまだ到達できるかを確かめる:
  ```bash
  git merge-base --is-ancestor <last_commit_synced> HEAD
  ```
  - **Exit 0（祖先である）:** 安全。`git log <last_commit_synced>..HEAD --oneline` で何が変わったかを見る。
  - **Exit 1（祖先でない —— rebase か force-push があった）:** 記録された SHA はもうこのブランチの履歴に無い。ユーザーに警告する: *「記録済みの commit `<sha>` に到達できません —— ブランチが rebase または force-push された可能性があります。全体スキャンに切り替えます。」* そのうえで初回の同期として扱う: すべてを再スキャンし、Step 6 の最後で `last_commit_synced` を現在の HEAD の SHA に更新する。

前回の同期から意味のある変化が無ければ止まる（何と言うかは Step 7）。

## Step 3: 何を蒸留するか決める

Karpathy のパターンの核心の問い: **3 か月後に文脈ゼロで戻ってきたとき、このプロジェクトについて何を知りたいか？**

蒸留する価値があるもの:

- 設計判断と、*なぜ*そうしたか
- 作りながら見つけたパターン（書いておかなければまた検索し直すもの）
- プロジェクトが依存するツール・サービス・API と、それらのつなぎ方
- 主要な抽象とそのつながり、メンタルモデル
- 比較検討したトレードオフと、何をなぜ選んだか
- 作りながら学んだことのうち、コードを読んでも分からないもの

蒸留する価値がないもの:

- ファイル一覧・定型コード・見れば分かる設定
- 教訓の広がらない個別のバグ修正
- 依存のバージョン・lock ファイルの中身
- コードが既にはっきり語っている実装の詳細
- diff を読めば誰でも分かる日常的な変更

判断基準: **コードを読めば答えが出るなら wiki に書かない。20 コミット分の git blame を読んで理由を組み立て直す羽目になるなら、wiki に書く。**

## Step 4: wiki ページへ蒸留する

### プロジェクト固有の知識

`$VAULT/projects/<project-name>/` の下に置く:

```
projects/<project-name>/
├── <project-name>.md          ← プロジェクトの概要（プロジェクト名で付ける。_project.md ではない）
├── concepts/                  ← プロジェクト固有の考え方・アーキテクチャ
├── skills/                    ← プロジェクト固有の手順・パターン
└── references/                ← プロジェクト固有の出典の要約
```

概要ページ（`<project-name>.md`）に書くこと:
- プロジェクトが何か（1 段落）
- 主要な概念とそのつながり
- プロジェクト固有のページとグローバルな wiki ページへのリンク

### グローバルな知識

プロジェクトに固有でないものは、グローバルのカテゴリへ置く:

| 見つけたもの | 置き場 |
|---|---|
| 一般的な概念を学んだ | `concepts/` |
| 再利用できるパターンや技法 | `skills/` |
| ツール・サービス・人物 | `entities/` |
| プロジェクトをまたぐ分析 | `synthesis/` |

### ページの書式

すべてのページに YAML frontmatter を付ける。folded scalar 記法（`title: >-` / `summary: >-`）を使う —— 句読点（`:`、`#`、引用符）を含んでも、エスケープ規則なしでパーサーが安全に読める。中身は空白 2 つで字下げする:

```markdown
---
title: >-
    ページのタイトル
category: concepts
tags: [tag1, tag2]
sources: [projects/<project-name>]
summary: >-
    このページが何を扱うかを 1〜2 文で（200 字以内）。
provenance:
  extracted: <computed>         # 本文のマーカー実数から出す。下の数字は書かない
  inferred: <computed>
  ambiguous: <computed>
base_confidence: <computed>     # 式の出力のみ。証拠が強いからと上げない
lifecycle: draft                # 下限。この skill は直前にした作業を蒸留するので、証拠はたいてい手元にある ——
                                # `~/.claude/doc/doc_wiki_lifecycle_rubric.md` に従って昇格させ、
                                # `lifecycle_evidence` と `evidence_at` を足す。近いページの段を写さない。
lifecycle_changed: TIMESTAMP_DATE
created: TIMESTAMP
updated: TIMESTAMP
---

# ページのタイトル

- コードや doc に実際に書いてある事実。 ^[extracted]
- 設計がこう動く理由。 ^[inferred]

他のページとは [[wikilinks]] でつなぐ。
```

**`provenance` と `base_confidence` はテンプレや近いページの数字を写さず、毎回計算して書く。**

- `provenance` は `~/.claude/doc/doc_wiki_schema.md`（Provenance Markers）の 1 行レシピでマーカーを数え、
  その出力を写す。分母はマーカーの総数で、散文の行数ではない（散文を数えると実装ごとに答えが割れる）。
  wiki-capture の `_raw/` 用キャリブレーション表は本ページへ持ち込まない
- `base_confidence` は同じ doc の式の出力だけ（出典のバケットは同 doc の既定に従う）。証拠の強さは
  `lifecycle` の軸が担うので、ここで上乗せしない（二重に載せると Rule 12e がドリフトとして鳴る）

**`summary:` frontmatter を書く。** 新規・更新したすべてのページに、1〜2 文・200 字以内で、`>-` の folded 形式で書く。プロジェクト同期でのよい summary は「タイトルからは推測できない、このプロジェクトについての何をこのページが教えてくれるか」に答える。このフィールドが `wiki-query` の安価な検索を支えている。

**provenance マーカーを付ける。** `~/.claude/doc/doc_wiki_schema.md` の Provenance Markers の節に従う。プロジェクト同期では特に:

- **Extracted**（`^[extracted]`）—— コード・設定・doc・コミットメッセージに見えるもの全般: ファイル構成、依存、関数シグネチャ、ファイルが何をするか。
- **Inferred**（`^[inferred]`）—— 判断が*なぜ*なされたか、設計の根拠、トレードオフ、「チームは Y だから X を選んだ」。ただしコミットメッセージ・doc・ADR が明示しているものは除く。
- **Ambiguous**（`^[ambiguous]`）—— コードと doc が食い違うとき、または移行の途中で 2 つのパターンが併存しているのが明らかなとき。

そのレシピでマーカーを数え、得られた割合を、新規・更新したすべてのページの `provenance:` ブロックへ書く。

### 更新か新規作成か

- ページが vault に既にあるなら、新しい情報をそこへ**マージ**する。重複を作らない。
- 既存ページに足すときは、`updated` のタイムスタンプを更新し、新しい出典を加える。
- 新しく作る前に、`index.md` で既に何があるかを確かめる。

## Step 5: 相互リンク

ページを作成・更新したら:

- 新しいページから、関連する既存ページへ `[[wikilinks]]` を張る
- 関連する箇所では、既存ページから新しいページへも `[[wikilinks]]` を張り返す
- プロジェクトの概要ページから、プロジェクト固有のページすべてと、関連するグローバルのページへリンクする

## Step 6: 追跡情報を更新する

### `.manifest.json` を更新する

このプロジェクトのエントリを**キー単位で**追加・更新する —— **オブジェクトを丸ごと置き換えない。** 同じエントリを他の skill や他のセッションも書く。知らないキーはすべて残し、オブジェクト丸ごとの代入ではなく、対象を絞った `jq` の代入（`.projects["<name>"] += {…}`）で書く。キーの集合・jq の書き方・キーを落とすと何が壊れるかは `~/.claude/doc/doc_wiki_schema.md` にある —— ここでフィールドを作り出さない。

```json
{
  "projects": {
    "<project-name>": {
      "source_cwd": "/absolute/path/to/project",
      "last_synced": "TIMESTAMP",
      "last_commit_synced": "abc123f",
      "pages_in_vault": ["projects/<project-name>/<project-name>.md", "..."],
      "note": "free-text remark about this project's sync, if there is one"
    }
  }
}
```

### `index.md` を更新する

新しく作ったページのエントリを足す。1 エントリは 1 行で、ページの `summary:` フィールドをそのまま写す（200 字以内）。エントリをそれより長くしない —— 文が長すぎるならページの `summary:` を直し、index のエントリはいじらない（200 字を超える summary は `wiki-lint` が既に指摘する）。

### `log.md` を更新する

追記する:
```
- [TIMESTAMP] WIKI_UPDATE project=<project-name> pages_updated=X pages_created=Y source_cwd=/path/to/project
```

`[TIMESTAMP]` は `date -u +%Y-%m-%dT%H:%M:%SZ` の出力 —— 実行して結果をそのまま貼る。手で書かない（理由: schema doc の `log.md`）。

### `hot.md` を更新する

**`hot.md` はキャッシュで、1 エントリ 1 行。ここには何も溜めない。** 作業中にも他のセッションが書き込むので、**変更は変更箇所をちょうど覆う最小範囲への `Edit` だけで行い、`Write` は使わない**（理由: schema doc の Special Files）。

- 変える部分だけを読む: `Grep -A 6 "## Recent Activity" $OBSIDIAN_VAULT_PATH/hot.md` なら、ファイルを読み込まずに置き換える行が返る。
- **Recent Activity** —— この節だけ: 操作 1 回につき 1 行、新しい順、直近 3 件だけ。自分の行を 1 回の `Edit` で先頭に入れ、最も古い行は**別の** `Edit` で落とす —— 両方を一度にやると、節全体を `old_string` に入れることになる。
- **Active Threads** —— この節だけ: スレッド 1 つにつき 1 行、最大 3 件、1 行ごとに `Edit` 1 回。もう動いていないスレッドは、新しいものと並べて残さずに落とす。**この節がファイルに無ければ、無いままにする** —— 足さない。
- **気づき・教訓・判断はここに書かない。** それらはこの同期で書いたページ本文に置く —— そのための蒸留である。`hot.md` へ重複させたことが、かつて際限なく膨らんだ原因だった。
  - ページ内では **1 行に**収め、末尾に足すのではなくその話題の節に置き、**ページが既に別の言い方で同じことを言っていない場合に限る** —— 別の場所で言い直した教訓は、置き場所が変わっただけの同じ重複である。
- frontmatter の `updated` タイムスタンプも、同じ回の中で別の `Edit` で更新する。

エントリはファイル一覧ではなく、何が起きたかで書く: 「obsidian-wiki を同期 —— wiki-capture を追加した。新しくできるようになったのは、進行中の会話を wiki ページにすること。」

`hot.md` が無ければ、`~/.claude/doc/doc_wiki_schema.md` の雛形（Special Files → `hot.md`）どおりに作る。教訓の節は無い —— 書き漏れではなく意図的に置いていない。

**ここで QMD の検索インデックスを更新しない。** markdown の vault が正本で、SessionStart hook がすべての vault を無条件に再インデックスする —— いま書いたページは、次のセッションの開始時に検索できるようになる。それまでは `wiki-query` が `Grep` に落ちるので、インデックスを放っておいても何も失わない。同期の一部として `qmd update` / `qmd embed` を走らせない。

## Step 7: 報告

この skill はたいてい別のタスクの終わりに頼まれずに走るので、何を出力しても、ユーザーが実際に尋ねたことへの回答と競合する。邪魔にならないようにする。

- **最後に 1 行だけ**、ユーザーの言語で: `wiki: <page> を更新` —— Step 2 で何も見つからなければ `wiki: 更新なし`。
- 行った手順・ページの構成・`index.md` / `hot.md` / `log.md` の差分を**説明しない**。成果物は vault であって報告ではない。長く語る価値のあることは、いま書いたページに書く。
- **失敗したときは 1 行足して**、何が壊れたかを名指す。それを報告するために同期の残りをロールバックしない。

## コツ

- **積極的にマージする。** プロジェクトが React Server Components を使っていて `concepts/react-server-components.md` が既にあるなら、新しいページを作らない。既存ページを更新し、このプロジェクトを出典に加える。
- **タグは感覚ではなく規約で付ける。** vault のページが既に付けているタグを使い回し、プロジェクトごとに新しい語彙を作らず、`~/.claude/doc/doc_wiki_schema.md` のタグ規則（1 ページに付けてよいタグの数・予約済みの `visibility/` 名前空間）に従う。
- **コードを写さない。** 実装ではなく*知識*を蒸留する。「このプロジェクトは 300ms の遅延付きの debounce 検索パターンを使う」は役に立つ。debounce 関数そのものを貼るのは役に立たない。
- **プロジェクトの概要ページが起点になる。** `<project-name>.md` は、全体をつかむために最初に読むファイルだ。よく書く。
