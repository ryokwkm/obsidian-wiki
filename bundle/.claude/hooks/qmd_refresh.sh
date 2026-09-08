#!/usr/bin/env bash
# SessionStart / SessionEnd フック: qmd の検索インデックスを vault の現状へ追いつかせる。
#
# 解きたい問題: vault の markdown と collection 定義は git で同期されるが、**インデックス DB
# （`~/.cache/qmd/index.sqlite`）だけはマシンローカル**。別環境で蒸留 → こちらで pull すると
# 「ページはあるがインデックスに無い」状態が残り、しかも `wiki-query` は grep 経路へ静かに
# フォールバックするので、**気づけないまま検索の当たりが劣化する**。
#
# 設計の要（理由・実測は vault [[concepts/wiki-kill-switch]] と [[skills/qmd-markdown-search]]）:
#   - update は同期・embed はバックグラウンド（update さえ終われば BM25 は新ページを拾う）
#   - `QMD_WIKI_COLLECTION` に依存しない（あれは検索側の変数。更新対象は常に全 collection）
#   - 実行の痕跡を `~/.cache/qmd/refresh.log` へ必ず 1 行残す（正常系が無言な設計なので、
#     痕跡が無いと「走って何もしなかった」と「そもそも走っていない」を区別できない）
#
# SessionStart hook 仕様: stdout がそのままコンテキストへ注入され、exit 0 以外は non-blocking
# error になる。**0 以外を返す経路を作らない**（set -e を使わないのも同じ理由）。
set -uo pipefail

# `--wait` は人が叩く経路と SessionEnd 用（embed も同期で終わらせ、変更が無くても 1 行出す）。
# `--src=<名前>` はログに残す発火元 —— 変更が無いときの行は全経路で同形なので、これが無いと
# どの入口から走ったか判定できない。
# ⚠️ **未知の引数でエラーにしない**（呼び出し側の書き間違いでセッションの入口を壊さない）。
WAIT=0
SRC=manual
while [ $# -gt 0 ]; do
    case "$1" in
        --wait)   WAIT=1 ;;
        --src=*)  SRC="${1#--src=}" ;;
        *)        : ;;
    esac
    shift
done
# ログの 1 行 1 レコードを壊さないよう、英数と `_-` 以外を落とす。
SRC="${SRC//[^a-zA-Z0-9_-]/}"
[ -n "$SRC" ] || SRC=manual

say() {
    if [ "$WAIT" -eq 1 ]; then
        printf 'qmd: %s\n' "$1"
    else
        printf '_qmd インデックス（自動注入）: %s_\n\n' "$1"
    fi
}

# `QMD_BIN_DIR`（任意 env）を PATH の先頭へ置く —— **hook は非対話・非ログインシェルで走るので
# `.zshrc` の PATH が無い**（先頭の `~` はホームが違う複数マシンへ配れるよう自分で展開する）。
#
# 🔴 **以後は変数やパスでなく素の `qmd` で呼ぶ**。`Bash(qmd *)` の allow も sandbox の
# `excludedCommands` も**コマンド名でマッチし、マッチは変数展開の前に行われる**。`"$QMD" embed`
# と書くと除外が外れてサンドボックス**内**で実行され、GPU が見えず embed が落ちる。
# 壊れるのは AI が検証で叩く経路だけ（hook 経路はサンドボックス外で動く）なので見つけにくい。
if [ -n "${QMD_BIN_DIR:-}" ]; then
    PATH="${QMD_BIN_DIR/#\~/$HOME}:$PATH"
fi
export PATH

# qmd 未導入は異常ではない（wiki skill は grep 経路へ静かに落ちる）。黙って抜ける。
command -v qmd >/dev/null 2>&1 || exit 0

# collection 定義が無ければ対象が無い。bun の起動ぶんを節約して抜ける。
[ -f "$HOME/.config/qmd/index.yml" ] || exit 0

# **`$TMPDIR` ではなく `~/.cache/qmd/` に置く**。hook はサンドボックス外・AI の Bash は内で走り、
# **両者の `$TMPDIR` は別物**なので、TMPDIR だとロックが共有されない。
STATE_DIR="$HOME/.cache/qmd"
LOG="$STATE_DIR/refresh.log"
LASTLOG="$STATE_DIR/refresh-last.log"
LOCK="$STATE_DIR/refresh.lock"
LOCK_STALE_SEC=600

mkdir -p "$STATE_DIR" 2>/dev/null

# **変更が無くても 1 行残す**のが要点（`tail ~/.cache/qmd/refresh.log` が唯一の確認手段）。
# `src=` を末尾に置くのは、既存の読み手が前方の `ok changed=N embed=…` をそのまま拾えるようにするため。
note() { printf '%s %s src=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$1" "$SRC" >>"$LOG" 2>/dev/null; }

# **ロックを持っている間だけ**切る（読んで書き戻す操作は他プロセスの追記を落とす）。
trim_log() {
    local n
    # ⚠️ **存在チェックを省かないこと**。`<` はコマンド実行の前に評価されるので、`2>/dev/null` が
    # 適用される前に bash が「No such file or directory」を stderr へ出す。
    [ -f "$LOG" ] || return 0
    n="$(wc -l <"$LOG" 2>/dev/null)" || return 0
    n="${n// /}"
    case "$n" in ''|*[!0-9]*) return 0 ;; esac
    [ "$n" -gt 400 ] || return 0
    tail -n 200 "$LOG" >"$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null
}

mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null; }

# **複数のセッションが同時に入口を通る**ので、`mkdir` のアトミック性でロックを取り、取れなければ
# 黙って抜ける（他のセッションが同じ仕事をしている ＝ 待つ必要も報告する必要も無い）。
if ! mkdir "$LOCK" 2>/dev/null; then
    lock_at="$(mtime "$LOCK")"
    now="$(date '+%s')"
    # **古いロックは奪う** —— embed をバックグラウンドへ逃がす以上、親が消えて解放されない経路が
    # ある。放置すると二度と更新されず、この hook が解こうとしている状態そのものを作る。
    if [ -n "${lock_at:-}" ] && [ $(( now - lock_at )) -gt "$LOCK_STALE_SEC" ]; then
        rmdir "$LOCK" 2>/dev/null
        mkdir "$LOCK" 2>/dev/null || exit 0
    else
        note 'skip locked'
        [ "$WAIT" -eq 1 ] && say '別のプロセスが更新中のためスキップ'
        exit 0
    fi
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
trim_log

if ! OUT="$(qmd update 2>&1)"; then
    printf '%s\n' "$OUT" >"$LASTLOG"
    note 'fail update'
    say "更新に失敗した（詳細: ${LASTLOG}）。検索は grep 経路で動くので作業は続けてよい"
    exit 0
fi

# 出力は collection ごとに 1 行（`Indexed: 0 new, 1 updated, 91 unchanged, 0 removed`）。
# unchanged は無視して new / updated / removed を全 collection ぶん足す。
CHANGED=0
COUNTS="$(printf '%s\n' "$OUT" \
    | sed -n 's/.*Indexed: \([0-9]*\) new, \([0-9]*\) updated, [0-9]* unchanged, \([0-9]*\) removed.*/\1 \2 \3/p')"
if [ -n "$COUNTS" ]; then
    while read -r n u r; do
        CHANGED=$(( CHANGED + ${n:-0} + ${u:-0} + ${r:-0} ))
    done <<EOF
$COUNTS
EOF
fi

# qmd 自身の指示を第一の根拠にし、**件数を保険に置く** —— 文言は上流の実装都合で変わりうるが、
# 「変更があったのに embed しない」は静かな劣化に直結する。空振りの embed は数秒で終わり害が無い。
NEED_EMBED=0
printf '%s' "$OUT" | grep -q "qmd embed" && NEED_EMBED=1
[ "$CHANGED" -gt 0 ] && NEED_EMBED=1

if [ "$NEED_EMBED" -eq 0 ]; then
    note 'ok changed=0'
    [ "$WAIT" -eq 1 ] && say 'インデックスは最新（変更なし）'
    exit 0
fi

if [ "$WAIT" -eq 1 ]; then
    if qmd embed >"$LASTLOG" 2>&1; then
        note "ok changed=${CHANGED} embed=done"
        say "${CHANGED} 件を再インデックスし、embed まで完了"
    else
        note "warn changed=${CHANGED} embed=failed"
        say "${CHANGED} 件を再インデックスしたが embed に失敗（詳細: ${LASTLOG}）"
    fi
    exit 0
fi

# hook 経路では embed を待たない。**ロックの解放もバックグラウンド側へ渡す**（embed 中に別
# セッションが update を始めると SQLite の書き込みが重なる）。親が先に死んで残っても stale 判定が奪う。
# **バックグラウンド側でも痕跡を残す**（`embed=async` は起動しか意味しない）。関数は別プロセスへ
# 渡らないので printf を直接書く。⚠️ ここでも素の `qmd`（`PATH` は export 済みなので子へ渡る）。
trap - EXIT
PATH="$PATH" LASTLOG="$LASTLOG" LOG="$LOG" LOCK="$LOCK" SRC="$SRC" nohup bash -c '
    if qmd embed >"$LASTLOG" 2>&1; then
        printf "%s embed=done src=%s\n" "$(date -u "+%Y-%m-%dT%H:%M:%SZ")" "$SRC" >>"$LOG" 2>/dev/null
    else
        printf "%s embed=failed src=%s\n" "$(date -u "+%Y-%m-%dT%H:%M:%SZ")" "$SRC" >>"$LOG" 2>/dev/null
    fi
    rmdir "$LOCK" 2>/dev/null
' >/dev/null 2>&1 </dev/null &

note "ok changed=${CHANGED} embed=async"
say "${CHANGED} 件を再インデックス（embed はバックグラウンドで実行中）"
exit 0
