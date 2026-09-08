#!/usr/bin/env bash
# SessionStart フック: 「整えるグループ」（wiki-lint / wiki-dedup）が長く実行されていなければ
# 監査を促し、あわせて派生ビュー（hot.md / index.md）のサイズメーターを出す。
#
# 設計の要（理由・棄却案・実測は vault [[concepts/wiki-kill-switch]] が正典）:
#   - cron でなく「人がいるセッションの入口」で促す（dry-run → 明示確認と無人実行は噛み合わない）
#   - 促すのは読み取り専用の監査モードだけ。修正の適用は促さない
#   - 1 セッションで促すのは最も古い 1 種だけ
#   - state ファイルは持たない（実行 = log.md への追記が、そのまま次の抑制になる）
#
# SessionStart hook 仕様: stdout がそのままコンテキストへ注入され、exit 0 以外は non-blocking
# error になる。**0 以外を返す経路を作らない**（set -e を使わないのも同じ理由）。
set -uo pipefail

# ⚠️ この hook の作用先を配布元から列挙できない —— `OBSIDIAN_VAULT_PATH` は環境側が決める。
# wiki フラグは user スコープで ON なので、vault を持たないセッションでも起動する。
VAULT="${OBSIDIAN_VAULT_PATH:-}"

[ -n "$VAULT" ] || exit 0
[ -d "$VAULT" ] || exit 0

LOG="$VAULT/log.md"

# 置換文字列を変数に入れるのは、`/~}` と直書きすると環境によってバックスラッシュが残る／
# チルダ展開が走るのどちらかを踏むため。
TILDE='~'
label() { printf '%s' "${1/#$HOME/$TILDE}"; }

# 十進の整数だけを受け取る。`10#` が要るのは `08…` を bash が八進数と解釈して落ちるため。
# **19 桁以上も 0 へ**（`$((10#…))` は int64 を溢れると黙って wrap し、偽の小さな上限や
# 負値の丸めになる）。**メーターや上限が hook を壊す側になってはいけない。**
dec() {
    case "${1:-}" in
        ''|*[!0-9]*) printf 0 ;;
        *) if [ "${#1}" -gt 18 ]; then printf 0; else printf '%d' "$((10#$1))"; fi ;;
    esac
}

# バイト数を kB（1000 B 刻み・小数 1 桁）へ。100 B 刻みで丸めるので、**上限を 100 の倍数にすると
# 「75.0kB（上限 75.0kB）— 超過」という自己矛盾した行が出る**（超過は下で実バイトも併記する）。
kb() {
    local b t
    b="$(dec "${1:-0}")"
    t=$(( (b + 50) / 100 ))
    printf '%d.%dkB' $(( t / 10 )) $(( t % 10 ))
}

# 上限がファイルごとに別 env なのは成長法則が違うため（rewrite 定数の hot と、ページ数に線形な
# index を 1 個の値では縛れない）。⚠️ この env を「hot.md を生成する案」の生成予算に流用しないこと。
HOT_MAX="$(dec "${WIKI_HOT_MAX_BYTES:-0}")"
IDX_MAX="$(dec "${WIKI_INDEX_MAX_BYTES:-0}")"

# **促しの有無に関わらず毎セッション 1 行出す**（この節だけが後段の early exit より前にある）。
# 膨張は始まった日に見えなければ止められない。測るのは hot.md と index.md だけ（log.md は
# 追記型で純増が設計どおり、`.manifest.json` は機械生成物）。
if [ -f "$VAULT/hot.md" ] || [ -f "$VAULT/index.md" ]; then
    METER=''
    OVER=''
    for f in hot.md index.md; do
        case "$f" in
            hot.md)   lim="$HOT_MAX" ;;
            index.md) lim="$IDX_MAX" ;;
            *)        lim=0 ;;
        esac
        # **「無い」「空」「読めない」も名指しする** —— `wc -c` は読めないファイルに対して stderr へ
        # だけ書いて 0 を返し、**SessionStart の stderr は誰にも届かない**ので、`0.0kB` として
        # 黙って通ると「増えていない」と誤読される。
        if [ -f "$VAULT/$f" ]; then
            # BSD wc は数値を右寄せして空白を付ける（GNU wc は付けない）ので落とす。
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

    # 末尾スラッシュは 1 個ではなく全部落とす（`${VAULT%/}` だけでは `…/vault//` で名前が空になる）。
    VNAME="$VAULT"
    while [ "${VNAME%/}" != "$VNAME" ]; do VNAME="${VNAME%/}"; done
    VNAME="${VNAME##*/}"
    [ -n "$VNAME" ] || VNAME="$VAULT"

    # ⚠️ 全角括弧は変数名を終端しない（`"$METER_LINE（"` は `set -u` で落ちる = hook が exit 1）。
    # **日本語が続く位置の変数は必ずブレースで囲む。**
    METER_LINE="_wiki 派生ビュー（${VNAME}・自動注入）: $METER"
    [ -n "$OVER" ] && METER_LINE="${METER_LINE} — 超過: ${OVER}"
    echo "${METER_LINE}_"

    if [ -n "$OVER" ]; then
        echo
        echo "⚠️ **天井を上げるのではなく、増えた節を特定して書き手（skill）を直す。**"
        echo "差分: \`git -C $(label "$VAULT") log -p -- hot.md index.md\`"
        echo "上限の設定: settings.json の env \`WIKI_HOT_MAX_BYTES\` / \`WIKI_INDEX_MAX_BYTES\`（0 で計測のみ）"
    fi
    echo
fi

# log.md の行は `- [<日時>] <EVENT> key=value ...`。**日時の書式が 3 種混在している**ので先頭
# 10 文字 = YYYY-MM-DD だけを取る。イベント名の直後にスペースを要求するのは `LINT` と
# `LINT_CONSOLIDATE` を分けるため、位置を行頭に固定するのは本文中の同語を拾わないため。
# 最大値を `sort` で取るのは、`merge=union` で行順が乱れうるので「最後の行」を最新とみなせないから。
last_date() {
    local ev="$1"
    [ -f "$LOG" ] || return 1
    sed -n "s/^- \[\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)[^]]*\] *${ev} .*/\1/p" "$LOG" \
        | sort -r | head -1 | grep . || return 1
}

# BSD date（macOS）と GNU date（Linux）の両方を試す。
days_since() {
    local d="$1" then now
    then="$(date -j -f '%Y-%m-%d' "$d" '+%s' 2>/dev/null)" \
        || then="$(date -d "$d" '+%s' 2>/dev/null)" \
        || return 1
    now="$(date '+%s')"
    echo $(( (now - then) / 86400 ))
}

# 「最も古い 1 種」を選ぶための保持変数。未実行を閾値超過より優先する（日数は不明だが
# 「一度も実行されていない」が最も古い状態）。
BEST_SCORE=-1   # 0 = 対象なし / 1 = 閾値超過 / 2 = 未実行
BEST_DAYS=0
BEST_SKILL=''
BEST_LABEL=''
BEST_LIMIT=0

consider() {
    local ev="$1" skill="$2" limit="$3" name="$4" d days score

    [ "$limit" -gt 0 ] 2>/dev/null || return 0

    if d="$(last_date "$ev")"; then
        days="$(days_since "$d")" || return 0
        [ "$days" -ge "$limit" ] || return 0
        score=1
    else
        days=0
        score=2
    fi

    if [ "$score" -gt "$BEST_SCORE" ] \
        || { [ "$score" -eq "$BEST_SCORE" ] && [ "$days" -gt "$BEST_DAYS" ]; }; then
        BEST_SCORE="$score"
        BEST_DAYS="$days"
        BEST_SKILL="$skill"
        BEST_LABEL="$name"
        BEST_LIMIT="$limit"
    fi
}

# ⚠️ **`consider` を足すときは、第 2 引数の skill が実在することを必ず確かめる**（配布元の
# wiki 系テストが機械で検査する）。存在しない skill を促すと log にイベントが入らないので
# `score=2`（未実行）のまま毎セッション最優先で出続ける（旧 TAG_AUDIT 分岐がその実例）。
consider LINT  wiki-lint  "${WIKI_LINT_INTERVAL_DAYS:-14}"  '健全性の監査'
consider DEDUP wiki-dedup "${WIKI_DEDUP_INTERVAL_DAYS:-30}" '重複ページの検出'

[ "$BEST_SCORE" -gt 0 ] || exit 0

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
