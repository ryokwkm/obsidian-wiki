# consolidate モード（`--consolidate`）

呼び出しに `--consolidate` が付いているときだけこれを読む。wiki-lint を
報告のみから**修復して報告**へ切り替える —— wiki が自分で治るように定期的に走る
"dream cycle" である。

## 安全の手順

**必ず最初に dry-run で走らせる。** 何かを書く前に:

1. lint の検査をすべて走らせる（`SKILL.md` の Check 0–13）。
2. 予定している consolidate のアクションを構造化したリストで出力する（下の「dry-run の出力」を参照）。
3. ユーザーに尋ねる: `"この N 件の変更を適用しますか？ [yes / no / 番号で選ぶ]"`。
4. 明示的な確認を得てから書き込みに進む。ユーザーが番号で個々の
   アクションを選んだら、それだけを適用する。番号は dry-run の表示順（Action 1 → 5 の順）に振った通し番号。
5. ページを決してマージしない —— それには `wiki-dedup` を使う。`lifecycle` を決して書かない —— 行うのはリンク、
   `tier` の降格、印を付けることだけ。

確認の要らない唯一の書き込みは、最後の `log.md` への 1 回の追記である。

## consolidate のアクション（確認の後、この順に）

### Action 1: リンク切れを直す

スクリプトの `broken` のリストにあるエントリ**だけ**を扱う。`ambiguous` のものは決して扱わない ——
それらのリンクは誤りではなく、複数のページに一致しているだけで、1 つをプレーンテキストへ降格させると
機能している参照を壊す（Action 1a を参照）。

リンク切れの各リンク先について:
- タイトルかファイル名があいまい一致で最も近いページを vault から探す（`index.md` のタイトルを対象に `Grep` を使う）
- 最良の一致が 1 つに決まるなら（編集距離が 2 文字以内か、語根が同じ）: リンクを書き換える。書き換えを記録する: `[[Original]] → [[corrected-page]]`。
- 一致が無ければ: プレーンテキストへ変え（`~~[[Target]]~~` → `Target`）、コメント `<!-- リンク切れ: 一致するページが無い -->` を足す。
- リンク切れを満たすためだけに新しいページを決して作らない。
- リンクは**リンク元のページが既に使っている記法で**書き換える ——
  `[label](../dir/page.md)` を `[[page]]` に変えると、解決のされ方が変わる。

### Action 1a: 曖昧なリンクを修飾する

スクリプトの `ambiguous` のリストの各エントリについて: リンク先をディレクトリ付きで書き換える
（`[[build-spec]]` → `[[project-a/build-spec]]`）。選ぶのは、リンク元のページの主題に
合うページ。**どれを指したのかが周りの文から
明らかでなければ、そのままにして報告する** —— ここで推測すると、グラフを黙ってつなぎ替えることになる。

### Action 2: 孤立ページへ欠けている相互参照を足す

Check 1 の各孤立ページについて、そこで挙げた 2 つの誤検知を除いたうえで
（0 バイトのファイルと、意図して wiki ページにしていないディレクトリ —— これらには代わりに
`.wikilintignore` のエントリを足し、相互参照は決して足さない）:
- vault の本文を、そのページのタイトルか別名への言及で grep する（大文字小文字を区別しない）。
  **コードフェンスとインラインコードの中の言及は無視する** —— それらは例であり、リンクに
  すると周りの文の意味が変わる。
- 別のページで見つかった言及ごとに、プレーンテキストの言及を置き換えてリンクを足す。
  記法はそのページが既に使っているもの。
- 孤立ページ 1 つにつき挿入は 3 か所まで —— ページをリンクで溢れさせない。
- 範囲は孤立ページだけ。vault 全体のリンク付けに広げない。

### Action 3: 陳腐化した序列内のページに印を付ける

**このアクションは `lifecycle` を決して書かない。** 段はページ本文の証拠で決まり
（`~/.claude/doc/doc_wiki_lifecycle_rubric.md`）、`--consolidate` は本文を読まない。
してよいのは注記だけだ。

閾値はどの段でも **90 日** —— Rule 12c と同じ値で、決して独自の変種にしない。
`evidence_at` から計算し、無ければ `updated:` へ落ちる。

ページの `lifecycle` の値が位置する**段**で分岐する —— 段はここで値を書き直さず、ルーブリック
（§序列 / §序列外）から読む。値は集合として照合し、決して部分文字列として
照合しない:

- rank 5–6（人間が承認した段）で陳腐化 → 本文の先頭に足す: `> ⚠️ **陳腐化**: <date> に人間がこれを保証した。頼る前に確かめること。`
- rank 3–4（AI が確かめた段）で陳腐化 → 足す: `> ⚠️ **再検証**: この内容の証拠は <date> のもの。検査の再実行は安い。` **疑いではなく再検証として書く** —— 測定はその時点では正しかった
- `index`（序列外）で陳腐化 → 足す: `> ⚠️ **古い可能性**: このページは他のページを索引しており、最後に触れられたのは <date>。`
- それ以外 → コールアウトなし

コールアウトは、まだ無いときだけ足す。

### Action 4: tier の降格

`tier: supporting`（または未設定）で、**入ってくるリンクが 1 以下**、かつ 90 日以上
更新されていないページについて:
- `tier: peripheral` にする。
- ユーザーが見直せるよう、降格の一覧を出す。
- `tier: core` のページは自動で降格しない —— それらは手で設定されたものだ。

`≤ 1` はこのバンドルのどこでも降格の閾値だ（schema doc の
重要度の tier と同じ値 —— 決して独自の変種にしない）。

### Action 5: 矛盾のコールアウト

互いに矛盾すると印の付いたページの組（frontmatter の `relationships: contradicts`
によるもの、または Check 5 で指摘されたもの）それぞれについて:
- 該当する主張の近くに `> ⚠️ [[Other Page]] との矛盾を指摘` のコールアウトが既にあるかを確かめる。
- 無ければ、矛盾している主張（または節）の直後に 1 行で足す。矛盾している主張の場所が特定できなければ、本文の末尾に置く。"Key Ideas" や "Open Questions" の節があると決めてかからない（理由: schema doc のページ雛形）。
- 矛盾を解消しない。目に見える形で印を付けるだけにする。

### Action 6: consolidate のレポートを書く

すべてのアクションの後、`synthesis/consolidation-<YYYY-MM-DD>.md` にレポートを書く:

```markdown
---
title: consolidate レポート <YYYY-MM-DD>
category: synthesis
tags: [maintenance, consolidation]
sources: []
summary: wiki-lint --consolidate の <date> の実行から自動生成した consolidate レポート。
lifecycle: draft
lifecycle_changed: <date>
tier: peripheral
created: <ISO timestamp>
updated: <ISO timestamp>
---

# consolidate レポート — <YYYY-MM-DD>

## 概要
- 直したリンク切れ: N
- 修飾した曖昧なリンク: Q
- 足した相互参照: M
- 足した陳腐化のコールアウト: K
- tier の降格: D
- 足した矛盾のコールアウト: C

## リンク切れの修正
- `concepts/foo.md:12` — [[OldTarget]] → [[correct-target]]
- `entities/bar.md:8` — [[Missing]] → `Missing`（一致するページが無い）

## 修飾した曖昧なリンク
- `project-a/a.md` — [[build-spec]] → [[project-a/build-spec]]

## 足した相互参照（孤立ページの救済）
- `concepts/baz.md` — リンク元: [[concepts/alpha]], [[skills/beta]]

## 陳腐化のコールアウト
- `synthesis/old-analysis.md` — 陳腐化のコールアウトを追加（lifecycle=verified、evidence_at 2025-10-01）
- `project-a/calibration.md` — 再検証のコールアウトを追加（lifecycle=tested、evidence_at 2025-11-20）

## tier の降格
- `concepts/unused-concept.md` — supporting → peripheral（リンク 1 本・120 日更新なし）

## 矛盾のコールアウト
- `concepts/scaling.md` — [[synthesis/efficiency]] との矛盾を指摘
```

レポートのページは、ほかの新しいページと同じく `draft` である: 1 回の実行が何をしたかを述べるもので、
その中の証拠は何も確かめていないので、決して `draft` より上の段を持たない。

## dry-run の出力（書き込みの前に示す）

```
wiki-lint --consolidate — dry-run

予定しているアクション（全 N 件）:
[1] リンク切れの修正: concepts/foo.md:12 [[OldTarget]] → [[correct-target]]
[2] 曖昧なリンクの修飾: project-a/a.md [[build-spec]] → [[project-a/build-spec]]
[3] 相互参照の追加: concepts/baz.md ← [[concepts/alpha]]（孤立ページの救済）
[4] 陳腐化のコールアウト: synthesis/old-analysis.md（lifecycle=verified、evidence_at から 208 日）
[5] 再検証のコールアウト: project-a/calibration.md（lifecycle=tested、evidence_at から 95 日）
[6] tier の降格: concepts/unused.md → peripheral（リンク 1 本・112 日更新なし）
[7] 矛盾のコールアウト: concepts/scaling.md ↔ [[synthesis/efficiency]]

この 7 件の変更を適用しますか？ [yes / no / 番号で選ぶ]
```

## consolidate モードの log エントリ

```
- [TIMESTAMP] LINT_CONSOLIDATE links_fixed=N ambiguous_qualified=Q orphans_rescued=M stale_callouts=K tier_demotions=D contradiction_callouts=C report=synthesis/consolidation-YYYY-MM-DD.md
```

`[TIMESTAMP]` は `date -u +%Y-%m-%dT%H:%M:%SZ` の出力 —— 実行して結果を
そのまま貼る。

## ここではタグの別名を正規化しない

このモードはタグの別名を正規化しない。この skill の中で別名の一覧を作り出して、そうした処理を
足さない —— タグの別名表には、まず正規の置き場が 1 つ要る
（`~/.claude/doc/doc_wiki_schema.md`）。
