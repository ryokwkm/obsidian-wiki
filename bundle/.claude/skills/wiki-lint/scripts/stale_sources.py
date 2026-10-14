#!/usr/bin/env python3
"""出典ファイルの今の更新時刻がページの `updated` より新しいページを挙げる（wiki-lint Check 4）。

    python3 stale_sources.py <vault>

時刻は出典の**今の** git の最終コミット（`git log -1 --format=%cI`）。git の外のファイルは mtime で、
`fallback: "mtime"` を付ける。manifest の `modified_at` は取り込んだ時点の値なので使わない。

相対パスの出典は、持ち主のプロジェクトの manifest `projects.<name>.source_cwd` から解決する。持ち主の候補は
同じ `sources:` の `projects/<name>` → manifest のキーと同じ名前だけの行 → vault 名、の順に並べ、
ファイルが実在する最初の候補を採る（複数のリポジトリを引くページがあるため。
frontmatter_metrics.py の classify_sources と同じ規則を、名前だけの行まで広げたもの）。

比べないもの（`skipped` に種類ごとの件数と 3 例）:
  no_base     : 持ち主のプロジェクト（か、その source_cwd）が決まらない相対パス
  missing     : 解決した先にファイルが無い（改名・削除）
  dir         : ディレクトリ（中のどれが変わったかを言えず、ほぼ毎回鳴る）
  living      : 常に更新される管理ファイル（LIVING_FILES）
  wiki        : vault の中のパス（他のページ・`_source_docs/` の凍結した原本）
  url_or_text : URL・会話・その他の文章

依存は標準ライブラリと同じディレクトリの frontmatter_metrics.py / linkgraph.py。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import frontmatter_metrics as fm  # noqa: E402

# 作業のたびに書き足される管理ファイル。出典に挙げたページは、内容が古びていなくても毎回鳴る
LIVING_FILES = ("progress.md", "backlog.md", "ai-context.md")
SKIP_KINDS = ("no_base", "missing", "dir", "living", "wiki", "url_or_text")
EXAMPLES = 3
_HEAD_RE = re.compile(r"\s|（|\(")
# 出典の後ろに付く注記の始まり。空白を含むパス（`/Library/Managed Preferences/…`）を切らないよう、
# 注記と見なすのは全角括弧と「空白 + 半角括弧」だけ
_NOTE_RE = re.compile(r"（|\s\(")
# スキーム無しで書かれた URL（`github.com/owner/repo`）
_HOST_RE = re.compile(r"^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+/")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vault", type=Path)
    args = ap.parse_args()
    json.dump(analyse(args.vault), sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


def analyse(vault: Path) -> dict:
    """vault の全ページの `sources:` を出典の今の更新時刻と比べ、stale と skipped を返す。"""
    vault = vault.resolve()
    cwd_of = source_cwds(vault)
    stale = []
    skipped = {k: {"n": 0, "examples": []} for k in SKIP_KINDS}
    cache: dict[Path, tuple[datetime, bool]] = {}
    for rel, meta, _body in fm.read_pages(vault):
        updated = parse_updated(meta.get("updated"))
        sources = meta.get("sources") or []
        if isinstance(sources, str):
            sources = [sources]
        if updated is None or not sources:
            continue
        owners = owner_projects(sources, cwd_of, vault.name)
        for raw in sources:
            kind, target = locate(raw.strip(), owners, cwd_of, vault)
            if kind is None:
                continue
            if kind != "file":
                bucket = skipped[kind]
                bucket["n"] += 1
                if len(bucket["examples"]) < EXAMPLES:
                    bucket["examples"].append({"page": rel, "source": raw.strip()})
                continue
            if target not in cache:
                cache[target] = last_change(target)
            when, by_mtime = cache[target]
            if when > updated:
                entry = {"page": rel, "source": raw.strip(), "last_change": when.isoformat(),
                         "updated": str(meta.get("updated"))}
                if by_mtime:
                    entry["fallback"] = "mtime"
                stale.append(entry)
    return {"stale": stale, "skipped": skipped}


def source_cwds(vault: Path) -> dict[str, str | None]:
    path = vault / ".manifest.json"
    if not path.is_file():
        return {}
    projects = json.loads(path.read_text(encoding="utf-8")).get("projects") or {}
    return {name: (p or {}).get("source_cwd") for name, p in projects.items()}


def parse_updated(value) -> datetime | None:
    """日付だけならその日の終わり（ローカル時刻）とみなす。同じ日のコミットで鳴らさないため。"""
    if value is None:
        return None
    text = str(value).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return datetime.combine(datetime.fromisoformat(text).date(), time(23, 59, 59)).astimezone()
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.astimezone()


def owner_projects(sources: list[str], cwd_of: dict[str, str | None], vault_name: str) -> list[str]:
    names = [m.group(1) for s in sources if (m := re.match(r"^projects/([^/\s]+)", s.strip()))]
    names += [s.strip() for s in sources if s.strip() in cwd_of]
    if vault_name in cwd_of:
        names.append(vault_name)
    return list(dict.fromkeys(names))


def locate(src: str, owners: list[str], cwd_of: dict[str, str | None], vault: Path) -> tuple[str | None, Path | None]:
    """出典 1 行を (種類, 実体のパス) にする。持ち主の目印の行（`projects/<name>`・名前だけ）は (None, None)。"""
    src = src.strip("[]")
    if src.startswith("projects/") or src in cwd_of:
        return None, None
    if re.match(r"^https?://", src) or _HOST_RE.match(src):
        return "url_or_text", None
    whole = _NOTE_RE.split(src, maxsplit=1)[0].strip()
    head = _HEAD_RE.split(src, maxsplit=1)[0]
    if head.startswith(("~/", "/")):
        candidates = [Path(whole).expanduser(), Path(head).expanduser()]
    else:
        bucket = fm.classify_one(src, "")[1]
        if head.startswith("_source_docs/") or bucket == "llm_generated":
            return "wiki", None
        if bucket != "repository":
            return "url_or_text", None
        bases = [Path(cwd_of[n]).expanduser() for n in owners if cwd_of.get(n)]
        if not bases:
            return "no_base", None
        candidates = [b / c for b in bases for c in (whole, head)]
    path = next((p for p in candidates if p.exists()), candidates[-1])
    if path.resolve().is_relative_to(vault):
        return "wiki", None
    if not path.exists():
        return "missing", None
    if path.is_dir():
        return "dir", None
    if path.name in LIVING_FILES:
        return "living", None
    return "file", path.resolve()


def last_change(path: Path) -> tuple[datetime, bool]:
    """(更新時刻, mtime で代用したか)。git が履歴を持たない（git の外・未追跡）ときは mtime。"""
    out = subprocess.run(
        ["git", "-C", str(path.parent), "log", "-1", "--format=%cI", "--", path.name],
        capture_output=True, text=True,
    )
    if out.returncode == 0 and out.stdout.strip():
        return datetime.fromisoformat(out.stdout.strip()), False
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone(), True


if __name__ == "__main__":
    sys.exit(main())
