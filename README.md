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
```

`bundle/` の外（README・LICENSE・templates/）はリポジトリの付属物で、配布されない
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

## クイックスタート

上から順に実行すれば動く状態になる。**qmd（意味検索）は任意**で、手順 5 を飛ばしても
全 skill が grep で動く。

前提は [Claude Code](https://claude.com/claude-code) だけ。

### 1. skill パックを置く

llmtpl を使う経路（A）と、ファイルを手で写す経路（B）のどちらか一方を選ぶ。

<details open>
<summary><b>経路 A: llmtpl で入れる（推奨・キルスイッチが効く）</b></summary>

[llmtpl](https://github.com/ryokwkm/llmtpl) はフラグ 1 つで規約・skill・hook 登録をまとめて
出し入れするツール。`wiki = false` にすれば全部消える。

```sh
brew install ryokwkm/tap/llmtpl     # または go install github.com/ryokwkm/llmtpl@latest

git clone https://github.com/ryokwkm/obsidian-wiki.git ~/src/obsidian-wiki

# バンドルルートを作り、この配布物（bundle/）を wiki という名前で置く
mkdir -p ~/llm-tpl
ln -s ~/src/obsidian-wiki/bundle ~/llm-tpl/wiki

# ホームをターゲットにする（llmtpl.conf があるディレクトリがターゲット）
printf 'wiki = true\n' > ~/llmtpl.conf

# 断片の受け口。中身は空でよい（既にある場合は消さずにそのまま使う）
[ -e ~/.claude/CLAUDE.md.tmpl ]    || : > ~/.claude/CLAUDE.md.tmpl
[ -e ~/.claude/settings.json.tmpl ] || printf '{}\n' > ~/.claude/settings.json.tmpl

cd ~ && llmtpl apply
```

**ターゲットがホームなのは、この配布物の中身が `.claude/` で始まるから。** 置いた場所と同じ
相対パスへ着地する規約なので、`~/.claude/skills/` などへ届けるにはホームがターゲットになる。

⚠️ **既に `~/.claude/CLAUDE.md` と `~/.claude/settings.json` を手で書いている場合**は、先に
`.tmpl` へ改名する（`mv ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.tmpl` と settings も同様）。
llmtpl は `.tmpl` を土台に生成物を作り、そこへバンドルの断片を足す。改名せずに `apply` すると
既存ファイルは `.archive/` へ退避されてから置き換わる（消えはしないが、内容は生成物になる）。

バンドルルートをホーム以外に置きたいなら `llmtpl apply --tpl-home <ディレクトリ>` で指せる。

うまくいけばこう出る:

```console
$ cd ~ && llmtpl apply
バンドルルート: /Users/you/llm-tpl（親探索）
▸ you  [ON: wiki]
  ✅ 生成 .claude/CLAUDE.md
  ✅ 生成 .claude/settings.json
  🔗 リンク .claude/doc/doc_wiki_schema.md -> ../../llm-tpl/wiki/.claude/doc/doc_wiki_schema.md
  🔗 リンク .claude/hooks/qmd_refresh.sh -> ../../llm-tpl/wiki/.claude/hooks/qmd_refresh.sh
  🔗 リンク .claude/skills/wiki-update -> ../../llm-tpl/wiki/.claude/skills/wiki-update
  （以下 skill 7 個 + doc 2 本 + hook 2 本）
```

</details>

<details>
<summary><b>経路 B: 手で写す（llmtpl を入れない）</b></summary>

```sh
git clone https://github.com/ryokwkm/obsidian-wiki.git
cd obsidian-wiki/bundle

mkdir -p ~/.claude/skills ~/.claude/hooks ~/.claude/doc
cp -R .claude/skills/* ~/.claude/skills/
cp -R .claude/hooks/*  ~/.claude/hooks/
cp .claude/doc/*.md    ~/.claude/doc/
```

残り 2 つは手でマージする。

**規約**: `.claude/CLAUDE.md.tmpl` の中身をそのまま `~/.claude/CLAUDE.md` の末尾へ追記する
（テンプレート構文は入っていないのでそのまま貼れる）。

**hook 登録と env**: `.claude/settings.json.tmpl` は**先頭に `{{- /* … */}}` のコメントが付いていて
そのままでは JSON として読めない**。1 行目のコメントブロックを削ってから、`env` と `hooks` を
`~/.claude/settings.json` へ手で合成する。`jq` があれば機械的にできる:

```sh
# コメントを除いた JSON を作る
sed '/^{{-/,/\*\/}}/d' .claude/settings.json.tmpl > /tmp/wiki-settings.json

# 既存の settings.json へ深くマージ（無ければ作る）
[ -f ~/.claude/settings.json ] || echo '{}' > ~/.claude/settings.json
jq -s '.[0] * .[1]' ~/.claude/settings.json /tmp/wiki-settings.json > /tmp/merged.json \
  && mv /tmp/merged.json ~/.claude/settings.json
```

⚠️ `jq` の `*` は**同じキーの配列を置き換える**。既に `SessionStart` hook を持っているなら、
上書きされていないか `jq '.hooks' ~/.claude/settings.json` で確かめて、必要なら手で足す。

</details>

### 2. vault を作る

vault は「プロジェクトごとに 1 つ」が原則。`templates/vault/` を seed としてコピーする。

```sh
VAULT=~/vault/my-project          # 好きな場所でよい
REPO=~/src/obsidian-wiki          # clone 先

mkdir -p "$VAULT"/{concepts,entities,skills,references,synthesis,journal,projects,_archives,_raw,_staging}
cp "$REPO"/templates/vault/*.md "$REPO"/templates/vault/.manifest.json \
   "$REPO"/templates/vault/.wikilintignore "$VAULT/"
```

seed にはプレースホルダが入っているので置換する:

```sh
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
for f in "$VAULT"/README.md "$VAULT"/hot.md "$VAULT"/log.md "$VAULT"/.manifest.json; do
  sed -i '' -e "s|PROJECT_NAME|my-project|g" -e "s|TIMESTAMP|$TS|g" \
            -e "s|VAULT_PATH|$VAULT|g" "$f"   # Linux (GNU sed) は -i '' ではなく -i
done
grep -r 'PROJECT_NAME\|TIMESTAMP\|VAULT_PATH' "$VAULT" && echo "!! 置換もれ" || echo "置換 OK"
```

vault 自体を git 管理するなら `templates/vault/.gitattributes` もコピーする
（`log.md merge=union` — 追記型ログの衝突を自動解決する）。

### 3. vault の場所を教える

**ここを飛ばすと何も起きない。** `OBSIDIAN_VAULT_PATH` が未設定だと hook は黙って抜け、
skill も動かない —— エラーも出ないので、設定し忘れに気づけない。

経路 A なら `~/.claude/settings.json.tmpl` の `env` へ足して `apply` し直す。
**`.tmpl` を丸ごと上書きしない** —— 手順 1 で既存の `settings.json` を改名した場合、
そこには自分の設定が入っている。`jq` で 1 キーだけ足す:

```sh
# $VAULT は手順 2 で設定したもの。別のシェルを開いたなら絶対パスを書く
jq --arg v "$VAULT" '.env.OBSIDIAN_VAULT_PATH = $v' ~/.claude/settings.json.tmpl \
  > ~/.claude/settings.json.tmpl.new && mv ~/.claude/settings.json.tmpl{.new,}

cd ~ && llmtpl apply
grep -o 'OBSIDIAN_VAULT_PATH[^,]*' ~/.claude/settings.json     # 生成物に入ったか
```

経路 B なら同じ要領で `~/.claude/settings.json` の `env` へ直接足す（`.tmpl` は無い）。

プロジェクトごとに別の vault を使うなら、ホームではなくそのプロジェクトの
`.claude/settings.json` の `env` に書く。そちらが優先される。

### 4. 動くことを確かめる

```sh
ls ~/.claude/skills | grep wiki           # wiki-* が 6 個 + claude-history-ingest
grep -o 'OBSIDIAN_VAULT_PATH' ~/.claude/settings.json   # 手順 3 が効いているか

# hook を直接叩く（Claude Code の SessionStart と同じもの）
OBSIDIAN_VAULT_PATH="$VAULT" bash ~/.claude/hooks/wiki_maintenance.sh
```

最後のコマンドが**サイズメーターの 1 行と `wiki-lint` の催促を出せば導入できている**:

```
_wiki 派生ビュー（my-project・自動注入）: hot.md 0.1kB（上限 8.2kB） / index.md 0.1kB_

## wiki メンテナンス（自動注入）
`/path/to/vault` は **`wiki-lint` が未実行**（健全性の監査・閾値 14 日）。
```

あとは Claude Code を起動すれば、同じ内容がセッション冒頭に出る。`/wiki-update` で蒸留、
`/wiki-query` で検索が使えるようになる。

### 5.（任意）qmd で意味検索にする

[qmd](https://github.com/tobi/qmd) を入れると `wiki-query` が BM25 + ベクトルのハイブリッド検索に
なり、`qmd_refresh.sh` が索引をセッションの出入口で自動更新する。**入れなくても全機能が
grep で動く。**

```sh
# 1. bun（qmd の実行環境）
curl -fsSL https://bun.sh/install | bash
export PATH="$HOME/.bun/bin:$PATH"          # .zshrc / .bashrc にも書いておく

# 2. qmd 本体
bun install -g @tobilu/qmd                  # npm install -g @tobilu/qmd でも可
qmd --version                               # 2.8 以降であること

# 3. collection 定義（どの vault を索引するか）
mkdir -p ~/.config/qmd
cp "$REPO"/templates/qmd-index.yml ~/.config/qmd/index.yml
```

`~/.config/qmd/index.yml` を開いて 2 箇所を書き換える:

- `my-vault:` → collection 名（**vault のディレクトリ名に合わせる**）
- `path: /path/to/your/vault` → vault の絶対パス

```sh
# 4. 索引を作る
qmd update      # ファイルを読んで BM25 索引を張る（数秒）
qmd embed       # ベクトルを作る
qmd status      # collection と件数が出れば成功
```

⚠️ **初回はモデルのダウンロードが入る。進捗が止まって見えても失敗ではない。**
落ちてくるタイミングが 2 つに分かれる（実測・`~/.cache/qmd/models/` に保存され 2 回目以降は不要）:

| いつ | 何が | サイズ |
|---|---|---|
| 初回の `qmd embed` | 埋め込みモデル | 318MB |
| 初回の `qmd query` | クエリ拡張 + リランカー | 1.2GB + 610MB |

合計で約 2.1GB。`qmd search`（BM25 のみ）はモデルを使わないので、DL を待たずに試せる。

**qmd 2.8 以降を使うこと。** 2.5 系までは `better-sqlite3` 12.x が prebuild を持たず、
`bun install -g` が postinstall をブロックするため、同梱ランチャーの node 経路が
`better_sqlite3.node` 不在で落ちた。2.8 系は `better-sqlite3` 13.x の prebuild を同梱するので
`npm install -g` / `bun install -g` のどちらでも素で動く。

**hook から `qmd` が見つからないとき**は `QMD_BIN_DIR` に置き場（`~/.bun/bin` など）を指定する。
hook は非ログインシェルで走るので `.zshrc` の PATH を持たない。

### 消すとき

経路 A なら `~/llmtpl.conf` を `wiki = false` にして `cd ~ && llmtpl apply`。規約・skill・doc・
hook 登録が同時に消える（キルスイッチ）。経路 B なら手順 1 でコピーしたファイルを消し、
`settings.json` から `hooks` と `env` を手で戻す。

## 環境変数

設定は env 経由。`~/.claude/settings.json` の `env`（全プロジェクト）、またはプロジェクトの
`.claude/settings.json` の `env`（そのプロジェクトだけ）へ書く。

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
| `QMD_BIN_DIR` | 任意 | `qmd` の置き場（`~/.bun/bin` 等）。hook は非ログインシェルで走り `.zshrc` の PATH を持たないので、`qmd` が見つからないときに指定する |

## うまく動かないとき

| 症状 | 原因 | 対処 |
|---|---|---|
| セッション冒頭に何も出ない | `OBSIDIAN_VAULT_PATH` 未設定（hook は黙って抜ける設計） | 手順 3。`bash ~/.claude/hooks/wiki_maintenance.sh` を直接叩いて切り分ける |
| `/wiki-update` が補完に出ない | skill が `~/.claude/skills/` に無い | `ls ~/.claude/skills`。経路 A なら `llmtpl apply` の出力に 🔗 が並んでいるか |
| `apply` が「寄与が着地しなかった」と言う | 受け口の `.tmpl` が無い | `~/.claude/CLAUDE.md.tmpl` と `~/.claude/settings.json.tmpl` を作る（空でよい） |
| `Cannot find module '.../better_sqlite3.node'` | qmd が 2.8 より古い | `bun install -g @tobilu/qmd` で上げる |
| `qmd embed` / `qmd query` が返ってこない（初回） | モデルの DL（合計 約 2.1GB） | そのまま待つ。2 回目以降は不要。急ぐなら `qmd search` は DL 無しで動く |
| hook 経由だと `qmd` が見つからない | 非ログインシェルに `.zshrc` の PATH が無い | `QMD_BIN_DIR` に `~/.bun/bin` を指定 |

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
