#!/usr/bin/env bash
# SessionStart フック: vault の「整えるグループ」（wiki-lint / wiki-dedup）が長く実行されて
# いなければ監査の実行を促し、あわせて派生ビュー（hot.md / index.md）のサイズメーターを出す。
# 入れる系 skill（wiki-update / wiki-ingest）は vault 全体の保守をしないので、催促が無いと
# 孤立ページ・壊れたリンク・タグゆれが蓄積する。
#
# 設計の要（理由・棄却案・実測の経緯は vault [[concepts/wiki-kill-switch]] が正典）:
#   - cron でなく「人がいるセッションの入口」で促す（dry-run → 明示確認と無人実行は噛み合わない）
#   - 促すのは読み取り専用の監査モードだけ。修正の適用はユーザー判断の領域なので促さない
#   - 1 セッションで促すのは最も古い 1 種だけ（複数出すとセッションが監査だけで終わる）
#   - state ファイルは持たない（棄却済み。実行 = log.md への追記が、そのまま次の抑制になる）
#
# ⚠️ **この hook の作用先を配布元から全部は列挙できない**。`OBSIDIAN_VAULT_PATH` は環境側
# （各プロジェクトの settings・別マシン・別リポジトリの settings.local.json）が決めるので、
# hook は自分がどの vault に対して走るかを事前に知らない。
#
# 閾値は env（`WIKI_*_INTERVAL_DAYS`）で変えられる。`0` を渡すとその種別は無効。
#
# Claude Code の SessionStart hook 仕様: stdout がそのままコンテキストへ注入され、exit 0 以外は
# non-blocking error になる。**0 以外を返す経路を作らない**（set -e を使わないのも同じ理由）。

set -uo pipefail

VAULT="${OBSIDIAN_VAULT_PATH:-}"

# vault を持たないプロジェクトでは何もしない。wiki フラグは user スコープで ON なので、この
# hook は wiki を使わないセッションでも起動する。
[ -n "$VAULT" ] || exit 0
[ -d "$VAULT" ] || exit 0

LOG="$VAULT/log.md"

# 表示用に $HOME を ~ へ畳む。置換文字列を変数に入れるのは、`/~}` と直書きすると環境によって
# バックスラッシュが残る／チルダ展開が走るのどちらかを踏むため（実測）。
TILDE='~'
label() { printf '%s' "${1/#$HOME/$TILDE}"; }

# ---- 派生ビューのサイズメーター ------------------------------------------------

# **促しの有無に関わらず毎セッション 1 行出す**（この節だけが後段の early exit より前にある）。
# 膨張は始まった日に見えなければ止められない —— hot.md が 84 KB まで育つ間、skill が 57 回
# それを読んでいたのに誰も気づかなかったのが動機（経緯・値の導出・実測は vault
# [[concepts/wiki-kill-switch]]。実値は settings.json 側だけに置き、ここには再掲しない）。
#
# 測るのは hot.md と index.md だけ。log.md は追記型で純増が設計どおり（`tail` で読む前提）、
# `.manifest.json` は機械生成物なので、どちらも上限を持つ対象ではない。上限がファイルごとに
# 別 env（`WIKI_HOT_MAX_BYTES` / `WIKI_INDEX_MAX_BYTES`）なのは成長法則が違うため
# （rewrite 定数の hot と、ページ数に線形な index を 1 個の値では縛れない）。
#
# 0・空・非数値・19 桁以上はすべて「上限なし」へ落とす: **メーターや上限が hook を壊す側に
# なってはいけない**。⚠️ この env を「hot.md を log.md から生成する案」の生成予算に流用しない
# こと（ファイルの物理サイズとは単位が違う。生成予算は `WIKI_HOT_BUILD_BYTES` を新設して受ける）。
#
# 超過したファイルは名指しする。黙って超過している方が、膨張そのものより悪い。**同じ理由で
# 「無い」「空」「読めない」も名指しする** —— `wc -c` は読めないファイルに対して stderr へだけ
# 書いて 0 を返し、**SessionStart の stderr は誰にも届かない**ので、`0.0kB` として黙って通ると
# 「増えていない」と誤読される（他セッションの書き込み途中も同じく小さく出る = 偽陰性のみが起きる）。
#
# 超過は丸め値ではなく **実バイトで併記する**。`kb()` は 100 B 刻みで丸めるので、上限を 100 の
# 倍数にすると「75.0kB（上限 75.0kB）— 超過」という自己矛盾した行が出る（実測）。値を変えるときは注意。

# 十進の整数だけを受け取る。`08…` のような先頭 0 付きの値を素で `$(( ))` に渡すと bash が
# 八進数として解釈して「value too great for base」で落ちるので `10#` を付ける
# （`[ 080000 -gt 0 ]` は十進で通るため、test 側のガードだけでは素通りする）。
# 負値・16 進・非数値・空はすべて 0 へ。**19 桁以上も 0 へ**（`$((10#…))` は int64 を溢れると
# 黙って wrap し、`18446744073709552616` は 1000 = 偽の小さな上限で全ファイルが超過、
# `9223372036854775807` は `kb()` の丸めが負値になって表示が壊れる。いずれも実測）。
dec() {
    case "${1:-}" in
        ''|*[!0-9]*) printf 0 ;;
        *) if [ "${#1}" -gt 18 ]; then printf 0; else printf '%d' "$((10#$1))"; fi ;;
    esac
}

# バイト数を kB（1000 B 刻み・小数 1 桁）へ。外部コマンドを呼ばず整数演算だけで四捨五入する
# （`(b+50)/100` の商と余りを 10 で分ける）。
kb() {
    local b t
    b="$(dec "${1:-0}")"
    t=$(( (b + 50) / 100 ))
    printf '%d.%dkB' $(( t / 10 )) $(( t % 10 ))
}

# 比較と表示で基数が食い違わないよう、閾値も同じ関数を通してから使う。
HOT_MAX="$(dec "${WIKI_HOT_MAX_BYTES:-0}")"
IDX_MAX="$(dec "${WIKI_INDEX_MAX_BYTES:-0}")"

# 片方でも存在するときだけ出す（両方無い vault は wiki として初期化されていない）。
if [ -f "$VAULT/hot.md" ] || [ -f "$VAULT/index.md" ]; then
    METER=''
    OVER=''
    for f in hot.md index.md; do
        case "$f" in
            hot.md)   lim="$HOT_MAX" ;;
            index.md) lim="$IDX_MAX" ;;
            *)        lim=0 ;;
        esac
        if [ -f "$VAULT/$f" ]; then
            # BSD wc は数値を右寄せして空白を付ける（`     84744`）ので落とす。GNU wc は付けない。
            # 読めないときは stderr へ書いて非 0 で返るので、`0.0kB` と混ぜず名指しする。
            if ! bytes="$(wc -c < "$VAULT/$f" 2>/dev/null)"; then
                METER="${METER:+$METER / }$f 読めない"
                continue
            fi
            bytes="$(dec "${bytes// /}")"
            if [ "$bytes" -eq 0 ]; then
                METER="${METER:+$METER / }$f 空"
                continue
            fi
            METER="${METER:+$METER / }$f $(kb "$bytes")"
            [ "$lim" -gt 0 ] && METER="${METER}（上限 $(kb "$lim")）"
            if [ "$lim" -gt 0 ] && [ "$bytes" -gt "$lim" ]; then
                OVER="${OVER:+$OVER, }${f}（${bytes} > ${lim} B）"
            fi
        else
            METER="${METER:+$METER / }$f なし"
        fi
    done

    # vault 名は basename を呼ばずパラメータ展開で取る。末尾スラッシュは 1 個ではなく
    # 全部落とす（`${VAULT%/}` だけでは `…/vault//` で名前が空になり `（）` と出る）。
    VNAME="$VAULT"
    while [ "${VNAME%/}" != "$VNAME" ]; do VNAME="${VNAME%/}"; done
    VNAME="${VNAME##*/}"
    [ -n "$VNAME" ] || VNAME="$VAULT"

    # ⚠️ 全角括弧は変数名を終端しない。`"$METER_LINE（"` は `METER_LINE（` という名前を
    # 探して `set -u` で落ちる（= SessionStart hook が exit 1 を返す）。**日本語が続く位置の
    # 変数は必ずブレースで囲む。**
    METER_LINE="_wiki 派生ビュー（${VNAME}・自動注入）: $METER"
    [ -n "$OVER" ] && METER_LINE="${METER_LINE} — 超過: ${OVER}"
    echo "${METER_LINE}_"

    # 超過時だけ「次の一手」を 3 行足す。メーターは長らく**消費者のいないテキスト**だった ——
    # 超過に反応する指示は skill にも CLAUDE.md 断片にも 0 件で（2026-08-05 実測）、根拠は
    # hook 内のコメントにしか無く、それは実行時に AI へ届かない。
    # ⚠️ `consider HOT_REBUILD` のような**存在しない skill へは誘導しない**（Stage 1 で潰した型）。
    # 誘導先は既に存在する資料とコマンドだけに限る。
    if [ -n "$OVER" ]; then
        echo
        echo "⚠️ **天井を上げるのではなく、増えた節を特定して書き手（skill）を直す。**"
        echo "差分: \`git -C $(label "$VAULT") log -p -- hot.md index.md\`"
        echo "上限の設定: settings.json の env \`WIKI_HOT_MAX_BYTES\` / \`WIKI_INDEX_MAX_BYTES\`（0 で計測のみ）"
    fi
    echo
fi

# ---- log.md から最終実行日を読む ----------------------------------------------

# log.md の行は `- [<日時>] <EVENT> key=value ...`。**日時の書式が 3 種混在している**
# （`2026-08-03T07:07:53Z` / `2026-08-01` / `2026-08-02T00:57:00+0900`）ので、先頭 10 文字
# = YYYY-MM-DD だけを取ってどの書式でも読めるようにする。
#
# イベント名の直後にスペースを要求するのは `LINT` と `LINT_CONSOLIDATE` を分けるため。
# また本文中に同じ語が出てくる行（WIKI_UPDATE の note= に "LINT" と書かれた等）を拾わないよう、
# 位置を「行頭の `- [日付…]` の直後」に固定している。
#
# 最大値を取るのは `sort` 経由。log.md は追記型だが `merge=union` で行順が乱れうるので
# 「ファイルの最後の行」を最新とみなせない。ISO 8601 の日付は辞書順 = 時系列順。
last_date() {
    local ev="$1"
    [ -f "$LOG" ] || return 1
    sed -n "s/^- \[\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)[^]]*\] *${ev} .*/\1/p" "$LOG" \
        | sort -r | head -1 | grep . || return 1
}

# YYYY-MM-DD から今日までの経過日数。BSD date（macOS）と GNU date（Linux）の両方を試す。
days_since() {
    local d="$1" then now
    then="$(date -j -f '%Y-%m-%d' "$d" '+%s' 2>/dev/null)" \
        || then="$(date -d "$d" '+%s' 2>/dev/null)" \
        || return 1
    now="$(date '+%s')"
    echo $(( (now - then) / 86400 ))
}

# ---- 種別ごとの判定 ------------------------------------------------------------

# 「最も古い 1 種」を選ぶための保持変数。未実行は経過日数を -1 で表し、比較では最優先にする
# （日数不明だが「一度も実行されていない」は最も古い状態なので）。
BEST_SCORE=-1   # 0 = 対象なし / 1 = 閾値超過 / 2 = 未実行
BEST_DAYS=0
BEST_SKILL=''
BEST_LABEL=''
BEST_LIMIT=0

# $1=イベント名 $2=skill 名 $3=閾値（日・0 で無効） $4=表示名
consider() {
    local ev="$1" skill="$2" limit="$3" name="$4" d days score

    [ "$limit" -gt 0 ] 2>/dev/null || return 0

    if d="$(last_date "$ev")"; then
        days="$(days_since "$d")" || return 0
        [ "$days" -ge "$limit" ] || return 0
        score=1
    else
        # log.md に一度も現れない = 未実行。**未着手の vault は両種ともこの分岐に来る**
        # （2026-08-05 実測）ので、閾値超過と同じに扱う。
        days=0
        score=2
    fi

    # 未実行（2）を閾値超過（1）より優先し、同じ種類なら経過日数が大きい方を採る。
    if [ "$score" -gt "$BEST_SCORE" ] \
        || { [ "$score" -eq "$BEST_SCORE" ] && [ "$days" -gt "$BEST_DAYS" ]; }; then
        BEST_SCORE="$score"
        BEST_DAYS="$days"
        BEST_SKILL="$skill"
        BEST_LABEL="$name"
        BEST_LIMIT="$limit"
    fi
}

consider LINT  wiki-lint  "${WIKI_LINT_INTERVAL_DAYS:-14}"  '健全性の監査'
consider DEDUP wiki-dedup "${WIKI_DEDUP_INTERVAL_DAYS:-30}" '重複ページの検出'

# ⚠️ **`consider` を足すときは、第 2 引数の skill が実在することを必ず確かめる**
# （`tests/test_wiki_skills.sh` が機械で検査する）。存在しない skill を促すと、log にイベントが
# 入らないので `score=2`（未実行）のまま毎セッション最優先で出続ける。旧 TAG_AUDIT 分岐が
# この型の実例（前提ファイル不在で一度も発火せず、2026-08-12 に分岐ごと削除。経緯は vault）。
# タグ規約の正典は `~/.claude/doc/doc_wiki_schema.md`、上限の検査は wiki-lint の Check 8a が持つ。
#
# ⚠️ DEDUP の監査は merge 0 件で終わるのが普通（最頻の判定は layered ＝ 足りないのはマージで
# なく relationships エッジ）。0 件は「催促が無駄」の意味でも「重複が無い」証拠でもない。

[ "$BEST_SCORE" -gt 0 ] || exit 0

# ---- 注入 ---------------------------------------------------------------------

echo "## wiki メンテナンス（自動注入）"
echo
if [ "$BEST_SCORE" -eq 2 ]; then
    echo "\`$(label "$VAULT")\` は **\`${BEST_SKILL}\` が未実行**（${BEST_LABEL}・閾値 ${BEST_LIMIT} 日）。"
else
    echo "\`$(label "$VAULT")\` は **\`${BEST_SKILL}\` を ${BEST_DAYS} 日実行していない**（${BEST_LABEL}・閾値 ${BEST_LIMIT} 日）。"
fi
echo
echo "このセッションで \`/${BEST_SKILL}\` を実行すること。**読み取り専用の監査**なので vault は変わらない。"
echo "検出された問題の修正は促していない —— 適用するかはレポートを見てユーザーが判断する"
echo "（\`wiki-lint --consolidate\` / \`wiki-dedup --merge\` は破壊的なので、勝手に走らせないこと）。"
echo
echo "実行すると \`log.md\` に記録が入り、次は ${BEST_LIMIT} 日後まで促されない。"
echo "他の種別も溜まっている場合は、1 セッションに 1 種ずつ順に出る。"

exit 0
