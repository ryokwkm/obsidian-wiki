#!/usr/bin/env python3
"""vault の既存ページに付いている tag を「tag<TAB>ページ数」の行で、多い順に出す（wiki-capture の tag 選び）。

    python3 tag_vocabulary.py <vault>

frontmatter の `tags:` を、インライン（`tags: [a, b]`）とブロック（`tags:` の次の行から `- a`）の
両形式で読む。`^tags:` の grep はブロック形式を拾えず、ブロック形式主体の vault で語彙が
94 個中 6 個しか出なかった。`visibility/` は語彙と別管理なので出さない。

走査の除外は wiki-lint・wiki-dedup と同じ規約: `_` で始まるディレクトリ・管理ファイル・
vault ルートの `.wikilintignore`。依存は標準ライブラリのみ。
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from collections import Counter
from pathlib import Path

SKIP_DIRS = frozenset({".obsidian", ".git", ".claude"})
SKIP_NAMES = frozenset({"index.md", "log.md", "hot.md", "_insights.md", "README.md"})
RESERVED_TAG_PREFIX = "visibility/"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vault", type=Path)
    args = ap.parse_args()
    for tag, n in vocabulary(args.vault).items():
        print(f"{tag}\t{n}")
    return 0


def vocabulary(vault: Path) -> dict[str, int]:
    """tag ごとのページ数を、多い順（同数は名前順）で返す。"""
    patterns = load_ignore(vault)
    counts: Counter[str] = Counter()
    for path in vault.rglob("*.md"):
        rel = path.relative_to(vault).as_posix()
        if is_ignored(rel, patterns):
            continue
        tags = page_tags(path.read_text(encoding="utf-8", errors="replace"))
        counts.update({t for t in tags if not t.startswith(RESERVED_TAG_PREFIX)})
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def load_ignore(vault: Path) -> frozenset[str]:
    f = vault / ".wikilintignore"
    if not f.is_file():
        return frozenset()
    # BOM 付きで保存されると先頭行のパターンが黙って無効になる
    text = f.read_text(encoding="utf-8-sig", errors="replace")
    return frozenset(ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#"))


def is_ignored(rel: str, patterns: frozenset[str]) -> bool:
    parts = rel.split("/")
    if any(p in SKIP_DIRS or p.startswith("_") for p in parts[:-1]) or parts[-1] in SKIP_NAMES:
        return True
    for pat in patterns:
        p = pat.rstrip("/")
        if p and (p in parts[:-1] or fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(rel, p + "/*")):
            return True
    return False


def page_tags(text: str) -> list[str]:
    m = re.match(r"\A---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return []
    lines = m.group(1).split("\n")
    for i, line in enumerate(lines):
        head = re.match(r"^tags:\s*(.*)$", line)
        if not head:
            continue
        value = head.group(1).strip()
        if value.startswith("[") and value.endswith("]"):
            return [unquote(v) for v in value[1:-1].split(",") if v.strip()]
        tags = []
        for item in lines[i + 1:]:
            m_item = re.match(r"^\s*-\s+(.*)$", item)
            if not m_item:
                break
            tags.append(unquote(m_item.group(1)))
        return tags
    return []


def unquote(value: str) -> str:
    return value.split(" #", 1)[0].strip().strip("\"'")


if __name__ == "__main__":
    sys.exit(main())
