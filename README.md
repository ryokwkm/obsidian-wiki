# obsidian-wiki

Claude Code 用の Obsidian wiki skill パック。AI エージェントの作業から得た知識を
Obsidian vault へ蒸留し、検索し、健全に保つための skill 7 本・hook 2 本・規約 doc 2 本。

[Ar9av/obsidian-wiki](https://github.com/Ar9av/obsidian-wiki)（MIT）を出発点に、
実運用で書き直した派生版。skill を 39 本から 7 本へ絞り、上流のリンク解決バグ 2 件を直し、
ページの lifecycle 判定を作り直し、日本語 vault での実測に基づく規約を足してある。

> **English**: A Claude Code skill pack for distilling agent-session knowledge into an
> Obsidian vault — 7 skills, 2 hooks, and 2 canonical docs. A production-hardened rework of
> [Ar9av/obsidian-wiki](https://github.com/Ar9av/obsidian-wiki): 39 skills cut down to 7,
> two upstream link-resolution bugs fixed, a redesigned page-lifecycle rubric, and
> conventions verified against a real Japanese-language vault. Docs are in Japanese —
> they are read by the agent, and the author's agents work in Japanese.

## 中身

```
bundle/                   ここが配布物の本体（llmtpl バンドル。手動コピーもここから）
├── bundle.conf           llmtpl バンドル定義（llmtpl を使わない場合は無視してよい）
└── .claude/
    ├── CLAUDE.md.tmpl        蒸留の規約断片（いつ wiki-update を打つか）
    ├── settings.json.tmpl    env 4 個 + hook 登録 3 個
    ├── doc/
    │   ├── doc_wiki_schema.md            vault 規約の正典（カテゴリ・特殊ファイル・manifest）
    │   └── doc_wiki_lifecycle_rubric.md  ページ lifecycle 判定の唯一の正典
    ├── hooks/
    │   ├── wiki_maintenance.sh   監査の催促 + hot.md/index.md のサイズメーター（SessionStart）
    │   └── qmd_refresh.sh        qmd 索引をマシン間のずれから守る（SessionStart / SessionEnd）
    └── skills/
        ├── wiki-update           プロジェクトの知識を vault へ同期（蒸留の主経路）
        ├── wiki-query            vault を検索して引用付きで答える（qmd → grep フォールバック）
        ├── wiki-ingest           文書・URL・テキストの取り込みと _raw/ からの昇格
        ├── wiki-capture          会話を wiki ノート化（60 秒の QUICK MODE つき）
        ├── wiki-lint             リンク切れ・orphan・陳腐化の監査（--consolidate で修復まで）
        ├── wiki-dedup            同一概念の重複ページ検出とマージ
        └── claude-history-ingest Claude Code の会話履歴から知見を発掘
templates/                vault の初期 seed 一式と qmd collection 定義のサンプル
bin/qmd                   qmd を bun 経路で強制起動するラッパー（任意）
```

`bundle/` の外（README・LICENSE・templates/・bin/）はリポジトリの付属物で、配布されない
（llmtpl はバンドル直下に非ドットのディレクトリを置くことを許さないため、この 2 層になっている）。

## 上流との差分（実測ベース）

- **skill 39 本 → 7 本**（使用実態の調査で 14 本へ → 再設計で 7 本へ）。skill の description は
  使わなくても毎セッション context に載る — 一度に削除した 19 本だけで合計 10,663 字あった
- **上流のリンク抽出バグ修正**: markdown リンクの抽出が「`.md` を含む」判定だったため、
  `https://www.mdpi.com/...` のようにドメイン名へ `.md` を含む外部 URL を誤検出していた
  （実 vault で 4 件）。`.md` をパス末尾に限定し、スキーム付き URL を除外
- **上流のリンク解決バグ修正**: 本文リンクの解決が basename 一段で、同名ページが複数あると
  黙って先頭を採っていた（実 vault で 110 件が別ページに incoming を付けていた）。
  複数一致は ambiguous として報告する
- **lifecycle ルーブリックの再設計**: ページの鮮度・降格・アーカイブ判定を
  `doc_wiki_lifecycle_rubric.md` に一本化
- **派生ビューのサイズメーター**: `hot.md` / `index.md` の肥大を SessionStart で計測し、
  超過したら「天井を上げる」のではなく「書き足した skill を直す」運用を規約化
- 詳細な出典・ライセンス調査は [THIRD_PARTY.md](THIRD_PARTY.md)

## インストール

前提: [Claude Code](https://claude.com/claude-code)。qmd（セマンティック検索）は任意依存で、
無ければ全 skill が grep へ自動フォールバックする。

### 経路 1: 手動コピー

`bundle/.claude/` をそのまま自分の設定へ写す。

```sh
git clone https://github.com/ryokwkm/obsidian-wiki.git
cd obsidian-wiki/bundle

# user スコープ（全プロジェクトで使う場合）
mkdir -p ~/.claude/skills ~/.claude/hooks ~/.claude/doc
cp -R .claude/skills/* ~/.claude/skills/
cp -R .claude/hooks/*  ~/.claude/hooks/
cp .claude/doc/*.md    ~/.claude/doc/
```

残り 2 つは手でマージする:

- `.claude/CLAUDE.md.tmpl` の内容（`{{`〜`}}` のコメントを除く）を `~/.claude/CLAUDE.md` へ追記
- `.claude/settings.json.tmpl` の `env` と `hooks` を `~/.claude/settings.json` へ deep merge

### 経路 2: llmtpl バンドル

[llmtpl](https://github.com/ryokwkm/llmtpl) を使っている場合は、このリポジトリを clone し、
バンドルルート（`llm-tpl/`）の下へ **`bundle/` を** `wiki` の名前で symlink して、conf に 1 行:

```sh
ln -s /path/to/obsidian-wiki/bundle /path/to/llm-tpl/wiki
```

```ini
wiki = true
```

規約・skills・doc・hook 登録が同じフラグから導出され、`wiki = false` で同時に消える
（キルスイッチ）。

## vault の用意

vault は「プロジェクトごとに 1 つ」が原則。`templates/vault/` を seed としてコピーする:

```sh
VAULT=/path/to/your/vault
mkdir -p "$VAULT"/{concepts,entities,skills,references,synthesis,journal,projects,_archives,_raw,_staging}
cp templates/vault/*.md templates/vault/.manifest.json templates/vault/.wikilintignore "$VAULT/"
```

コピー後に seed 内のプレースホルダを置換する:

- `PROJECT_NAME` → プロジェクト名
- `TIMESTAMP` → `date -u +%Y-%m-%dT%H:%M:%SZ` の出力
- `VAULT_PATH` → vault の絶対パス

vault 自体を git 管理する場合は `templates/vault/.gitattributes` もコピーする
（`log.md merge=union` — 追記型ログの衝突を自動解決する）。

## 環境変数

設定は env 経由。プロジェクトの `.claude/settings.json` の `env`、またはシェルへ。

| 変数 | 必須 | 意味 |
|---|---|---|
| `OBSIDIAN_VAULT_PATH` | **必須** | vault の絶対パス。未設定なら hook は黙って抜け、skill は動かない |
| `WIKI_LINT_INTERVAL_DAYS` | 任意（既定 14） | wiki-lint の催促間隔。`0` で無効 |
| `WIKI_DEDUP_INTERVAL_DAYS` | 任意（既定 30） | wiki-dedup の催促間隔。`0` で無効 |
| `WIKI_HOT_MAX_BYTES` | 任意（既定 8192） | `hot.md` のサイズ上限（超過は警告のみ） |
| `WIKI_INDEX_MAX_BYTES` | 任意（既定 0 = 計測のみ） | `index.md` のサイズ上限 |
| `OBSIDIAN_RAW_DIR` | 任意 | `_raw/` の場所を vault 外に置く場合 |
| `QMD_WIKI_COLLECTION` | 任意 | qmd の collection 名（vault ディレクトリ名と一致させる） |
| `QMD_PAPERS_COLLECTION` | 任意 | 論文用 collection 名 |
| `QMD_BIN_DIR` | 任意 | `qmd` 実行ファイルの探索パスを前置する場合 |

## qmd（任意依存）

[qmd](https://github.com/tobi/qmd)（`@tobilu/qmd` + bun）があると `wiki-query` が
セマンティック検索になり、`qmd_refresh.sh` が索引をセッションの出入口で自動更新する。
無くても全機能が grep で動く。

- collection 定義のサンプル: `templates/qmd-index.yml` → `~/.config/qmd/index.yml`
- 同梱ランチャーが node 経路で起動できない環境向けの bun 強制ラッパー: `bin/qmd`

## 設計の要点

- **キルスイッチ**: 規約・skill・hook 登録を 1 フラグから導出する。片付け忘れの
  「規約だけ残って skill が無い」「誰も読まない hook が回り続ける」を構造的に防ぐ
- **派生ビューはキャッシュ**: `hot.md` / `index.md` は捨てて作り直せる。蒸留物の置き場は
  ページ本文だけ。サイズメーターが超過を出したら、天井ではなく書き手を直す
- **複数セッション前提**: vault は同時に触られる。`index.md` / `hot.md` は Edit で該当箇所だけ、
  `.manifest.json` は jq 1 コマンドで読んで即書く（詳細は `doc_wiki_schema.md`）
- **正典は 1 箇所**: vault の構造規約は `doc_wiki_schema.md`、lifecycle 判定は
  `doc_wiki_lifecycle_rubric.md`。skill はそこを参照し、値や規則を再掲しない

## メンテ方針

これは作者が毎日使っている実運用の設定そのもの（このリポジトリが配布元で、作者の環境は
ここを参照している）。運用で直った分のコミットは今後も流れるが、**issue / PR への対応・
後方互換・サポートは約束しない**。自由に fork してほしい（MIT）。

ドキュメント・コメントは日本語のまま公開している。読み手は AI エージェントで、
作者のエージェントは日本語で動くため。

## ライセンス

[MIT](LICENSE)。由来の詳細と上流ライセンスの調査記録は [THIRD_PARTY.md](THIRD_PARTY.md)。
