# 論文深掘りテンプレート（Paper Deep-Dive Template）

**このファイルが Paper Deep-Dive Template の正本である。** これを使うのは `wiki-ingest` だけ ——
バンドルの他のどこもこれを定義もコピーもしていない。

汎用のページ雛形（`~/.claude/doc/doc_wiki_schema.md` を参照）はたいていのソースに合う。
**学術論文は例外である。** `references/` に置く ML/AI/LLM/VLM（など）の論文では、
中身はアーキテクチャ・数式・結果の表にある ——
簡潔な "Key Ideas" の箇条書きでは、まさにそれが失われる。これらには下のより豊かな雛形を使う。
ここは *"compile, don't retrieve"*（検索せずにコンパイルする）が、読み手が論文の代わりに読んで学べる、
徹底した自己完結の解説に道を譲る唯一の場所である。

必要な部品は Obsidian がネイティブに描画するので、追加のツールは要らない: Mermaid のフェンス付き
図、`$$…$$` の LaTeX（MathJax）、markdown の表、`![[image]]` / `![[paper.pdf#page=N]]` の
埋め込み。

この雛形を使うのは、ソースが学術論文（arXiv・学会）で、図や数式が中身を支えている場合だけ。
それ以外はすべて汎用のページ雛形を使う。frontmatter・provenance
マーカー・confidence・lifecycle・`relationships:` は変わらない —— 違うのは本文の節だけ
である。

````markdown
---
# ...必須の frontmatter。汎用の雛形と同じ。category: references...
---

# Paper Title

> [!tldr] 1 文で: 何が新しいか、と見出しになる結果。

## Problem & Motivation

この論文が対処する、壊れている・欠けているものは何か。

## Method / Architecture

散文での解説。論文の実物のアーキテクチャ図を主な図として
埋め込む（PyMuPDF で取り出す手順は SKILL.md の *学術論文* を参照）。
図を 1 つも取り出せないときに限って、Mermaid のフローチャートへ落ちる。

![[attachments/<slug>-fig1.png]]
*Figure N (Author Year): one-line caption.*

## Key Equations

中核の数式 1〜3 本を、バッククォートのコードではなく別行立ての数式で:

$$ \mathcal{L} = \mathbb{E}_{x}\!\left[-\log p_\theta(y \mid z)\right] $$

## Results

見出しになる数字は、カンマ区切りの塊ではなく表で —— 論文に主要な結果・動機を示す図
（スケーリングのプロット・ベンチマークのグラフ・能力のコラージュ）があれば
それも埋め込む:

| Method | Benchmark | Metric | Cost |
|---|---|---|---|
| Baseline | … | … | … |
| **This paper** | … | … | … |

![[attachments/<slug>-resultsN.png]]
*Figure N (Author Year): one-line caption.*

## Limitations

論文が認めている、または避けて通っていること。行間を読んだものは ^[inferred] を付ける。

## Related

近い研究への型付きの `[[wikilinks]]`。

## Sources

- クリックできる正規のリンク。例: <https://arxiv.org/abs/XXXX.XXXXX>
````

論文の散文から組み立て直した Mermaid の図は、書き写しではなく統合である ——
解釈が自明でないときは `^[inferred]` として扱う。
