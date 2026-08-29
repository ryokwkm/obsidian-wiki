# wiki バンドルのサードパーティ由来物

このバンドルには、外部 OSS の**アルゴリズムを参照して書き直した**手順書とスクリプトが
含まれる。原著のコードは複製していない。出典とライセンスを記録する。

ライセンス種別は各リポジトリから実際に取得して確認した（**確認日: 2026-08-05**）。

---

## 1. Ar9av/obsidian-wiki — MIT

- 出典: https://github.com/Ar9av/obsidian-wiki
- ライセンス: MIT（`Copyright (c) 2026 Ar9av`）— https://github.com/Ar9av/obsidian-wiki/blob/main/LICENSE
- このバンドルはこのリポジトリの skill 群を 39 → 14 に抜粋した fork が出発点。
- 参照したアルゴリズム:
  - `obsidian_wiki/lint.py` — 二形式のリンク抽出、orphan を「incoming 0 かつ outgoing 0」で
    定義する判定、除外ディレクトリ・予約ページ名の集合、relationship の enum 外を
    fail ではなく warn に落とす 3 段の status 判定
  - `scripts/manifest.py` — 相対キーを絶対パスへ書き換えず保持し、basename + パス末尾一致で
    照合する設計（上流も append モードでの silent re-ingestion を踏んで到達している）
- **移植にあたって直した上流のバグ**（`skills/wiki-lint/scripts/linkgraph.py` に反映済み）:
  - markdown リンクの抽出が `[^)]+\.md[^)]*`（「`.md` を含む」）なので、外部 URL と
    `https://www.mdpi.com/...` のようなドメイン名の中の `.md` を拾う。実 vault で 4 件の
    誤検出を確認した。こちらは `.md` をパス末尾に限定し、スキーム付き URL を除外する
  - 本文リンクの解決が basename 一段で、同名ページが複数あっても黙って先頭を採る。
    実 vault では 110 件が別ページに incoming を付けていた。こちらは複数一致を
    ambiguous として報告する

## 2. breferrari/obsidian-mind — MIT

- 出典: https://github.com/breferrari/obsidian-mind
- ライセンス: MIT（`Copyright (c) 2026 Brenno Ferrari`）— https://github.com/breferrari/obsidian-mind/blob/main/LICENSE
- 参照したアルゴリズム:
  - `.claude/scripts/lib/wikilinks.ts` — コードフェンスと inline code span を抽出の前段で
    落とす行走査（未閉鎖フェンスは EOF まで落とす）、バックティック N 個を「ちょうど N 個」で
    閉じる inline span の扱い、source-relative / path-suffix / basename+alias の 3 経路の解決
  - 設計意図のコメントを一部日本語に訳して引用している
- 上記は TypeScript を移植したものではなく、手順を Python / 自然言語で書き直したもの。
- **意味論を 1 点変えている**: 上流は 3 経路を排他分岐にしているが、こちらは markdown リンク
  （`[x](spec.md)`）を「リンク元ディレクトリ基準の相対パス」として先に解決する。実 vault は
  markdown リンクが主体で、`./` を付けない同ディレクトリ参照が支配的なため。

## 3. anthropics/skills — ⚠️ リポジトリ一括のライセンスは存在しない

**「anthropics/skills は Apache-2.0」と書かないこと。** ルートに LICENSE が無く、GitHub の
License API は 404、リポジトリメタデータの `license` は `null`。ライセンスは
`skills/<name>/LICENSE.txt` に skill 単位で置かれ、3 系統に割れている。

| 系統 | 対象 | 扱い |
|---|---|---|
| Apache-2.0（`Copyright 2026 Anthropic, PBC.`） | `skill-creator` `claude-api` `mcp-builder` ほか 8 件 | 参照可。改変した旨の記載が要る |
| Apache-2.0（APPENDIX 欠落・copyright 行なし） | `frontend-design` | 参照可 |
| **プロプライエタリ（source-available）** | **`docx` `pdf` `pptx` `xlsx`** | **参照・移植しない。** 派生物の作成・複製・リバースエンジニアリングが契約条項として明示的に禁止されている |
| ライセンス表示なし | `doc-coauthoring`・`spec/`・`template/` | 明示許諾が無いので触らない |

このバンドルは公式 skill のコードを持ち込んでいない。参照しているのは
「description に `<` `>` を含めない」「500 行を超えるなら `references/` へ階層化する」という
**書式上の制約の確認**だけで、これは著作物の利用にあたらない。

> ⚠️ 上流調査では「公式が実際にやっている唯一のコード共有は `skills/{docx,pptx,xlsx}/scripts/office/`
> の 50 ファイル 3 重複製」という観察があるが、**その 4 skill こそが持ち込み不可の系統**。
> 観察としては有効でも、そこから何かを写すことはできない。

---

## 表記義務についての整理

**厳密な義務としては、ほぼ生じない。** 著作権はアルゴリズム（解法）に及ばず（日本の
著作権法 10 条 3 項・米 17 U.S.C. §102(b)）、MIT / Apache の表示条件はいずれも複製・頒布に
かかるもので、private リポジトリ内での利用では発動しない。

**それでも書いている理由:**

1. 移植時の設計資料は上流の**正規表現リテラル・定数名・設計意図コメントを逐語で
   引用**している。コメント文は解法ではなく表現なので、引用の要件として出典の明示が要る
2. private は永続しない。公開・切り出し・共有のいずれかで外に出た瞬間に条件が遡って効くが、
   そのとき「誰が何を見て書いたか」は復元できない
3. 「調査した記録」が残る。文面の精密さより、**日付・ライセンス種別・参照範囲**が残っていることに価値がある
