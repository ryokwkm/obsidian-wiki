#!/usr/bin/env python3
"""vault のリンクグラフを構築し、orphan / broken / ambiguous を報告する。

依存は標準ライブラリのみ。Obsidian vault のどのページがどのページを指しているかを
決定論的に数え、以下を報告する。

  orphan     : incoming も（解決可能な）outgoing も 0 のページ
  broken     : 指す先が存在しないリンク
  ambiguous  : 同名ページが複数あり、どれを指すか決まらないリンク

`--json` は上記に加えて `pages`（走査した全ページ）・`incoming`・`outgoing`・`edges`
（解決した辺の一覧）を返す。ハブ判定・共起カウント・クラスタ分析はこの `edges` から作る。

⚠️ **`--json` のトップレベルは渡したパスの basename でネストする**（`{"<vault 名>": {"pages": …}}`）。
複数 vault を 1 回で渡せる形にしてあるため、1 本だけ渡してもこの階層は省略されない。
消費側（`wiki-lint` の Check 0）はこの前提で読む。

なぜスクリプトなのか
--------------------
同じ手順書を LLM が実行しても vault によって結果が割れる（2026-08-05 の実測で
一方の vault は orphan 87 件、他方は 5 件と報告され、後者だけが
パス付きリンクを解決していた）。リンクの数え上げは判断を要さない計算なので、
機械が同じ答えを返すべきところ。

出典（アルゴリズムのみ参照。コードは移植していない。詳細は llm-tpl/wiki/THIRD_PARTY.md）
  - Ar9av/obsidian-wiki `obsidian_wiki/lint.py` (MIT) — 二形式のリンク抽出・orphan 判定・除外集合
  - breferrari/obsidian-mind `.claude/scripts/lib/wikilinks.ts` (MIT) — コード領域の除去・リンク解決の経路
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import posixpath
import re
import sys
from collections import defaultdict
from pathlib import Path

# 走査から外すディレクトリ。`_` で始まるディレクトリは（_raw / _archived / _staging /
# _source_docs / _state など）一律で除外するので、ここに書くのは例外だけでよい。
SKIP_DIRS = frozenset({".obsidian", ".git", ".claude"})

# orphan / frontmatter 検査の対象外にするページ。vault の骨格であって知識ページではない。
RESERVED_PAGE_STEMS = frozenset({"index", "log", "hot", "_insights"})

# リンク先がノートでないもの。埋め込み `![[diagram.png]]` を broken と誤報しないため。
ASSET_EXTENSIONS = frozenset(
    "png jpg jpeg gif svg webp pdf canvas base excalidraw html htm mp3 mp4 mov zip".split()
)

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)
_ALIASES_BLOCK_RE = re.compile(r"^aliases:\s*(.*?)$(?:\n(?:[ \t]+.*|)$)*", re.MULTILINE)

# `[[target]]` / `[[target|表示名]]` / `[[target#見出し]]` / 埋め込みの `![[...]]`
_WIKILINK_RE = re.compile(r"!?\[\[([^\[\]\n]+?)\]\]")

# `[表示名](path.md)`。上流 Ar9av の `[^)]+\.md[^)]*` は「.md を含む」判定なので
# `https://www.mdpi.com/...` のドメイン名や外部 URL の .md まで拾う（2026-08-05 に実 vault で
# 4 件の誤検出を確認）。ここでは (1) スキーム付き URL を除き (2) .md をパス末尾に限定する。
_MD_LINK_RE = re.compile(
    r"\[[^\]]*\]\(\s*(?!\w+:)([^)\s]+?\.md)(?:#[^)\s]*)?(?:\s+\"[^\"]*\")?\s*\)"
)

# inline code span。バックティック N 個は「ちょうど N 個」で閉じ、内側には N 未満の run を
# 許す（CommonMark）。末尾の (?!`) が閉じ run の長さを固定する。単純な `[^`]*` に退化させると
# ``code with ` inside`` を取り違える。
_INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1)[^\n])*?\1(?!`)")

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("vault", nargs="+", help="vault のパス（複数可）")
    ap.add_argument("--json", action="store_true", help="JSON で出力する")
    ap.add_argument("--quiet", action="store_true", help="件数だけ出す")
    args = ap.parse_args()

    report = {}
    for raw in args.vault:
        vault = Path(raw).expanduser().resolve()
        if not vault.is_dir():
            print(f"error: vault が見つからない: {vault}", file=sys.stderr)
            return 2
        report[vault.name] = analyse(vault)

    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        print_report(report, quiet=args.quiet)
    return 0


def analyse(vault: Path) -> dict:
    """vault 1 つを解析して findings を返す。"""
    included, excluded, unreadable = collect_pages(vault)
    pages = included + excluded

    by_node: dict[str, list[dict]] = defaultdict(list)
    by_base: dict[str, list[dict]] = defaultdict(list)
    by_alias: dict[str, list[dict]] = defaultdict(list)
    for page in pages:
        by_node[page["node"]].append(page)
        by_base[page["base"]].append(page)
        for alias in page["aliases"]:
            by_alias[alias].append(page)
    index = {"node": by_node, "base": by_base, "alias": by_alias, "pages": pages}

    # incoming は「何ページから参照されているか」。リンク本数と分けるのは、1 ページから
    # 10 回張られたページを「10 ページに依存されているハブ」と誤らせないため。
    incoming_pages: dict[str, set[str]] = defaultdict(set)
    incoming_links: dict[str, int] = defaultdict(int)
    outgoing: dict[str, int] = defaultdict(int)
    edges: list[dict] = []
    broken: list[dict] = []
    ambiguous: list[dict] = []
    to_excluded: list[dict] = []

    for page in included:
        for kind, target in page["targets"]:
            status, hit = resolve(kind, target, page, index)
            if hit is not None and hit["path"] == page["path"]:
                continue  # 自己参照は辺として数えない
            if status == "broken":
                broken.append({"page": page["path"], "target": target})
            elif status == "ambiguous":
                ambiguous.append({"page": page["path"], "target": target})
            elif hit["excluded"]:
                # 走査対象外のディレクトリにある実ファイル。壊れてはいないので broken に
                # 入れないが、グラフの辺でもない（相手がグラフに居ない）。
                to_excluded.append({"page": page["path"], "target": hit["path"]})
            else:
                incoming_pages[hit["path"]].add(page["path"])
                incoming_links[hit["path"]] += 1
                outgoing[page["path"]] += 1
                edges.append({"from": page["path"], "to": hit["path"]})

    # 0 件のページも必ず載せる。「載っていない = 0」を読み手に推測させると、
    # incoming 0 のページを一覧から取り出せない。
    incoming = {p["path"]: len(incoming_pages.get(p["path"], ())) for p in included}
    outgoing_all = {p["path"]: outgoing.get(p["path"], 0) for p in included}

    orphans = [
        p["path"]
        for p in included
        if p["base"] not in RESERVED_PAGE_STEMS
        and incoming[p["path"]] == 0
        and outgoing_all[p["path"]] == 0
    ]

    return {
        "stats": {
            "pages": len(included),
            "links": sum(len(p["targets"]) for p in included),
            "resolved": len(edges),
            "excluded_pages": len(excluded),
            "unreadable": len(unreadable),
        },
        "pages": [p["path"] for p in included],
        "orphans": sorted(orphans),
        "broken": sorted(broken, key=lambda d: (d["page"], d["target"])),
        "ambiguous": sorted(ambiguous, key=lambda d: (d["page"], d["target"])),
        "links_to_excluded": sorted(to_excluded, key=lambda d: (d["page"], d["target"])),
        "unreadable": sorted(unreadable),
        "incoming": dict(sorted(incoming.items(), key=lambda kv: (-kv[1], kv[0]))),
        "incoming_links": {p: incoming_links.get(p, 0) for p in incoming},
        "outgoing": outgoing_all,
        "edges": edges,
    }


def collect_pages(vault: Path) -> tuple[list[dict], list[dict], list[str]]:
    """走査対象・除外対象・読めなかったファイルに分けて返す。

    除外対象も解析はする —— 生きているページからそこへ張られたリンクは実在するので、
    索引に入れておかないと broken として誤報する。
    """
    patterns = read_ignore(vault)
    included: list[dict] = []
    excluded: list[dict] = []
    unreadable: list[str] = []
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault).as_posix()
        if not path.is_file():  # 壊れた symlink
            unreadable.append(rel)
            continue
        try:
            page = parse_page(path, vault)
        except OSError as e:
            unreadable.append(f"{rel} ({e.__class__.__name__})")
            continue
        page["excluded"] = is_excluded(rel, patterns)
        (excluded if page["excluded"] else included).append(page)
    return included, excluded, unreadable


def is_excluded(rel: str, patterns: frozenset[str]) -> bool:
    parts = rel.split("/")
    if any(p in SKIP_DIRS or p.startswith("_") for p in parts[:-1]):
        return True
    for pat in patterns:
        p = pat.rstrip("/")
        if not p:
            continue
        if p in parts[:-1]:  # ディレクトリ名だけの指定
            return True
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p + "/*"):
            return True
    return False


def read_ignore(vault: Path) -> frozenset[str]:
    """vault ルートの `.wikilintignore` を読む。1 行 1 パターン、`#` はコメント。

    ディレクトリ名（`reports`）・パス接頭辞（`reports/`）・glob（`drafts/*.md`）が書ける。
    """
    f = vault / ".wikilintignore"
    if not f.is_file():
        return frozenset()
    try:
        # BOM 付きで保存されると先頭行のパターンが黙って無効になる
        text = f.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return frozenset()
    lines = (ln.strip() for ln in text.splitlines())
    return frozenset(ln for ln in lines if ln and not ln.startswith("#"))


def parse_page(path: Path, vault: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(vault).as_posix()
    return {
        "path": rel,
        "dir": posixpath.dirname(rel),
        "node": slug_path(rel),
        "base": slug(path.stem),
        "aliases": parse_aliases(text),
        "targets": extract_targets(text),
        "excluded": False,
    }


def parse_aliases(text: str) -> list[str]:
    """frontmatter の aliases: を集める。別名で張られたリンクも辺として解決するため。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return []
    out = []
    for block in _ALIASES_BLOCK_RE.finditer(m.group(1)):
        inline = block.group(1).strip()
        if inline.startswith("["):  # aliases: [a, b]
            out += [x.strip().strip("'\"") for x in inline.strip("[]").split(",")]
        elif inline:
            out.append(inline.strip("'\""))
        for line in block.group(0).splitlines()[1:]:  # aliases:\n  - a
            item = line.strip().lstrip("-").strip().strip("'\"")
            if item:
                out.append(item)
    return [slug(a) for a in out if a.strip()]


def extract_targets(text: str) -> list[tuple[str, str]]:
    """本文からリンク先を `(形式, リンク先)` で集める。コード領域は除去済みの本文に対して行う。

    形式を保つのは、2 つの記法で**解決の意味論が違う**ため（resolve を参照）。
    frontmatter は落とさない —— `relationships:` の `target:` は意図された辺であり、
    落とすと typed relationship しか持たないページが orphan に化ける。
    """
    body = strip_code_regions(text)
    targets: list[tuple[str, str]] = []
    for raw in _WIKILINK_RE.findall(body):
        t = raw.replace("\\|", "|").replace("&#124;", "|")
        t = t.split("|")[0].split("#")[0].strip()
        t = t.strip("[]").strip()  # relationships: の "[[target]]" 記法
        if not t or "{{" in t:  # [[#見出し]] / テンプレート変数
            continue
        if t.rsplit(".", 1)[-1].lower() in ASSET_EXTENSIONS:
            continue
        targets.append(("wiki", t))
    for href in _MD_LINK_RE.findall(body):
        t = href.split("#")[0].strip()
        if t:
            targets.append(("md", t))
    return targets


def strip_code_regions(text: str) -> str:
    """コードフェンスと inline code span を落とす。

    SKILL.md や wiki ページはリンク記法の**例**を大量に含む。それらは説明であって辺ではない
    （実測で、ある vault の broken 10 件中 7 件がこれだった）。
    行走査にしているのは、閉じ忘れたフェンスの後ろが漏れるより EOF まで落とす方が安全なため。
    フェンス内の行は空行に置換する（削除しない）—— 報告に出す行番号をずらさないため。
    """
    out: list[str] = []
    marker: str | None = None
    for line in text.split("\n"):
        m = _FENCE_RE.match(line)
        if marker is not None:
            # 閉じるのは同じ文字種で、開いたときと同じ長さ以上のときだけ。長さを 3 に
            # 丸めると ````` で開いたフェンスの中の ``` が閉じ扱いになり、以降が漏れる。
            if m and m.group(1)[0] == marker[0] and len(m.group(1)) >= len(marker):
                marker = None
            out.append("")
            continue
        if m:
            marker = m.group(1)
            out.append("")
            continue
        out.append(_INLINE_CODE_RE.sub("", line))
    return "\n".join(out)


def resolve(kind: str, target: str, source: dict, index: dict) -> tuple[str, dict | None]:
    """リンク先を解決する。**記法によって意味論が違う**ので経路を分ける。

    `[x](spec.md)` は markdown のパスなので、`./` が無くても**リンク元ディレクトリ基準**。
    `[[spec]]` は Obsidian の参照なので、パスでなければ **vault 全体の basename 解決**。
    この 2 つを同一視すると、同名ページが別ディレクトリにある vault で誤る（実測で、
    ある vault の隣接する 2 ディレクトリに同名 3 組があり、
    markdown 側を basename で引くと 63 件が ambiguous、逆に黙って先頭を採ると
    110 件が別ページに incoming を付けていた）。

      md 形式          → リンク元ディレクトリ基準 → vault ルート基準。外れたら broken
      wiki の ./ ../   → リンク元ディレクトリ基準。外れたら broken
      wiki の / を含む → vault ルートからの完全一致 → 末尾一致
      wiki のそれ以外  → basename → alias

    **markdown リンクは basename へ落とさない。** パスが外れているなら壊れているのであって、
    vault のどこかにある同名ファイルを指したかったのだとは限らない。
    末尾一致と basename で複数当たったら ambiguous。黙って先頭を採らない。
    """
    clean = target.replace("\\", "/").strip()
    clean = clean[:-3] if clean.lower().endswith(".md") else clean
    clean = clean.rstrip("/")
    if not clean:
        return ("broken", None)

    relative = clean.startswith("./") or clean.startswith("../")

    if kind == "md" or relative:
        joined = posixpath.normpath(posixpath.join(source["dir"], clean))
        if not joined.startswith(".."):  # vault の外を指していない
            hit = index["node"].get(slug_path(joined), [])
            if hit:
                return pick(hit)
        if relative:
            return ("broken", None)  # 明示的な相対パスが外れたら諦める
        hit = index["node"].get(slug_path(clean), [])  # vault ルート基準として再試行
        return pick(hit) if hit else ("broken", None)

    if "/" in clean:
        key = slug_path(clean)
        hit = index["node"].get(key, [])
        if hit:
            return pick(hit)
        suffix = [p for p in index["pages"] if p["node"].endswith("/" + key)]
        return pick(suffix)

    key = slug(clean)
    return pick(index["base"].get(key) or index["alias"].get(key, []))


def pick(matches: list[dict]) -> tuple[str, dict | None]:
    if not matches:
        return ("broken", None)
    if len(matches) > 1:
        return ("ambiguous", None)
    return ("ok", matches[0])


def slug(text: str) -> str:
    return text.strip().lower().replace(" ", "-")


def slug_path(rel: str) -> str:
    rel = rel[:-3] if rel.lower().endswith(".md") else rel
    return "/".join(slug(p) for p in rel.strip("/").split("/") if p and p != ".")


def print_report(report: dict, *, quiet: bool) -> None:
    for name, r in report.items():
        s = r["stats"]
        print(f"\n=== {name} — {s['pages']} ページ / リンク {s['links']} 件"
              f"（解決 {s['resolved']}）===")
        print(f"  orphan {len(r['orphans'])} / broken {len(r['broken'])}"
              f" / ambiguous {len(r['ambiguous'])}")
        if s["unreadable"]:
            print(f"  ⚠ 読めなかったファイル {s['unreadable']} 件（解析から除外）")
        if quiet:
            continue
        for label, key in (("orphan", "orphans"), ("broken", "broken"),
                           ("ambiguous", "ambiguous"), ("読めない", "unreadable")):
            if not r.get(key):
                continue
            print(f"\n  -- {label} --")
            for item in r[key]:
                if isinstance(item, str):
                    print(f"     {item}")
                else:
                    print(f"     {item['page']}  ->  {item['target']}")


if __name__ == "__main__":
    sys.exit(main())
