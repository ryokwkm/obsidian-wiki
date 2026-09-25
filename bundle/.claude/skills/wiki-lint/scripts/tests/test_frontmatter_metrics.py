#!/usr/bin/env python3
"""frontmatter_metrics.py のテスト。

    python3 llm-tpl/wiki/.claude/skills/wiki-lint/scripts/tests/test_frontmatter_metrics.py

provenance の分母・source_id の畳み方・base_confidence の式・cohesion の分母を固定する。
どれも手で数えると実装ごとに答えが割れた箇所なので、境界をテストで縛る。
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import frontmatter_metrics as fm  # noqa: E402


def page(front: str, body: str = "") -> str:
    return f"---\n{front.strip()}\n---\n{body}"


class VaultCase(unittest.TestCase):
    def build(self, files: dict[str, str]) -> Path:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        for rel, text in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        return root


class ProvenanceTest(unittest.TestCase):
    def test_denominator_is_marker_total(self):
        body = (
            "# 見出しは数えない\n\n"
            "- a ^[extracted]\n- b ^[extracted]\n- c ^[inferred]\n- d ^[ambiguous]\n"
            "無印の散文は分母に入らない。\n"
        )
        got = fm.count_provenance(body)
        self.assertEqual(got["n_markers"], 4)
        self.assertEqual((got["extracted"], got["inferred"], got["ambiguous"]), (0.5, 0.25, 0.25))

    def test_markers_in_code_are_examples_not_claims(self):
        body = "- real ^[inferred]\n\n```markdown\n- x ^[extracted]\n```\n\n`^[extracted]` の書き方\n"
        got = fm.count_provenance(body)
        self.assertEqual(got["n_markers"], 1)
        self.assertEqual(got["inferred"], 1.0)

    def test_no_markers_returns_none(self):
        self.assertIsNone(fm.count_provenance("本文だけ\n"))


class SourceIdTest(unittest.TestCase):
    def ids(self, sources: list[str]) -> dict[str, str]:
        return {s["id"]: s["bucket"] for s in fm.classify_sources(sources)}

    def test_one_repository_is_one_source(self):
        got = self.ids(["projects/ai-settings", "lib/sync.sh", ".claude/doc/x.md", "progress.md"])
        self.assertEqual(got, {"repo:ai-settings": "repository"})

    def test_relative_paths_without_project_fold_to_local(self):
        self.assertEqual(self.ids(["lib/a.sh", "README.md"]), {"repo:local": "repository"})

    def test_default_project_is_used_for_relative_paths(self):
        got = fm.classify_sources(["lib/a.sh", "tools/dq (write.go / guard.go)"], default_project="ai-settings")
        self.assertEqual([(s["id"], s["bucket"]) for s in got], [("repo:ai-settings", "repository")])

    def test_home_paths_fold_per_repository(self):
        got = self.ids(["~/source/note/tools/llmtpl", "~/source/note/tools/llmtpl/main.go"])
        self.assertEqual(got, {"repo:tools/llmtpl": "repository"})

    def test_paths_outside_repositories_are_one_source(self):
        got = self.ids(["~/.gitconfig", "~/.local/share/x", "/etc/hosts"])
        self.assertEqual(got, {"repo:home": "repository"})

    def test_urls(self):
        got = self.ids([
            "https://arxiv.org/abs/1802.06997",
            "https://github.com/charmbracelet/vhs",
            "https://github.com/charmbracelet/vhs/blob/main/README.md",
            "https://qiita.com/someone/items/abc",
            "https://stackoverflow.com/questions/1",
            "https://example.com/post",
        ])
        self.assertEqual(got, {
            "arxiv.org/1802.06997": "paper",
            "github.com/charmbracelet/vhs": "repository",
            "qiita.com/someone": "blog",
            "stackoverflow.com/questions": "forum",
            "example.com/post": "unknown",
        })

    def test_wiki_pages_are_llm_generated(self):
        self.assertEqual(self.ids(["entities/調査.md"]), {"wiki:entities/調査.md": "llm_generated"})

    def test_session_text_is_transcript(self):
        got = self.ids(["Claude Code システムプロンプト（2026-09-06 のセッションで観測）"])
        self.assertEqual(list(got.values()), ["session_transcript"])

    def test_override_wins(self):
        got = fm.classify_sources(["https://example.com/post"], overrides={"example.com/post": "official"})
        self.assertEqual(got[0]["bucket"], "official")


class ConfidenceTest(unittest.TestCase):
    def test_single_repository(self):
        # 出典 1 本 = 0.167、repository 0.75 → 0.375。合計 0.54（progress.md ② の 0.542）
        self.assertEqual(fm.base_confidence([{"id": "repo:x", "bucket": "repository"}]), 0.54)

    def test_count_saturates_at_three(self):
        srcs = [{"id": f"p{i}", "bucket": "paper"} for i in range(5)]
        self.assertEqual(fm.base_confidence(srcs), 1.0)

    def test_duplicate_id_takes_highest_bucket(self):
        srcs = [{"id": "a", "bucket": "unknown"}, {"id": "a", "bucket": "paper"}]
        self.assertEqual(fm.base_confidence(srcs), round(1 / 3 * 0.5 + 1.0 * 0.5, 2))


class VaultReportTest(VaultCase):
    def test_drift_and_fix(self):
        root = self.build({
            "concepts/a.md": page(
                "title: A\nbase_confidence: 0.85\nsources:\n  - projects/ai-settings\n  - lib/x.sh\n"
                "provenance:\n  extracted: 0.9\n  inferred: 0.1\n  ambiguous: 0.0",
                "- x ^[extracted]\n- y ^[inferred]\n",
            ),
            "concepts/b.md": page("title: B\nbase_confidence: 0.54\nsources: [projects/ai-settings]"),
            "concepts/nosrc.md": page("title: N\nbase_confidence: 0.9"),
        })
        rep = fm.analyse(root)
        a = rep["pages"]["concepts/a.md"]
        self.assertEqual(a["base_confidence"]["recomputed"], 0.54)
        self.assertTrue(a["base_confidence"]["drift_flag"])
        self.assertTrue(a["provenance"]["drift_flag"])  # 0.9 vs 0.5 は 0.20 超
        self.assertFalse(rep["pages"]["concepts/b.md"]["base_confidence"]["drift_flag"])
        self.assertIsNone(rep["pages"]["concepts/nosrc.md"]["base_confidence"])

        changed = fm.fix_confidence(root, rep)
        self.assertEqual(changed, ["concepts/a.md"])
        text = (root / "concepts/a.md").read_text(encoding="utf-8")
        self.assertIn("base_confidence: 0.54\n", text)
        self.assertIn("- x ^[extracted]", text)  # 本文は触らない

    def test_cohesion_counts_linked_pairs(self):
        files = {}
        for i in range(5):
            links = "[[p1]]" if i == 0 else ""
            files[f"concepts/p{i}.md"] = page(f"title: P{i}\ntags:\n  - t", links)
        files["concepts/p1.md"] = page("title: P1\ntags:\n  - t", "[[p0]] [[p0]]")
        rep = fm.analyse(self.build(files))
        t = rep["clusters"]["t"]
        # p0↔p1 は両方向でも 1 組。10 組中 1 組
        self.assertEqual((t["n"], t["linked_pairs"], t["cohesion"]), (5, 1, 0.1))

    def test_small_tags_are_omitted(self):
        rep = fm.analyse(self.build({"concepts/a.md": page("title: A\ntags: [t]")}))
        self.assertEqual(rep["clusters"], {})


if __name__ == "__main__":
    unittest.main()
