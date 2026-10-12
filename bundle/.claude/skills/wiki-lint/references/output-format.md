# Wiki 健全性レポート — 出力形式

`--check`（報告のみ）の実行のための雛形。lint の検査 1 つにつき節 1 つ、検査の順に並べる。
**何も見つからなかった検査の節は省く** —— 「0 件」の見出しが 16 個並んだレポートは、
セッション開始時にそれを読むエージェントに丸ごと読み飛ばされる。

ここの件数は、手で数え直したものではなく、Check 0 のスクリプトの出力のものでなければならない。

```markdown
## Wiki 健全性レポート

### 孤立ページ（N 件）
- `concepts/foo.md` — 入ってくるリンクも出ていくリンクも無い

### リンク切れ（N 件）
- `entities/bar.md` — [[nonexistent-page]] へリンクしている

### 曖昧なリンク（N 件）
- `project-a/a.md` — `build-spec` が 2 ページに一致する。ディレクトリで修飾する

### frontmatter の欠落（N 件）
- `skills/baz.md` — 欠けている: tags, sources

### summary の欠落（N 件 —— soft）
- `concepts/foo.md` — `summary:` フィールドが無い
- `entities/bar.md` — summary が 200 字を超えている

### 陳腐化した内容（N 件）
- `references/paper-x.md` — 出典の更新は 2024-03-10、ページの最終更新は 2024-01-05

### 矛盾（N 件）
- `concepts/scaling.md` は「X」と主張するが、`synthesis/efficiency.md` は「X ではない」と主張する

### index の問題（N 件）
- `concepts/new-page.md` はディスク上にあるが index.md に無い
- 12 件のエントリがページの `summary:` の逐語ではない。例: `concepts/scaling.md`（エントリ 245 字 / summary 138 字）

### provenance の問題（N 件）
- `concepts/scaling.md` — AMBIGUOUS > 15%: 主張の 22% が ambiguous（ソースから取り込み直すか synthesis/ へ移す）
- `entities/some-tool.md` — ドリフト: frontmatter は inferred=0.10、再計算値は 0.45
- `concepts/transformers.md` — INFERRED=52% のハブページ（入ってくるリンク 31 本）: ここの誤りは広く伝わる
- `synthesis/speculation.md` — 出典の無い統合: `sources:` フィールドが無く、55% が inferred

### 断片化したタグクラスタ（N 件）
- **#systems** — 7 ページ、cohesion=0.06 ⚠️
- **#databases** — 5 ページ、cohesion=0.10 ⚠️

### タグ過多と形式の崩れたタグ（N ページ / M タグ）
- 27 ページが `visibility/` 以外のタグを 5 個超持つ — タグ 6 個が 26 ページ、7 個が 1 ページ（前回の実行から変化なし）
- `concepts/platform-overview.md` — タグ 7 個
- `skills/test-account-login.md` — タグ 6 個
- `skills/quality-verification-procedure.md` — タグ 6 個
- `skills/admin-panel-patterns.md` — タグ 6 個
- `skills/proxy-app-integration.md` — タグ 6 個
- タグ `my_project` が小文字とハイフンだけでできていない（アンダースコア）— 2 ページにある

### visibility の問題（N 件）
- `entities/user-records.md` — `email:` の値のパターンを含むが `visibility/pii` タグが無い
- `concepts/auth-flow.md` — `visibility/pii` が付いているが `sources:` frontmatter が無い

### misc の昇格候補（N 件）
vault に `misc/*.md` があるときだけ。無ければ節ごと省く。

| ページ | 最上位のプロジェクト | affinity のスコア |
|---|---|---|
| `misc/web-martinfowler-articles-microservices.md` | `obsidian-wiki` | 4 |

### 統合の穴（N 件）
よく共起するのに synthesis ページが無い概念の組:

| 組 | 共起 | 提案するアクション |
|---|---|---|
| [[Caching]] × [[Consistency]] | 5 ページ | `synthesis/` ページを書く |
| [[Testing]] × [[Observability]] | 3 ページ | `synthesis/` ページを書く |

### confidence / lifecycle の問題（N 件）
- 66 ページがルーブリック以前の値 `lifecycle: active` を持つ — `~/.claude/doc/doc_wiki_lifecycle_rubric.md` に従って変換する
- `concepts/foo.md` — `lifecycle` フィールドが無い
- `entities/bar.md` — `lifecycle: stalestate` は許される値の集合に無い
- `concepts/scaling.md` — `base_confidence: 1.4` が範囲 [0.0, 1.0] の外にある
- `project-a/spec.md` — `lifecycle: tested` だが `evidence_at` が無い（Rule 12f）
- `concepts/bar.md` — `lifecycle: sourced`、`lifecycle_evidence: "§3 の実装表"` — その節がもう無い（Rule 12f）
- `concepts/heuristic.md` — `lifecycle: tested` だが本文にコマンドの出力もサンプル数も無い（Rule 12f、ヒューリスティック）
- `synthesis/old-analysis.md` — 陳腐化（evidence_at 2025-10-01、182 日）lifecycle=verified ⚠️ 優先度高
- `concepts/pipeline.md` — 陳腐化（updated 2025-11-15、137 日）lifecycle=index
- `entities/tool-v1.md` — `superseded_by: [[entities/tool-v2]]` だが lifecycle=sourced（archived のはず）
- `concepts/drift-example.md` — base_confidence のドリフト: stored=0.80、recomputed=0.59（delta=0.21）

### 型付きの関係の問題（N 件）
- `concepts/foo.md` — relationships[1]: 型 "contradication" は許される型に無い（"contradicts" のことか？）
- `concepts/bar.md` — relationships[0]: target "[[skills/nonexistent-skill]]" は vault のどのページにも解決しない
- `entities/baz.md` — relationships[2]: 自己参照（target がこのページ自身の id に解決する）
```

タグ過多の未処理分と、旧値の lifecycle の指摘は件数で報告し、ページごとに 1 件ずつ
報告しない —— 規則は SKILL.md にある（Check 8a と Rule 12a）。上の見本の行が
その形を示している。
