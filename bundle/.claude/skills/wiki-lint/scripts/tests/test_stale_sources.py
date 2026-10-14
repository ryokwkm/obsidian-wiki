#!/usr/bin/env python3
"""stale_sources.py のテスト。

    python3 llm-tpl/wiki/.claude/skills/wiki-lint/scripts/tests/test_stale_sources.py

相対パスの持ち主の決め方・比べない出典の仕分け・日付だけの `updated` の扱いを固定する。
手で回すと「どのリポジトリからの相対か」が実行ごとに割れ、常時更新のファイルが毎回鳴った箇所。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stale_sources as ss  # noqa: E402

COMMIT_AT = "2026-01-10T12:00:00+09:00"


def page(front: str) -> str:
    return f"---\n{front.strip()}\n---\n本文\n"


class StaleSourcesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.repo = self.tmp / "repo"
        for rel in ("a.md", "progress.md", "dir/x.md", "with space.md"):
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / rel).write_text("x\n", encoding="utf-8")
        env = {**os.environ, "GIT_AUTHOR_DATE": COMMIT_AT, "GIT_COMMITTER_DATE": COMMIT_AT}
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.com",
               "-c", "commit.gpgsign=false"]
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "init"], check=True, env=env)
        # 配布 symlink（~/.claude/... → リポジトリ）の形。実体の git 時刻で比べること
        self.link = self.tmp / "link.md"
        self.link.symlink_to(self.repo / "a.md")
        self.spaced = self.repo / "with space.md"
        self.plain = self.tmp / "plain.txt"
        self.plain.write_text("x\n", encoding="utf-8")
        mtime = datetime.fromisoformat("2026-02-01T00:00:00+09:00").timestamp()
        os.utime(self.plain, (mtime, mtime))

    def vault(self, name: str, pages: dict[str, str]) -> Path:
        root = self.tmp / name
        for rel, text in pages.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        (self.tmp / "other").mkdir(exist_ok=True)
        (root / ".manifest.json").write_text(json.dumps({"projects": {
            "proj": {"source_cwd": str(self.repo)}, "other": {"source_cwd": str(self.tmp / "other")}, "nocwd": {},
        }}), encoding="utf-8")
        return root

    def test_compares_with_the_current_commit_time(self):
        rep = ss.analyse(self.vault("v", {
            "concepts/old.md": page("updated: 2026-01-05\nsources:\n  - projects/proj\n  - a.md"),
            "concepts/same-day.md": page("updated: 2026-01-10\nsources: [projects/proj, a.md]"),
            "concepts/bare.md": page("updated: 2026-01-05\nsources:\n  - proj\n  - a.md"),
            "concepts/abs.md": page(f"updated: 2026-01-05\nsources:\n  - {self.link}"),
            "concepts/mtime.md": page(f"updated: 2026-01-05\nsources:\n  - {self.plain}"),
            "concepts/spaced.md": page(f"updated: 2026-01-05\nsources:\n  - {self.spaced}（注記）"),
            # 2 つ目の持ち主のリポジトリにだけあるファイル
            "concepts/two-repos.md": page("updated: 2026-01-05\nsources:\n  - projects/other\n  - projects/proj\n  - a.md"),
            "concepts/no-updated.md": page("sources: [projects/proj, a.md]"),
        }))
        got = {(s["page"], s.get("fallback")) for s in rep["stale"]}
        self.assertEqual(got, {
            ("concepts/old.md", None),
            ("concepts/bare.md", None),
            ("concepts/abs.md", None),
            ("concepts/mtime.md", "mtime"),
            ("concepts/spaced.md", None),
            ("concepts/two-repos.md", None),
        })
        abs_entry = next(s for s in rep["stale"] if s["page"] == "concepts/abs.md")
        self.assertEqual(abs_entry["last_change"], COMMIT_AT)

    def test_sources_that_are_not_compared(self):
        rep = ss.analyse(self.vault("v", {
            "concepts/p.md": page(
                "updated: 2026-01-01\nsources:\n"
                "  - projects/proj\n  - progress.md\n  - dir/\n  - gone.md\n"
                "  - https://example.com/a\n  - github.com/owner/repo (README)\n  - session 2026-01-01\n"
                "  - concepts/q.md\n  - _source_docs/2026-01-01-x.md"
            ),
            "concepts/q.md": page("updated: 2026-01-01\nsources:\n  - projects/nocwd\n  - lib/x.sh"),
        }))
        self.assertEqual(rep["stale"], [])
        self.assertEqual({k: v["n"] for k, v in rep["skipped"].items()}, {
            "no_base": 1, "missing": 1, "dir": 1, "living": 1, "wiki": 2, "url_or_text": 3,
        })
        self.assertEqual(rep["skipped"]["no_base"]["examples"], [{"page": "concepts/q.md", "source": "lib/x.sh"}])

    def test_updated_formats_compare_as_the_same_instant(self):
        utc = ss.parse_updated("2026-01-05T01:00:00Z")
        self.assertEqual(utc, ss.parse_updated("2026-01-05T10:00:00+09:00"))
        self.assertIsNotNone(ss.parse_updated("2026-01-05T10:00:00").tzinfo)  # naive はローカル時刻とみなす
        self.assertIsNone(ss.parse_updated("not a date"))

    def test_vault_name_is_the_default_project(self):
        rep = ss.analyse(self.vault("proj", {
            "concepts/a.md": page("updated: 2026-01-05\nsources:\n  - a.md (注記)"),
        }))
        self.assertEqual([s["source"] for s in rep["stale"]], ["a.md (注記)"])

    def test_paths_inside_the_vault_are_pages(self):
        root = self.vault("v", {"concepts/q.md": page("updated: 2026-01-01")})
        rep = ss.analyse(self.vault("v", {
            "concepts/a.md": page(f"updated: 2026-01-01\nsources:\n  - {root / 'concepts/q.md'}"),
        }))
        self.assertEqual(rep["skipped"]["wiki"]["n"], 1)


if __name__ == "__main__":
    unittest.main()
