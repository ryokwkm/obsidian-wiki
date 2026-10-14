#!/usr/bin/env python3
"""tag_vocabulary.py のテスト。

    python3 llm-tpl/wiki/.claude/skills/wiki-capture/scripts/tests/test_tag_vocabulary.py

インライン（`tags: [a, b]`）とブロック（`tags:` の次の行から `- a`）の両形式を読むことを固定する。
`^tags:` の grep ではブロック形式が 0 件になり、ブロック形式主体の vault で語彙が 94 個中 6 個しか出なかった。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tag_vocabulary as tv  # noqa: E402


class TagVocabularyTest(unittest.TestCase):
    def build(self, files: dict[str, str]) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        for rel, text in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(text, encoding="utf-8")
        return root

    def test_reads_both_forms_and_orders_by_page_count(self):
        root = self.build({
            "concepts/a.md": "---\ntitle: A\ntags: [git, \"wiki\"]\n---\n本文\n",
            "concepts/b.md": "---\ntitle: B\ntags:\n  - wiki\n  - visibility/pii\nsummary: x\n---\n- 本文の箇条は tag ではない\n",
            "concepts/c.md": "---\ntitle: C\ntags:\n- wiki\n- wiki\n---\n",
        })
        self.assertEqual(list(tv.vocabulary(root).items()), [("wiki", 3), ("git", 1)])

    def test_skips_reserved_files_and_ignored_paths(self):
        root = self.build({
            "concepts/a.md": "---\ntags: [kept]\n---\n",
            "index.md": "---\ntags: [index-only]\n---\n",
            "_raw/draft.md": "---\ntags: [raw-only]\n---\n",
            "reports/r.md": "---\ntags: [report-only]\n---\n",
            ".wikilintignore": "# 読み物版\nreports/\n",
        })
        self.assertEqual(tv.vocabulary(root), {"kept": 1})


if __name__ == "__main__":
    unittest.main()
