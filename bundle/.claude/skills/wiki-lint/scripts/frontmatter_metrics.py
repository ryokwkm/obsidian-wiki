#!/usr/bin/env python3
"""frontmatter の数値指標（provenance・base_confidence・tag cohesion・summary の長さと index の逐語）を計算する。

依存は標準ライブラリと同じディレクトリの linkgraph.py だけ。wiki-lint の
Check 3a（Missing Summary）・Check 6（Index Consistency）・Check 7（Provenance Drift）・
Check 8（Fragmented Tag Clusters）・Rule 12e（Confidence drift）が読む数字をここで出す。

  provenance         : 本文の 3 マーカーの比率。分母はマーカー総数（コードフェンス・inline code 内は例なので数えない）
  base_confidence    : `~/.claude/doc/doc_wiki_schema.md` の式。source_id への畳み方とバケットは下の分類規則
  clusters           : 5 ページ以上に付いた tag ごとの n・リンクで結ばれた組の数・cohesion
  summary_over_limit : `summary:` が 200 字を超えるページ
  index              : index.md のエントリのうち、リンク先の `summary:` の逐語でないもの（index.md が無ければ null）

`--fix-confidence` は Rule 12e の drift（|保存値 − 再計算値| > 0.05）がある `base_confidence:` 行だけを
書き換える。本文にも他の frontmatter にも触らない。

なぜスクリプトなのか
--------------------
3 つとも入力で答えが決まる算術で、判断の余地が無い。モデルに数えさせると実装ごとに答えが割れ
（同じページの inferred 比率が 0.07 と 0.43）、base_confidence は vault 全体で式から外れた。
バケットの当てはめだけは判断が混ざるので、既定の規則で決めたうえで `--bucket` で上書きできる。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import linkgraph  # noqa: E402

# `~/.claude/doc/doc_wiki_schema.md` の Source-quality scores 表と同じ値。表を変えたらここも変える。
BUCKET_SCORES = {
    "paper": 1.0,
    "official": 0.9,
    "documentation": 0.85,
    "book": 0.8,
    "repository": 0.75,
    "blog": 0.55,
    "session_transcript": 0.5,
    "forum": 0.4,
    "unknown": 0.4,
    "llm_generated": 0.3,
}

CONFIDENCE_DRIFT = 0.05
PROVENANCE_DRIFT = 0.20
CLUSTER_MIN_PAGES = 5
SUMMARY_MAX_CHARS = 200

MARKERS = ("extracted", "inferred", "ambiguous")
_MARKER_RE = re.compile(r"\^\[(extracted|inferred|ambiguous)\]")
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
_INDEX_ENTRY_RE = re.compile(r"^\s*[-*+]\s+(.+?)\s+—\s+(.*?)\s*$")
_TAG_SUFFIX_RE = re.compile(r"\s*\(\s*#[^()]*\)$")

_PAPER_HOSTS = ("arxiv.org", "doi.org", "aclanthology.org", "openreview.net")
_BLOG_HOSTS = ("qiita.com", "zenn.dev", "medium.com", "note.com", "dev.to", "hatenablog")
_FORUM_HOSTS = ("stackoverflow.com", "stackexchange.com", "news.ycombinator.com", "reddit.com")
_DOC_HOST_PREFIXES = ("docs.", "developer.", "developers.", "learn.")
_EXTENSIONLESS_REPO_FILES = ("Makefile", "Dockerfile", "Justfile", "Rakefile", "Gemfile", "Brewfile")
_WIKI_DIRS = ("concepts/","entities/", "skills/", "references/", "synthesis/", "journal/")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vault", type=Path)
    ap.add_argument("--bucket", action="append", default=[], metavar="SOURCE_ID=BUCKET",
                    help="source_id のバケットを上書きする。複数可")
    ap.add_argument("--fix-confidence", action="store_true", help="drift のある base_confidence: 行を書き換える")
    args = ap.parse_args()

    overrides = {}
    for spec in args.bucket:
        sid, _, bucket = spec.rpartition("=")
        if not sid or bucket not in BUCKET_SCORES:
            ap.error(f"--bucket の形式かバケット名が不正: {spec}（バケット: {', '.join(BUCKET_SCORES)}）")
        overrides[sid] = bucket

    report = analyse(args.vault, overrides=overrides)
    if args.fix_confidence:
        report["fixed"] = fix_confidence(args.vault, report)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


def analyse(vault: Path, *, overrides: dict[str, str] | None = None) -> dict:
    """vault を走査し、ページごとの指標と tag クラスタを返す。"""
    included, _excluded, _unreadable = linkgraph.collect_pages(vault)
    paths = [p["path"] for p in included if p["base"] not in linkgraph.RESERVED_PAGE_STEMS]

    pages: dict[str, dict] = {}
    tags_of: dict[str, list[str]] = {}
    summaries: dict[str, str | None] = {}
    for rel in paths:
        text = (vault / rel).read_text(encoding="utf-8", errors="replace")
        front, body = split_frontmatter(text)
        meta = parse_frontmatter(front)
        tags_of[rel] = meta.get("tags") or []
        summaries[rel] = meta.get("summary")
        pages[rel] = {
            "provenance": provenance_entry(body, meta.get("provenance")),
            "base_confidence": confidence_entry(meta, overrides or {}, vault.resolve().name),
        }

    return {
        "pages": pages,
        "clusters": clusters(vault, tags_of),
        "summary_over_limit": [
            {"page": rel, "chars": len(s)} for rel, s in sorted(summaries.items()) if s and len(s) > SUMMARY_MAX_CHARS
        ],
        "index": index_report(vault, included + _excluded, summaries),
    }


def split_frontmatter(text: str) -> tuple[str, str]:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return "", text
    return m.group(1), text[m.end():]


def parse_frontmatter(front: str) -> dict:
    """ここで要るキーだけを読む最小の YAML 読み。スカラー・折り返し（`>-` 等。行は空白で繋ぐ）・inline/block リスト・1 段の map。"""
    meta: dict = {}
    key = None
    in_block = False
    for line in front.split("\n"):
        top = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if top:
            key, value = top.group(1), top.group(2).strip()
            in_block = value in (">-", ">", "|", "|-")
            if in_block:
                meta[key] = ""
            elif value.startswith("[") and value.endswith("]"):
                meta[key] = [unquote(v) for v in value[1:-1].split(",") if v.strip()]
            elif value:
                meta[key] = unquote(value)
            else:
                meta[key] = None
            continue
        if key is None:
            continue
        if in_block:
            if line.strip():
                meta[key] = f"{meta[key]} {line.strip()}".lstrip()
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item:
            if not isinstance(meta.get(key), list):
                meta[key] = []
            meta[key].append(unquote(item.group(1)))
            continue
        sub = re.match(r"^\s+([A-Za-z_][\w-]*):\s*(.*)$", line)
        if sub:
            if not isinstance(meta.get(key), dict):
                meta[key] = {}
            meta[key][sub.group(1)] = unquote(sub.group(2))
    return meta


def unquote(value: str) -> str:
    value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value



def provenance_entry(body: str, stored) -> dict | None:
    counted = count_provenance(body)
    if counted is None:
        return None
    entry = dict(counted)
    entry["stored"] = None
    entry["drift_flag"] = False
    if isinstance(stored, dict):
        try:
            entry["stored"] = {k: float(stored[k]) for k in MARKERS if k in stored}
        except ValueError:
            entry["stored"] = None
        if entry["stored"]:
            entry["drift_flag"] = any(abs(v - counted[k]) > PROVENANCE_DRIFT for k, v in entry["stored"].items())
    return entry


def count_provenance(body: str) -> dict | None:
    """3 マーカーの出現数から比率を返す。マーカーが 1 つも無ければ None。"""
    counts = dict.fromkeys(MARKERS, 0)
    for m in _MARKER_RE.finditer(linkgraph.strip_code_regions(body)):
        counts[m.group(1)] += 1
    total = sum(counts.values())
    if total == 0:
        return None
    result = {k: round(v / total, 2) for k, v in counts.items()}
    result["n_markers"] = total
    return result


def index_report(vault: Path, pages: list[dict], summaries: dict[str, str | None]) -> dict | None:
    """index.md の各エントリがリンク先ページの `summary:` の逐語か（末尾の `( #tag)` は除いて比べる）。

    リンクが解決しないエントリは数えない（broken / ambiguous は Check 2 / 2a の担当）。
    """
    path = vault / "index.md"
    if not path.is_file():
        return None
    lookup = linkgraph.build_index(pages)
    root = {"dir": ""}
    entries = 0
    not_verbatim = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _INDEX_ENTRY_RE.match(line)
        targets = linkgraph.extract_targets(m.group(1)) if m else []
        if not targets:
            continue
        status, hit = linkgraph.resolve(*targets[0], root, lookup)
        if status != "ok" or hit["path"] not in summaries:
            continue
        entries += 1
        text = _TAG_SUFFIX_RE.sub("", m.group(2))
        summary = summaries[hit["path"]]
        if text != summary:
            not_verbatim.append({
                "page": hit["path"],
                "entry_chars": len(text),
                "summary_chars": None if summary is None else len(summary),
            })
    return {"entries": entries, "entry_not_verbatim": not_verbatim}


def confidence_entry(meta: dict, overrides: dict[str, str], project: str) -> dict | None:
    sources = meta.get("sources")
    stored = meta.get("base_confidence")
    if not sources or stored is None:
        return None
    if isinstance(sources, str):
        sources = [sources]
    classified = classify_sources(sources, overrides=overrides, default_project=project)
    recomputed = base_confidence(classified)
    try:
        stored_f = float(stored)
    except ValueError:
        stored_f = None
    drift = None if stored_f is None else round(stored_f - recomputed, 2)
    return {
        "stored": stored_f,
        "recomputed": recomputed,
        "drift": drift,
        "drift_flag": drift is None or abs(drift) > CONFIDENCE_DRIFT,
        "sources": classified,
    }


def classify_sources(sources: list[str], *, overrides: dict[str, str] | None = None,
                     default_project: str = "local") -> list[dict]:
    """`sources:` の各行を source_id とバケットへ畳む。同じ id は 1 件にまとめ、高い方のバケットを採る。

    リポジトリ内の相対パスは、同じ `sources:` にある `projects/<name>` と同じ出典として数える
    （1 リポジトリ ＝ 1 出典）。無ければ `default_project`（analyse は vault 名を渡す。1 リポジトリ 1 vault なので）。
    """
    overrides = overrides or {}
    project = next((s.split("/", 2)[1] for s in sources if re.match(r"^projects/[^/]+", s.strip())), default_project)
    merged: dict[str, dict] = {}
    for raw in sources:
        sid, bucket = classify_one(raw.strip(), project)
        bucket = overrides.get(sid, bucket)
        prev = merged.get(sid)
        if prev is None or BUCKET_SCORES[bucket] > BUCKET_SCORES[prev["bucket"]]:
            merged[sid] = {"id": sid, "bucket": bucket, "score": BUCKET_SCORES[bucket]}
    return list(merged.values())


def classify_one(src: str, project: str) -> tuple[str, str]:
    src = src.strip("[]")
    if re.match(r"^https?://", src):
        return classify_url(src)
    if src.startswith("projects/"):
        return f"repo:{src.split('/', 2)[1]}", "repository"
    if src.startswith(("~/", "/")):
        return f"repo:{home_repo(src)}", "repository"
    if src.startswith(_WIKI_DIRS) and src.endswith(".md"):
        return f"wiki:{src}", "llm_generated"
    if re.search(r"session|セッション|会話", src, re.IGNORECASE):
        return src, "session_transcript"
    # `tools/dq (write.go / guard.go)` のように注記付きで書かれることがあるので先頭の語だけで判定する
    head = src.split()[0] if src.split() else ""
    if "/" in head or re.search(r"\.\w+$", head) or head in _EXTENSIONLESS_REPO_FILES:
        return f"repo:{project}", "repository"
    return src, "unknown"


def classify_url(url: str) -> tuple[str, str]:
    u = urlparse(url)
    host = (u.hostname or "").removeprefix("www.")
    segs = [s for s in u.path.split("/") if s]
    if host in _PAPER_HOSTS:
        ident = segs[-1] if segs else ""
        return f"{host}/{ident}", "paper"
    if host == "github.com" and len(segs) >= 2:
        if len(segs) >= 3 and segs[2] in ("issues", "discussions", "pull"):
            return f"github.com/{segs[0]}/{segs[1]}/{segs[2]}", "forum"
        return f"github.com/{segs[0]}/{segs[1]}", "repository"
    first = f"{host}/{segs[0]}" if segs else host
    if host.endswith(".gov") or ".gov." in host:
        return first, "official"
    if any(h in host for h in _FORUM_HOSTS):
        return first, "forum"
    if any(h in host for h in _BLOG_HOSTS):
        return first, "blog"
    if host.startswith(_DOC_HOST_PREFIXES) or "docs" in segs[:2]:
        return first, "documentation"
    return first, "unknown"


def home_repo(path: str) -> str:
    """`~/source/note/tools/llmtpl/x.go` → `tools/llmtpl`。note 直下は 1 段、tools/tpl は 2 段で 1 リポジトリ。

    リポジトリの外（`~/.gitconfig`・`~/.local/...` 等）は手元環境の観察としてまとめて 1 出典にする。
    パスごとに数えると、同じ環境を覗いただけで出典数が増えて式が上振れする。
    """
    parts = [p for p in path.removeprefix("~/").split("/") if p]
    if parts[:2] == ["source", "note"] and len(parts) > 2:
        rest = parts[2:]
        return "/".join(rest[:2]) if rest[0] in ("tools", "tpl") and len(rest) > 1 else rest[0]
    if parts[:1] == ["miidas"] and len(parts) > 1:
        return "/".join(parts[:2])
    return "home"


def base_confidence(classified: list[dict]) -> float:
    """schema の式: min(distinct/3, 1) × 0.5 + 質の平均 × 0.5。"""
    best: dict[str, float] = {}
    for s in classified:
        best[s["id"]] = max(best.get(s["id"], 0.0), BUCKET_SCORES[s["bucket"]])
    if not best:
        return 0.0
    count = min(len(best) / 3, 1.0)
    quality = sum(best.values()) / len(best)
    return round(count * 0.5 + quality * 0.5, 2)


def clusters(vault: Path, tags_of: dict[str, list[str]]) -> dict:
    members: dict[str, set[str]] = defaultdict(set)
    for rel, tags in tags_of.items():
        for t in tags:
            members[t].add(rel)
    big = {t: pages for t, pages in members.items() if len(pages) >= CLUSTER_MIN_PAGES}
    if not big:
        return {}
    linked = {frozenset((e["from"], e["to"])) for e in linkgraph.analyse(vault)["edges"]}
    out = {}
    for tag, pages in sorted(big.items()):
        n = len(pages)
        pairs = sum(1 for a, b in combinations(sorted(pages), 2) if frozenset((a, b)) in linked)
        out[tag] = {"n": n, "linked_pairs": pairs, "cohesion": round(pairs / (n * (n - 1) / 2), 2)}
    return out


def fix_confidence(vault: Path, report: dict) -> list[str]:
    """drift のあるページの `base_confidence:` 行だけを再計算値へ書き換え、書き換えたパスを返す。"""
    changed = []
    for rel, entry in sorted(report["pages"].items()):
        bc = entry["base_confidence"]
        if not bc or not bc["drift_flag"]:
            continue
        path = vault / rel
        text = path.read_text(encoding="utf-8")
        front, body = split_frontmatter(text)
        new_front, n = re.subn(r"^base_confidence:.*$", f"base_confidence: {bc['recomputed']}", front,
                               count=1, flags=re.MULTILINE)
        if n:
            path.write_text(text.replace(front, new_front, 1), encoding="utf-8")
            changed.append(rel)
    return changed


if __name__ == "__main__":
    sys.exit(main())
