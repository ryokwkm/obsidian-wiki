#!/usr/bin/env bash
# SessionStart / SessionEnd フック: qmd の検索インデックスを vault の現状へ追いつかせる。
#
# 解きたい問題: vault の markdown と collection 定義は git で同期されるが、**インデックス DB
# （`~/.cache/qmd/index.sqlite`）だけはマシンローカル**。別環境で蒸留 → こちらで pull すると
# 「ページはあるがインデックスに無い」状態が残り、しかも `wiki-query` は qmd が使えないとき
# grep 経路へ静かにフォールバックするので、「検索の当たりがなんとなく悪い」形でしか現れない。
# **気づけないまま劣化する**のが本質。
#
# 設計の要（理由・実測・経緯は vault [[concepts/wiki-kill-switch]] と
# [[skills/qmd-markdown-search]] が正典）:
#   - update は同期・embed はバックグラウンド（update さえ終われば BM25 は新ページを拾う）
#   - `QMD_WIKI_COLLECTION` に依存しない（あれは検索側の変数。更新対象は常に全 collection）
#   - pull との順序は保証しない（先に走っても 1 セッション遅れるだけで、次の入口が拾う）
#   - 実行の痕跡を `~/.cache/qmd/refresh.log` へ必ず 1 行残す（正常系が無言な設計なので、
#     痕跡が無いと「走って何もしなかった」と「そもそも走っていない」を区別できない）
#
# Claude Code の SessionStart hook 仕様: stdout がそのままコンテキストへ注入され、exit 0 以外は
# non-blocking error になる。**0 以外を返す経路を作らない**（set -e を使わないのも同じ理由）。

set -uo pipefail

# `--wait` は人が叩く経路（横断同期コマンド等）と SessionEnd 用。embed も同期で終わらせ、変更が無くても
# 1 行出す（人が待っている場面で無言だと「動いたのか」が分からない）。既定＝SessionStart 経路は
# 逆に、変更が無ければ何も出さない —— セッションの入口を騒がせない。
#
# `--src=<名前>` は**ログに残す発火元**。無くても動く（既定 `manual`）。変更が無いときの行は
# 全経路で `ok changed=0` と同形なので、これが無いと「どの入口から走ったか」を判定できない
# （経緯は vault [[skills/qmd-markdown-search]]）。
WAIT=0
SRC=manual
# ⚠️ **未知の引数でエラーにしない**（この hook は「0 以外を返す経路を作らない」規約。
# 呼び出し側の書き間違いでセッションの入口を壊さないほうが大事）。
while [ $# -gt 0 ]; do
    case "$1" in
        --wait)   WAIT=1 ;;
        --src=*)  SRC="${1#--src=}" ;;
        *)        : ;;
    esac
    shift
done
# ログの 1 行 1 レコードを壊さないよう、英数と `_-` 以外を落とす（空白・改行の混入対策）。
SRC="${SRC//[^a-zA-Z0-9_-]/}"
[ -n "$SRC" ] || SRC=manual

say() {
    if [ "$WAIT" -eq 1 ]; then
        printf 'qmd: %s\n' "$1"
    else
        # SessionStart の stdout は markdown として注入されるので、他の hook（wiki のサイズ
        # メーター）と同じ斜体 1 行の書式に揃える。
        printf '_qmd インデックス（自動注入）: %s_\n\n' "$1"
    fi
}

# ---- qmd の解決 ----------------------------------------------------------------

# **`QMD_BIN_DIR`（任意 env）を PATH の先頭へ置き、以後は素の `qmd` で呼ぶ。**
#
# 前半（`qmd` の置き場を前置できるようにする）の理由: **hook は非対話・非ログインシェルで走るので
# `.zshrc` の PATH が無い**。`~/.bun/bin` のような場所に入れた `qmd` は、これが無いと見つからない
# （先頭の `~` は hook が展開する —— ホームが違う複数マシンへ同じ設定を配れるようにするため）。
#
# 🔴 後半（**変数やパスでコマンド名を書かない**）の理由が重要。`Bash(qmd *)` の allow も sandbox の
# `excludedCommands` も **コマンド名でマッチし、マッチは変数展開の前に行われる**。`"$QMD" embed` と
# 書くと除外が外れてサンドボックス**内**で実行され、GPU が見えず embed が Metal 初期化で落ちる
# （実際に踏んだ。→ vault [[skills/qmd-markdown-search]]）。壊れるのは AI が検証でこのスクリプトを
# 叩く経路だけなのが厄介（hook 経路はサンドボックス外で動いてしまう）。
if [ -n "${QMD_BIN_DIR:-}" ]; then
    PATH="${QMD_BIN_DIR/#\~/$HOME}:$PATH"
fi
export PATH

# qmd が無い環境は「未導入」であって異常ではない（導入は任意で、
# 無ければ wiki skill は grep 経路へ静かに落ちる）。黙って抜ける。
command -v qmd >/dev/null 2>&1 || exit 0

# collection 定義が無ければインデックスすべき対象が無い。bun の起動ぶんを節約して抜ける。
[ -f "$HOME/.config/qmd/index.yml" ] || exit 0

# ---- 実行の痕跡と状態の置き場 --------------------------------------------------

# **`$TMPDIR` ではなく `~/.cache/qmd/` に置く**。hook はサンドボックス外・AI の Bash は内で走り、
# **両者の `$TMPDIR` は別物**（実測）。TMPDIR に置くとロックが共有されず、手動実行と入口の実行が
# 重なりうる。`~/.cache/qmd` なら qmd の DB と同じ場所で、どちらからも書ける。
STATE_DIR="$HOME/.cache/qmd"
LOG="$STATE_DIR/refresh.log"
LASTLOG="$STATE_DIR/refresh-last.log"
LOCK="$STATE_DIR/refresh.lock"
LOCK_STALE_SEC=600

mkdir -p "$STATE_DIR" 2>/dev/null

# **変更が無くても 1 行残す**のがこの関数の要点（`tail ~/.cache/qmd/refresh.log` が唯一の
# 確認手段）。1 行 = 1 レコードで `<UTC> <結果> src=<発火元>`。`src=` を末尾に置くのは、
# 既存の読み手（人の `tail` と `tests/test_qmd_refresh.sh` の部分一致 grep）が前方の
# `ok changed=N embed=…` をそのまま拾えるようにするため。
note() { printf '%s %s src=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$1" "$SRC" >>"$LOG" 2>/dev/null; }

# ログが伸び続けないよう切り詰める。**ロックを持っている間だけ**行う —— 追記は O_APPEND なので
# 短い行なら競合に強いが、読んで書き戻す操作は他プロセスの追記を落とす。毎回は切らない。
trim_log() {
    local n
    # ⚠️ **存在チェックを省かないこと**。`wc -l <"$LOG" 2>/dev/null` はリダイレクトの失敗を
    # 抑えられない —— `<` はコマンド実行の前に評価されるので、`2>/dev/null` が適用される前に
    # bash が「No such file or directory」を stderr へ出す（初回実行で実測）。SessionStart の
    # stderr は誰にも届かないが、`--wait`（人が叩く経路）では人の画面にノイズとして出る。
    [ -f "$LOG" ] || return 0
    n="$(wc -l <"$LOG" 2>/dev/null)" || return 0
    n="${n// /}"
    case "$n" in ''|*[!0-9]*) return 0 ;; esac
    [ "$n" -gt 400 ] || return 0
    tail -n 200 "$LOG" >"$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null
}

# ---- 多重起動の防止 ------------------------------------------------------------

# **複数のセッションが同時に入口を通る**（プロジェクトごとにセッションを開く運用）。SQLite の
# 書き込みを重ねる理由が無いので、`mkdir` のアトミック性でロックを取り、取れなければ黙って
# 抜ける（他のセッションが同じ仕事をしている ＝ 待つ必要も報告する必要も無い）。

mtime() { stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null; }

if ! mkdir "$LOCK" 2>/dev/null; then
    # 前回の実行が殺されるとロックが残る（embed をバックグラウンドへ逃がすので、親が消えても
    # 解放が走らない経路がある）。**古いロックは奪う** —— 放置すると二度と更新されなくなり、
    # この hook が解こうとしている「静かに劣化する」状態そのものを作ってしまう。
    lock_at="$(mtime "$LOCK")"
    now="$(date '+%s')"
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

# ---- update（同期） ------------------------------------------------------------

if ! OUT="$(qmd update 2>&1)"; then
    printf '%s\n' "$OUT" >"$LASTLOG"
    note 'fail update'
    say "更新に失敗した（詳細: ${LASTLOG}）。検索は grep 経路で動くので作業は続けてよい"
    exit 0
fi

# 出力は collection ごとに 1 行:
#   Indexed: 0 new, 1 updated, 91 unchanged, 0 removed
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

# embed の要否は qmd 自身の指示（"Run 'qmd embed' …"）を第一の根拠にし、**件数を保険に置く**
# —— 文言は上流の実装都合で変わりうるが、「変更があったのに embed しない」は静かな劣化に
# 直結するので、どちらか一方でも立てば走らせる。空振りの embed は数秒で終わり、害が無い。
NEED_EMBED=0
printf '%s' "$OUT" | grep -q "qmd embed" && NEED_EMBED=1
[ "$CHANGED" -gt 0 ] && NEED_EMBED=1

if [ "$NEED_EMBED" -eq 0 ]; then
    note 'ok changed=0'
    [ "$WAIT" -eq 1 ] && say 'インデックスは最新（変更なし）'
    exit 0
fi

# ---- embed -------------------------------------------------------------------

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

# hook 経路では embed を待たない。**ロックの解放もバックグラウンド側へ渡す**（embed が
# 走っている間に別セッションが update を始めると SQLite の書き込みが重なるため）。親が先に
# 死んでロックが残っても、次回の stale 判定が奪う。
trap - EXIT
# **バックグラウンド側でも痕跡を残す**（`embed=async` は起動しか意味しないので、完了したのか
# 落ちたのかがここでしか分からない）。関数は別プロセスへ渡らないので `printf` を直接書く。
# ⚠️ **バックグラウンド側でも素の `qmd`**（`PATH` は export 済みなので子へ渡る）。
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
