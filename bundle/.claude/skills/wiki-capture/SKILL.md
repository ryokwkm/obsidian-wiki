---
name: wiki-capture
description: 現在の会話を、チャットの書き起こしではなく宣言的な知識として wiki ノートへ保存する。「これを保存して」「この会話を残して」「wiki に追加して」や英語の "save this" / "capture this" と言われたときに使う。`--quick`（「クイックキャプチャ」「raw に放り込んで」/ "quick capture"）は manifest も index も書かず `_raw/` へ 60 秒で投げ込み、後で wiki-ingest が本ページへ昇格させる。
---

# Wiki Capture — 会話を wiki ノートにする

現在の会話から得た知識を、恒久的な wiki ノートとして残す。目的は*中身* —— 知識そのもの —— を取り出すことであって、何が話されたかの要約ではない。

この skill には 2 つのモードがある:

- **フルモード（既定）** —— 内容を分類し、相互リンク済みの完成した wiki ページを適切なカテゴリへ直接書く。この文書の残り（Step 1–7）がこれにあたる。
- **クイックモード（`--quick`）** —— 手間ゼロのステージング: manifest / index / log を書かずに、知見を 60 秒以内で `_raw/` へ投げ込む。セッションの途中で残すために使う。下を参照し、そこで止まる —— フルモードの手順は実行**しない**。

## クイックモード（`--quick`）

`/wiki-capture --quick` として呼ばれたとき、または "quick capture" / "capture this finding" / "save this bug fix" / "save this gotcha" / "drop this to raw" / "quick save to wiki" と言われたときに発動する。

クイックモードは呼ばれたときにしか走らないので、知見がまだ会話の中にあるうちに呼ぶ。

**速度の約束:** インラインだけで済ませる。サブエージェントを使わない。manifest / `index.md` / `log.md` / `hot.md` を書かない。目標: 60 秒未満。wiki の本ページへの昇格は、後で `/wiki-ingest` が行う。

1. **設定を解決する** —— `OBSIDIAN_VAULT_PATH` が既に export されていればそれを使う。無ければ CWD から `$HOME` まで遡って `OBSIDIAN_VAULT_PATH` を含む `.env` を探し、最初に見つかったものを採る。どちらも無ければ `.claude/settings.json`（`env` ブロック）で設定するようユーザーに伝えて止まる。`OBSIDIAN_RAW_DIR` の既定は `$OBSIDIAN_VAULT_PATH/_raw`。**このディレクトリは無いものと考える** —— ほとんどの vault はまだ一度もキャプチャをステージングしたことがない —— ので、書く前に作る: `mkdir -p "$OBSIDIAN_RAW_DIR"`。

2. **関門 —— KEEP か SKIP か？** 取り出す前に、このセッションに残す価値があるかを判断する。これで、誰も昇格させないファイルが `_raw/` に溜まらずに済む。
   - **SKIP**（「このセッションには残す価値のあるものがありません。」と伝えて終える）にするのは、次がすべて当てはまるとき: 会話が純粋な対話（計画・Q&A・説明）で、実装を伴わない。エラー・デバッグ・問題解決が見当たらない。意外なことも、文書化されていないことも無い。どの知見もドキュメントから既に明らか。
   - **KEEP**（先へ進む）にするのは、次のどれか 1 つでも当てはまるとき: 調査を経て修正か回避策が見つかった。ライブラリ・API・フレームワークの自明でない挙動が確かめられた（エッジケース・文書化されていない制約・時間を取られる落とし穴）。デバッグのセッションが具体的な結論に達した。再利用できるパターンが生まれた。
   - **ユーザーが頼んだときは KEEP 寄りに倒す** —— 理由があって呼んだのだから。**頼まれずに自分から呼んだとき**（一区切りついた作業を自発的に締めくくるとき）は **SKIP 寄りに倒す** —— 誰もその依頼を吟味していないので、明確な証拠があるときだけ KEEP にする。

3. **再利用できる知見を探す** —— 自明でないバグとその根本原因、フレームワーク・ライブラリの落とし穴、意外な API の挙動、調べて見つけた回避策、環境・ツールチェーンの癖、デバッグから得たパターン。プロジェクト管理の進捗報告、CLAUDE.md に既にある設定、結論の出ないやりとり、ドキュメントを読めば明らかなこと、挨拶の類は飛ばす。中身のあるものが出てこなければ、そう伝えて止まる。

4. **話題ごとにまとめる** —— `_raw/` のファイルは知見ごとではなく、話題のクラスタごとに 1 本。それぞれ kebab-case のスラッグで名付ける（例: `swift-actor-reentrancy`、`nextjs-hydration-mismatch`）。

5. リポジトリ名・ファイルパス・言及されたフレームワーク・エラーメッセージから**プロジェクトの文脈を推定する**。確実に推定できる最も具体的な名前を使い、できなければ `null`。

6. **raw ファイルを書く** —— クラスタごとに `$OBSIDIAN_RAW_DIR/<ISO-date>-<slug>.md` を書く。frontmatter の完全な仕様、知見ブロックの本文構成、provenance と confidence のキャリブレーションは `references/RAW-FORMAT.md` を読む。クラスタごとに変わるフィールド: `title`、`tags`（2〜4 個。新しく作らず、vault の `index.md` に既に出ているタグを使い回す）、`summary`（200 字以内）、`project`（推定した名前か `null`）、`base_confidence` と `provenance.extracted` / `provenance.inferred` の配分（どちらも `references/RAW-FORMAT.md` のキャリブレーション表から取る —— 数字を当て推量しない）、`lifecycle_changed`（今日）、`sources`（`"<project> session (<YYYY-MM-DD>)"`）。

7. **完了を伝える** —— ステージングしたファイルを列挙し、昇格させるには `/wiki-ingest` を実行するようユーザーに伝える:
   ```
   Staged to _raw/:
     _raw/2026-05-27-swift-actor-reentrancy.md   — "Actor reentrancy causes deadlock in async forEach"
   Run /wiki-ingest to promote these to full wiki pages.
   ```
   クイックモードは意図して manifest・`index.md`・`log.md`・`hot.md` を書か**ない** —— `/wiki-ingest` による昇格がそのすべてを引き受ける。**ここで止まる。下のフルモードの手順は実行しない。**

---

## フルモード

## 着手前に

1. **設定を解決する** —— クイックモードの手順 1 と同じ。加えて `OBSIDIAN_LINK_FORMAT` を読む（既定: `wikilink`）。
2. これから書く概念で `$OBSIDIAN_VAULT_PATH/index.md` を Grep して既存ページを探す（`~/.claude/doc/doc_wiki_schema.md` の Retrieval Primitives）。丸ごと読むのは grep が空で返ったときだけ
3. `$OBSIDIAN_VAULT_PATH/hot.md` があれば読む —— Step 6 がこれを編集し、その `old_string` をこの読み込みから取る

Step 5 で内部リンクを書くときは、`~/.claude/doc/doc_wiki_schema.md` の Link Format の規則に従って `OBSIDIAN_LINK_FORMAT` の値を当てる（`wikilink` → `[[path/to/page|display]]`、`markdown` → 現在のファイルのディレクトリから計算した `[display](relative/path.md)`）。

## Step 1: 残す価値のあるものを見極める

会話を見渡す。そして問う: この会話を覚えていない 3 か月後にも価値を持つ知識が、ここで何か生まれたか？

残す価値があるもの:
- 下した判断と、*なぜ*そう判断したか
- 組み立てた分析・枠組み・メンタルモデル
- 技術的な知見・パターン・手順
- ある話題について統合した理解
- たどり着くのに手間のかかった、概念の明快な説明
- 会話で取り上げた外部ソースの重要な事実

飛ばすもの:
- 段取り・日程調整・挨拶の類
- 結論に至らなかった探索的なやりとり
- wiki に既にある内容

中身のあるものが出てこなければ、ユーザーにそう伝えて止まる。

## Step 2: 内容の種類を分類する

5 つの種類のどれか 1 つを割り当てる —— これで置き先のフォルダと書きぶりが決まる:

| 種類 | 説明 | 置き先のフォルダ |
|---|---|---|
| `synthesis` | 複数段階の分析、または推論を要した特定の問いへの答え | `synthesis/` |
| `concept` | 定義・枠組み・メンタルモデル（あるものが*何であるか*） | `concepts/` |
| `source` | 話題にした外部の文書・記事・リソースの要約 | `references/` |
| `decision` | 戦略・アーキテクチャ・設計上の選択とその根拠 | `synthesis/` |
| `session` | 会話が複数の話題にまたがるときの、議論全体の要約 | `journal/` |

内容が明らかに特定のプロジェクトに属するなら（文脈やユーザーの言及から判断する）、代わりに `projects/<project-name>/<category>/` の下に置く。

## Step 3: 宣言的な知識として書き直す

会話の要約を書か**ない**。知識そのものを、宣言的な現在形で書く:

- 書かない: 「ユーザーが X について尋ね、Claude は…と説明した」
- 書く: 「X は…によって動く」
- 書かない: 「…なので Y を使うことにした」
- 書く: 「[理由] なので、Z より Y がよい。[^[inferred]（根拠が明言されず、暗に示されただけのとき）]」

`~/.claude/doc/doc_wiki_schema.md` に従って provenance マーカーを付ける:
- *Extracted* —— 会話の中で明言されたもの → `^[extracted]`
- *Inferred* —— 会話から一般化・統合したもの → `^[inferred]`
- *Ambiguous* —— 異論がある・不確か・矛盾しているもの → `^[ambiguous]`

## Step 4: スラッグとタイトルを決める

内容から、明快で中身の分かるタイトルを導く。それをスラッグにする:
- 小文字、単語はハイフンで区切る
- 最大 50 文字
- スラッグに日付を入れない（frontmatter に `created` がある）

## Step 5: wiki ノートを書く

置き先のパスに、必須の frontmatter を付けてファイルを作る:

```yaml
---
title: >-
  <Title>
category: <synthesis|concepts|references|journal|skills>
tags: [<vault の index.md で既に使われているドメインのタグ 2〜5 個>]
sources:
  - conversation:<ISO-date>
created: <ISO-8601 timestamp>
updated: <ISO-8601 timestamp>
summary: >-
  <1〜2 文・200 字以内で、「このページはどんな知識を持っているか？」に答える>
provenance:
  extracted: 0.X
  inferred: 0.X
  ambiguous: 0.X
base_confidence: 0.42           # 出典が会話ログ 1 本のときの、式の固定の出力。
                                # 別個の出典が増えたら、`~/.claude/doc/doc_wiki_schema.md` の
                                # Confidence formula に従って計算し直す（`_raw/` の表からは決して取らない）
lifecycle: draft                # 下限。キャプチャは、後の工程が本文を読んで
                                # `~/.claude/doc/doc_wiki_lifecycle_rubric.md` に従って段を決めるまで、ここに留まる
lifecycle_changed: <ISO date today>
---
```

種類ごとの本文構成:

**synthesis / decision:**
```markdown
# Title

## Context
<きっかけ —— 扱っている問題や問い>

## Finding / Decision
<核心の知識、または結論>

## Reasoning
<なぜそうなのか、またはなぜこの選択をしたのか>

## Implications
<ここから何が言えるか —— 気をつける点・次の一手・トレードオフ>

## Related
<関連するページへの [[wikilinks]]>
```

**concept:**
```markdown
# Title

<明快な 1 文での定義。>

## What It Is
<その概念の説明>

## How It Works
<仕組みまたは構造>

## When to Use
<適用範囲・条件・トレードオフ>

## Related
<[[wikilinks]]>
```

**source:** —— 文書がローカルファイル（エクスポートやダウンロードしたもの）なら、先に `_source_docs/` へコピーし（`<YYYY-MM-DD>-<original filename>`。既定は `$OBSIDIAN_VAULT_PATH/_source_docs` で、`OBSIDIAN_SOURCES_DIR` があればそちらが優先）、コピーの vault 相対パスを `sources:` に書く。vault の外のパスは長持ちする出典にならない —— ダウンロードフォルダは片付けられる。
```markdown
# Title

> Source: <タイトルまたは URL>

## What It Covers
<そのソースが何を扱っているか>

## Key Points
<provenance マーカー付きの主張の箇条書き>

## Open Questions
<提起しているが答えていないこと —— 無ければ省く>

## Related
<[[wikilinks]]>
```

**session:**
```markdown
# Title

*Session captured: <date>*

## Topics Covered
<短い一覧>

## Key Takeaways
<出てきた中で最も重要な 3〜5 点>

## Decisions Made
<明示的に下した判断があれば、根拠とともに>

## Open Questions
<未解決のまま残っていること>

## Related
<[[wikilinks]]>
```

どのノートも、既存の wiki ページへ必ず 2 つ以上リンクする。書く前に `index.md` を検索する。関連ページが 2 つに満たなければ、言及した概念のうち最も重要なものについて最小限のスタブを作る。

## Step 6: 追跡ファイルを更新する

**`index.md`** —— 新しいページを、そのカテゴリの節の下に足す。1 エントリは 1 行で、ページの `summary:` フィールドをそのまま写す（200 字以内）。エントリをそれより長くしない —— 文が長すぎるならページの `summary:` を直し、index のエントリはいじらない（200 字を超える summary は `wiki-lint` が既に指摘する）。

**`log.md`** —— 追記する:
```
- [TIMESTAMP] CAPTURE type=<type> page="<path>" title="<title>"
```

`[TIMESTAMP]` は `date -u +%Y-%m-%dT%H:%M:%SZ` の出力 —— 実行して結果をそのまま貼る。手で書かない（理由: schema doc の `log.md`）。

**`hot.md`** —— 変更は `Edit` だけで行い、`Write` は決して使わない。1 回に 1 行ずつ、各 `old_string` は変更箇所をちょうど覆う最小範囲に留め、その文字列はいま読んだ内容から取る。**Recent Activity** では: いまキャプチャしたものを 1 行、1 回の `Edit` で一覧の先頭に入れ、続いて最も古いエントリを**別の** `Edit` で消して、一覧を 3 件の操作に保つ —— 両方を 1 回の `Edit` でやると、一覧全体を `old_string` に入れることになる。それから `updated` のタイムスタンプを `Edit` する。他のセッションが同じファイルを並行して編集するので、ファイル丸ごとの書き込みは、こちらが読んでから書くまでの間に他のセッションが足したものを黙って落とす。`Edit` は完全一致を要するので、相手の行を食う代わりに目に見えて失敗する —— そして範囲が小さいほど、そもそも衝突しにくい。**ノートの教訓をここに写さない** —— 教訓は既にノートにあり、そこが本来の置き場である。

## Step 7: ユーザーに完了を伝える

保存したパスとタイトルを報告する:
```
Saved to: projects/<name>/synthesis/<slug>.md
Title: <Title>
Type: synthesis
```

## 品質チェックリスト

- [ ] 内容を宣言的な知識として書き直した（チャットの書き起こしではない）
- [ ] 種類を正しく分類した。置き先のパスが正しいフォルダにある
- [ ] frontmatter に title, category, tags, sources, summary, provenance が揃っている
- [ ] 既存ページへの wikilink が 2 つ以上ある
- [ ] `index.md`・`log.md`・`hot.md` を更新した
- [ ] 保存先のパスをユーザーに伝えた
