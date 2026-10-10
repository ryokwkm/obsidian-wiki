# raw ファイルの書式リファレンス

`wiki-capture`（クイックモード）が書く `_raw/` ファイルの完全な仕様。
これらのファイルは `/wiki-ingest` が昇格させる前提で作られている。

## frontmatter

```yaml
---
title: "<クラスタの中身が分かるタイトル>"
category: skills
tags:
  - <primary-tech>
  - <vault の index.md で既に使われているドメインのタグを 1〜3 個追加>
summary: "<1〜2 文・200 字以内 —— この知見は何についてのものか？>"
tier: supporting
related: []
extends: null
contradicts: null
superseded_by: null
capture_source: claude-session
project: "<プロジェクト名か null>"
base_confidence: 0.75
lifecycle: draft                # 下限。raw のステージングは必ずここから始まる。段を決めるのは、ページが
                                # `_raw/` から本ページへ仕立てられるとき（`~/.claude/doc/doc_wiki_lifecycle_rubric.md` に従う）
lifecycle_changed: <YYYY-MM-DD>
provenance:
  extracted: 0.85
  inferred: 0.15
sources:
  - "<project> session (<YYYY-MM-DD>)"
---
```

## 本文: 知見ブロック

バグと修正の場合:

````markdown
## <Finding Title>

**Problem:** <何が自明でなかったか、何が壊れていたか —— 症状を具体的に>

**Root cause:** <なぜ起きたか —— エラーメッセージだけでなく、その下にある仕組み>

**Fix:**
```<lang>
// ❌ before
// ✅ after
```

**Confirmed by:** <ビルドが通った / テストが通った / 実際のアプリで動いた / エラーが消えた>
````

落とし穴と API の癖の場合（典型的なバグ→修正の流れが無いもの）:

```markdown
## <Gotcha Title>

**Behavior:** <ユーザーが驚いたこと>

**Explanation:** <なぜそう動くのか>

**Workaround / Pattern:** <代わりにどうするか>

**Confirmed by:** <どう確かめたか>
```

書くことの無い節は省く。注意点・関連するエッジケース・追って確かめたい問いは、
末尾に `**Notes:**` ブロックを足して書く。

---

## provenance と confidence のキャリブレーション

`~/.claude/doc/doc_wiki_schema.md` に従って、provenance マーカーを本文中に付ける:

| マーカー | 使うとき |
|---|---|
| `^[extracted]` | 会話の中で明言されたもの |
| `^[inferred]` | 直接言われたことを超えて統合・一般化したもの |
| `^[ambiguous]` | 不確か・不完全かもしれない・他所と矛盾している |

`base_confidence` と `provenance` の配分は、下の表で決める。

**適用範囲: `_raw/` のステージングだけ** —— `wiki-lint` は `_` で始まるディレクトリを決して走査しない。`/wiki-ingest` が
ファイルを昇格させるとき、schema doc の Confidence formula から `base_confidence` を計算し直す。**この表の数字を
昇格したページへ決して持ち込まない**（Rule 12e がドリフトとして報告し、`--fix` が上書きする）。

| 証拠の強さ | `extracted` | `inferred` | `base_confidence` |
|---|---|---|---|
| ビルドエラー + テスト通過 | 0.90 | 0.10 | 0.80–0.90 |
| 修正を当て、効いたように見えた | 0.75 | 0.25 | 0.70–0.75 |
| 議論したが、確認しきれていない | 0.60 | 0.40 | 0.60 |
| 1 件の事例から推論した | 0.50 | 0.50 | 0.55 |

`extracted + inferred` の合計は 1.0 にする（当てはまるなら、小さな `ambiguous` の割合を含める）。

---

## 1 つのファイルに複数の知見を置く

関連する複数の知見が同じ話題のクラスタに属するときは、本文に順に並べる
—— それぞれを `##` 見出し付きの独立した知見ブロックにする。最初のブロックの前に短い導入の段落を置き、
何がそれらを束ねているかを説明する。

```markdown
# Swift 6 Concurrency Gotchas

Findings from migrating an iOS app to strict concurrency checking. All confirmed during
the build phase.

## Actor reentrancy in async forEach

**Problem:** ...

## MainActor isolation not inferred on @Observable

**Problem:** ...
```
