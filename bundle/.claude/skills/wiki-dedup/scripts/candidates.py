#!/usr/bin/env python3
"""vault の中で「内容が重なっているページ対」を本文から採点してランキングで返す。

依存は標準ライブラリのみ。出力は上位 N 対の一覧（既定 20）で、閾値では切らない。

なぜタイトルではなく本文なのか
------------------------------
2026-08-13 に 3 vault（168 ページ）で実測した結果、**タイトル文字列の類似は日本語 vault で
「同じ概念か」を測れない**ことが確定した。タイトルが似ている対の上位は、どの vault でも
ほぼ全部が**意図的に並べて置いてあるページ**だった:

  0.833  site-a.example.com ページ別データ取得仕様 || site-b.example.com ページ別データ取得仕様
  0.714  batch-a-scrape / batch-a-update-daily バッチ || batch-b-update-daily バッチ
  0.611  管理側フロント（admin-front-next）の画面構成 || 利用者側フロント（user-front-next）の画面構成

（ページ名は匿名化してあるが構造は実測のまま: 2 サイト・2 バッチ・2 オーディエンスの並行ページ）

逆に、内容が実際に重なっている対はタイトルが似ていない（`速度指数 取得・活用の実装詳細`
と `Speed Index (速度指数)` — 日本語の長題と英語の短題 — は本文 containment 0.552 で 4 位に対し、
タイトル bigram では圏外）。英語 wiki で重複の主因になる表記ゆれ（`RSC` / `React Server
Components`）は、AI が一貫した命名で書く日本語 vault では起きない。起きるのは
**同じ対象を別の切り口で 2 ページに書く**ことで、それは字面ではなく本文にしか現れない。

なぜ閾値ではなくランキングなのか
--------------------------------
同じ式を 3 vault に当てた実測で、上位対のスコアが **0.744 / 0.391 / 0.199** と
4 倍近く割れた。固定閾値はどう置いても片方で 0 件・片方でノイズだらけになる
（現行の HIGH 0.90 は 3 vault すべてで永久に 0 件だった）。上位 N を必ず返す形にすれば
「0 件」が「重複が無い」の意味に化けることが構造的に起きない。

なぜスクリプトなのか
--------------------
168 ページ = 14,028 対の n-gram 集合演算は LLM には実行できない。実際、現行の SKILL.md は
式を書いた直後に「厳密な算術は不要」と自ら無効化しており、誰も式を計算していなかった。
数え上げは判断を要さないので機械が同じ答えを返すべきところ。判定（同じ概念か・統合すべきか）
だけを LLM が担う。

除外は `.wikilintignore` を読む（wiki-lint の linkgraph.py と同じ機構・同じファイル）。
除外しないと候補が使い物にならない: note vault の上位 30 対のうち **13 対（43%）** が
`reports/`（読み物版・README が「削除しない」と明記）と `_source_docs/`（ingest 元の原本）を
含んでいた。どちらも意図的な二重化で、マージしてはいけない。
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from itertools import combinations
from pathlib import Path

# 走査から外すディレクトリ。`_` で始まるディレクトリ（_raw / _archives / _source_docs など）は
# 一律で除外するので、ここに書くのは例外だけ。linkgraph.py と同じ規約。
SKIP_DIRS = frozenset({".obsidian", ".git", ".claude"})
# vault ページではない管理ファイル。
SKIP_NAMES = frozenset({"index.md", "log.md", "hot.md", "_insights.md", "README.md"})

CJK = re.compile(r"[぀-ヿ㐀-䶿一-鿿]")
ASCII_RUN = re.compile(r"[a-z0-9][a-z0-9+#._-]*")
CODE_FENCE = re.compile(r"```.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`]*`")
MD_LINK_TARGET = re.compile(r"\]\([^)]*\)")
WIKILINK_TARGET = re.compile(r"\[\[([^\]|]*)(\|[^\]]*)?\]\]")

# 本文が短すぎるページは containment が跳ねる（stub 同士が 1.0 になる）。
MIN_GRAMS = 40


def load_ignore(vault: Path) -> frozenset[str]:
    """vault ルートの `.wikilintignore` を読む。書式は wiki-lint と共通。"""
    f = vault / ".wikilintignore"
    if not f.is_file():
        return frozenset()
    try:
        # BOM 付きで保存されると先頭行のパターンが黙って無効になる
        text = f.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return frozenset()
    return frozenset(
        ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")
    )


def is_ignored(rel: str, patterns: frozenset[str]) -> bool:
    parts = rel.split("/")
    if any(p in SKIP_DIRS or p.startswith("_") for p in parts[:-1]):
        return True
    if parts[-1] in SKIP_NAMES:
        return True
    for pat in patterns:
        p = pat.rstrip("/")
        if not p:
            continue
        if p in parts[:-1]:
            return True
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p + "/*"):
            return True
    return False


def split_frontmatter(text: str) -> tuple[str, str]:
    """(frontmatter, body) に割る。frontmatter が無ければ ("", text)。"""
    if not text.startswith("---"):
        return "", text
    end = text.find("\n---", 3)
    if end < 0:
        return "", text
    return text[3:end], text[end + 4:]


def parse_frontmatter(fm: str) -> dict:
    """必要なキーだけを拾う軽量パーサ（PyYAML に依存しないため）。

    block scalar（`title: >-` の次行以降）とリスト（`[a, b]` と `- a` の両形）を扱う。
    """
    out: dict = {}
    lines = fm.split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in (">-", ">", "|", "|-"):
            buf = []
            i += 1
            while i < len(lines) and (lines[i].startswith("  ") or not lines[i].strip()):
                buf.append(lines[i].strip())
                i += 1
            out[key] = " ".join(x for x in buf if x)
            continue
        if val.startswith("[") and val.endswith("]"):
            out[key] = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
        elif not val:
            buf, j = [], i + 1
            while j < len(lines) and re.match(r"^\s+-\s", lines[j]):
                buf.append(re.sub(r"^\s+-\s+", "", lines[j]).strip().strip("\"'"))
                j += 1
            if buf:
                out[key] = buf
                i = j
                continue
            out[key] = ""
        else:
            out[key] = val.strip("\"'")
        i += 1
    return out


def relationship_targets(fm: str) -> set[str]:
    """`relationships:` の target に現れるページ slug を集める。

    書式は `- target: "[表示名](../path/to/page.md)"` と `- target: "[[node/id]]"` の両方があり、
    どちらもパス部分だけを見て slug 化する。
    """
    out = set()
    block = re.search(r"^relationships:\s*$(.*?)(?=^\S|\Z)", fm, re.M | re.S)
    if not block:
        return out
    for m in re.finditer(r"target:\s*(.+)$", block.group(1), re.M):
        raw = m.group(1).strip().strip("\"'")
        md = re.search(r"\]\(([^)]+)\)", raw)
        target = md.group(1) if md else raw.strip("[]").split("|")[0]
        target = re.sub(r"\.md$", "", target.strip())
        target = re.sub(r"^(\.\./)+", "", target)
        if target:
            out.add(target.split("/")[-1])
    return out


def grams(body: str, n: int = 3) -> set[str]:
    """本文を n-gram 集合にする。CJK は文字 n-gram、ASCII は語のまま。

    コードブロック・インラインコード・リンクの宛先は落とす（実装断片やパス文字列が
    共通するだけで跳ねるのを防ぐ）。
    """
    s = CODE_FENCE.sub(" ", body.lower())
    s = INLINE_CODE.sub(" ", s)
    s = WIKILINK_TARGET.sub(lambda m: (m.group(2) or "")[1:], s)
    s = MD_LINK_TARGET.sub(" ", s)
    out = {m.group() for m in ASCII_RUN.finditer(s) if len(m.group()) >= 3}
    cjk = "".join(c for c in s if CJK.match(c))
    out.update(cjk[i:i + n] for i in range(len(cjk) - n + 1))
    return out


def collect(vault: Path) -> list[dict]:
    patterns = load_ignore(vault)
    pages = []
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        if is_ignored(rel, patterns):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"warn: {rel} を読めない: {e}", file=sys.stderr)
            continue
        fm_raw, body = split_frontmatter(text)
        fm = parse_frontmatter(fm_raw)
        if "redirects_to" in fm:  # マージ済みのリダイレクト stub
            continue
        node_id = rel[:-3]
        aliases = fm.get("aliases") if isinstance(fm.get("aliases"), list) else []
        tags = fm.get("tags") if isinstance(fm.get("tags"), list) else []
        pages.append({
            "node_id": node_id,
            "slug": node_id.split("/")[-1],
            "title": fm.get("title") or "",
            "aliases": [str(a) for a in aliases],
            "tags": [str(t) for t in tags],
            "category": fm.get("category") or (rel.split("/")[0] if "/" in rel else ""),
            "linked": relationship_targets(fm_raw),
            "grams": grams(body),
            "chars": len(body),
        })
    return pages


def score_pair(a: dict, b: dict) -> dict:
    ga, gb = a["grams"], b["grams"]
    inter = len(ga & gb)
    # containment（小さい方がどれだけ覆われるか）を主指標にする。片方が詳細版で
    # 長い場合に Jaccard だと薄まるが、覆われている側は依然として重複している。
    overlap = inter / min(len(ga), len(gb))
    signals = []
    bonus = 0.0
    lower_a = {a["title"].lower(), *(x.lower() for x in a["aliases"])} - {""}
    lower_b = {b["title"].lower(), *(x.lower() for x in b["aliases"])} - {""}
    if lower_a & lower_b:
        bonus += 0.15
        signals.append("alias-match")
    if a["category"] and a["category"] == b["category"]:
        bonus += 0.05
        signals.append("same-category")
    shared = {t for t in set(a["tags"]) & set(b["tags"]) if not t.startswith("visibility/")}
    if len(shared) >= 3:
        bonus += 0.10
        signals.append(f"tags×{len(shared)}")
    elif len(shared) >= 2:
        bonus += 0.05
        signals.append(f"tags×{len(shared)}")
    return {
        "a": a["node_id"],
        "b": b["node_id"],
        "title_a": a["title"],
        "title_b": b["title"],
        "score": round(min(overlap + bonus, 1.0), 3),
        "overlap": round(overlap, 3),
        "signals": signals,
        # 型付きエッジで既に結ばれている = 書き手が「別ページとして並べる」と決めた証拠。
        "linked": b["slug"] in a["linked"] or a["slug"] in b["linked"],
    }


def analyse(vault: Path, top: int) -> dict:
    pages = collect(vault)
    usable = [p for p in pages if len(p["grams"]) >= MIN_GRAMS]
    skipped = [p["node_id"] for p in pages if len(p["grams"]) < MIN_GRAMS]
    rows = [score_pair(a, b) for a, b in combinations(usable, 2)]
    rows.sort(key=lambda r: -r["score"])
    return {
        "vault": vault.name,
        "pages_scanned": len(pages),
        "pages_compared": len(usable),
        "pages_too_short": skipped,
        "pairs_evaluated": len(rows),
        "candidates": [r for r in rows if not r["linked"]][:top],
        "already_linked": [r for r in rows if r["linked"]][:top],
    }


def render(res: dict) -> str:
    out = [
        f"vault: {res['vault']}  ページ {res['pages_compared']}/{res['pages_scanned']} 本"
        f"（{res['pairs_evaluated']} 対を採点）",
        "",
        f"## 候補（上位 {len(res['candidates'])} 対・スコア降順）",
        "",
    ]
    if not res["candidates"]:
        out.append("（比較できるページが足りない）")
    for i, r in enumerate(res["candidates"], 1):
        sig = " ".join(r["signals"]) or "-"
        out.append(f"{i:2d}. {r['score']:.3f} (overlap {r['overlap']:.3f}, {sig})")
        out.append(f"    A {r['a']} — {r['title_a'][:60]}")
        out.append(f"    B {r['b']} — {r['title_b'][:60]}")
    if res["already_linked"]:
        out += [
            "",
            f"## 既に relationships で結ばれている対（上位 {len(res['already_linked'])}・"
            "書き手が別ページとして並べた記録がある。判定対象外）",
            "",
        ]
        for r in res["already_linked"]:
            out.append(f"  - {r['score']:.3f}  {r['a']}  ||  {r['b']}")
    if res["pages_too_short"]:
        out += ["", f"## 本文が短く比較対象外: {len(res['pages_too_short'])} 本", ""]
        out += [f"  - {p}" for p in res["pages_too_short"]]
    out += [
        "",
        "⚠️ スコアは vault 内の相対順位でしかない（実測で上位対のスコアは vault 間で 4 倍割れる）。",
        "絶対値を閾値にしない。上位から読んで、同じ概念かどうかは本文で判定する。",
    ]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vault", help="vault のルートパス")
    ap.add_argument("--top", type=int, default=20, help="返す候補の数（既定 20）")
    ap.add_argument("--json", action="store_true", help="JSON で返す")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser()
    if not vault.is_dir():
        print(f"error: vault が見つからない: {vault}", file=sys.stderr)
        return 1
    res = analyse(vault, args.top)
    if args.json:
        json.dump(res, sys.stdout, ensure_ascii=False, indent=1)
        print()
    else:
        print(render(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
