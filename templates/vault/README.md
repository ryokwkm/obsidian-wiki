---
title: PROJECT_NAME vault
created: TIMESTAMP
updated: TIMESTAMP
---

# PROJECT_NAME vault

PROJECT_NAME 用の Obsidian wiki vault。AI エージェントが蒸留した知識の永続層。

## ディレクトリ

- `concepts/` — 概念・パターン・原則
- `entities/` — 具体的なツール・サービス・人物などの実体
- `skills/` — 手順・How-To・スキル知識
- `references/` — 外部資料へのリンクとメモ
- `synthesis/` — 複数 concept を横断する考察
- `journal/` — 日付つきの作業ログ
- `projects/` — プロジェクト固有の知識
- `_raw/` — 未整理ドラフトの staging（`wiki-ingest` が本ページへ昇格させる）
- `_staging/` — `WIKI_STAGED_WRITES=true` 時のレビュー待ち
- `_archives/` — rebuild/restore 用の vault スナップショット
- `_source_docs/` — 一次資料。ingest したローカルファイルの原本コピー（`<YYYY-MM-DD>-<元のファイル名>`）。ページの `sources:` はここを指す（元の場所は消える）。検索索引には入れない（蒸留ページと近重複）

## 特殊ファイル

- `index.md` / `hot.md` — 派生ビュー（捨てて作り直せるキャッシュ）
- `log.md` — 追記専用の操作ログ
- `.manifest.json` — 取り込み済みソースと差分計算の状態
- `.wikilintignore` — wiki ページとして扱わないパス

規約の正典は配布元リポジトリの `.claude/doc/doc_wiki_schema.md`。
