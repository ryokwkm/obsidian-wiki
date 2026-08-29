#!/usr/bin/env python3
"""candidates.py のテスト。

    python3 llm-tpl/wiki/skills/wiki-dedup/scripts/tests/test_candidates.py

固定してあるのは、実 vault の実測（2026-08-13・3 vault 168 ページ）で設計判断の
根拠になった振る舞い:

  - 除外（`_` 始まり / `.wikilintignore` / 管理ファイル / redirect stub）が効くこと
    —— 効かないと note vault では上位 30 対の 43% が「マージ禁止」ページで埋まる
  - 日本語本文で overlap が出ること（空白区切りに依存しない）
  - `relationships:` で結ばれた対が候補から外れて別枠へ回ること
  - 短いページが黙って混ざらないこと（stub 同士は containment が 1.0 に跳ねる）
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import candidates  # noqa: E402

# 本文が MIN_GRAMS を超えるだけの分量を持つ日本語の素材。2 ページで大半が重なる。
BODY_A = """
このページはスクレイピングバッチの処理フローを説明する。
バッチは 20 分間隔で起動し、出馬表と騎手プロフィールを収集して保存する。
収集に失敗したレースは次の周回で再取得され、取得済みのレースは触らない。
アクセス間隔は固定で、連続リクエストの上限を超えないように待機を挟む。
"""
BODY_B = """
バッチは 20 分間隔で起動し、出馬表と騎手プロフィールを収集して保存する。
収集に失敗したレースは次の周回で再取得され、取得済みのレースは触らない。
アクセス間隔は固定で、連続リクエストの上限を超えないように待機を挟む。
加えて当日分の暫定オッズを前倒しで取得する経路がある。
"""
BODY_OTHER = """
ここでは管理画面のロール制御について述べる。企業管理者は全ロールを内包しており、
権限の無い画面へ入ろうとしても弾かれるだけでリダイレクトは起きない。
画面の一覧は静的解析で機械抽出できるが、宣言の形が揃っていないと漏れる。
"""


def page(title: str, body: str, **fm: str) -> str:
    head = [f"title: {title}"]
    head += [f"{k}: {v}" for k, v in fm.items()]
    return "---\n" + "\n".join(head) + "\n---\n" + body


class VaultCase(unittest.TestCase):
    def build(self, files: dict[str, str], top: int = 20) -> dict:
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(tmp, ignore_errors=True))
        root = Path(tmp)
        for rel, body in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        return candidates.analyse(root, top)

    def pairs(self, res: dict) -> set[frozenset[str]]:
        return {frozenset((r["a"], r["b"])) for r in res["candidates"]}


class TestExclusion(VaultCase):
    def test_underscore_dirs_are_excluded(self):
        res = self.build({
            "concepts/a.md": page("A", BODY_A),
            "concepts/b.md": page("B", BODY_B),
            "_source_docs/orig.md": page("原本", BODY_A),
            "_raw/draft.md": page("下書き", BODY_B),
        })
        self.assertEqual(res["pages_scanned"], 2)
        self.assertEqual(self.pairs(res), {frozenset(("concepts/a", "concepts/b"))})

    def test_wikilintignore_is_honoured(self):
        res = self.build({
            ".wikilintignore": "# 読み物版\nreports/\n",
            "concepts/a.md": page("A", BODY_A),
            "concepts/b.md": page("B", BODY_B),
            "reports/long.md": page("読み物", BODY_A),
        })
        self.assertEqual(res["pages_scanned"], 2)
        self.assertNotIn("reports/long", [p for r in res["candidates"] for p in (r["a"], r["b"])])

    def test_wikilintignore_with_bom(self):
        """BOM 付きで保存されても先頭行のパターンが効く（linkgraph.py と同じ罠）。"""
        res = self.build({
            ".wikilintignore": "﻿reports/\n",
            "concepts/a.md": page("A", BODY_A),
            "reports/long.md": page("読み物", BODY_A),
        })
        self.assertEqual(res["pages_scanned"], 1)

    def test_management_files_and_stubs_are_excluded(self):
        res = self.build({
            "index.md": page("索引", BODY_A),
            "hot.md": page("hot", BODY_A),
            "log.md": page("log", BODY_A),
            "README.md": page("README", BODY_A),
            "concepts/a.md": page("A", BODY_A),
            "concepts/old.md": page("旧", BODY_B, redirects_to='"[[concepts/a]]"'),
        })
        self.assertEqual(res["pages_scanned"], 1)
        self.assertEqual(res["candidates"], [])


class TestScoring(VaultCase):
    def test_japanese_bodies_overlap_without_spaces(self):
        """日本語は空白で区切られないので、語トークンでは 0 になる対を拾えること。"""
        res = self.build({
            "concepts/a.md": page("まったく違う題名", BODY_A),
            "concepts/b.md": page("重ならない見出し", BODY_B),
        })
        self.assertEqual(len(res["candidates"]), 1)
        self.assertGreater(res["candidates"][0]["overlap"], 0.5)

    def test_unrelated_pages_score_lower_than_related(self):
        res = self.build({
            "concepts/a.md": page("A", BODY_A),
            "concepts/b.md": page("B", BODY_B),
            "concepts/c.md": page("C", BODY_OTHER),
        })
        ranked = [(frozenset((r["a"], r["b"])), r["score"]) for r in res["candidates"]]
        top_pair, top_score = ranked[0]
        self.assertEqual(top_pair, frozenset(("concepts/a", "concepts/b")))
        self.assertTrue(all(s < top_score for _p, s in ranked[1:]))

    def test_alias_match_is_flagged(self):
        res = self.build({
            "entities/x.md": page("要約ページ", BODY_A, aliases="[batch-scrape]"),
            "references/x-detail.md": page("詳細ページ", BODY_B, aliases="[batch-scrape, other]"),
        })
        self.assertIn("alias-match", res["candidates"][0]["signals"])

    def test_code_blocks_do_not_drive_the_score(self):
        """実装断片が共通するだけの対が上位に来ないこと。"""
        code = "\n```go\nfunc main() { fmt.Println(\"same snippet everywhere\") }\n```\n"
        res = self.build({
            "concepts/a.md": page("A", BODY_OTHER + code),
            "concepts/b.md": page("B", BODY_A + code),
            "concepts/c.md": page("C", BODY_B),
        })
        top = res["candidates"][0]
        self.assertEqual(frozenset((top["a"], top["b"])), frozenset(("concepts/b", "concepts/c")))


class TestRelationships(VaultCase):
    REL_MD = 'relationships:\n  - target: "[詳細](../references/x-detail.md)"\n    type: elaborates'
    REL_WIKILINK = 'relationships:\n  - target: "[[references/x-detail]]"\n    type: elaborates'

    def _vault(self, rel: str) -> dict:
        return self.build({
            "entities/x.md": "---\ntitle: 要約\n" + rel + "\n---\n" + BODY_A,
            "references/x-detail.md": page("詳細", BODY_B),
        })

    def test_markdown_link_target_moves_pair_aside(self):
        res = self._vault(self.REL_MD)
        self.assertEqual(res["candidates"], [])
        self.assertEqual(len(res["already_linked"]), 1)

    def test_wikilink_target_moves_pair_aside(self):
        res = self._vault(self.REL_WIKILINK)
        self.assertEqual(res["candidates"], [])
        self.assertEqual(len(res["already_linked"]), 1)

    def test_unlinked_pair_stays_a_candidate(self):
        res = self.build({
            "entities/x.md": page("要約", BODY_A),
            "references/x-detail.md": page("詳細", BODY_B),
        })
        self.assertEqual(len(res["candidates"]), 1)
        self.assertEqual(res["already_linked"], [])


class TestShortPages(VaultCase):
    def test_short_pages_are_reported_not_dropped(self):
        res = self.build({
            "concepts/a.md": page("A", BODY_A),
            "concepts/b.md": page("B", BODY_B),
            "concepts/stub1.md": page("stub1", "短い。\n"),
            "concepts/stub2.md": page("stub2", "短い。\n"),
        })
        self.assertEqual(res["pages_scanned"], 4)
        self.assertEqual(res["pages_compared"], 2)
        self.assertEqual(sorted(res["pages_too_short"]), ["concepts/stub1", "concepts/stub2"])
        self.assertEqual(self.pairs(res), {frozenset(("concepts/a", "concepts/b"))})


class TestFrontmatter(unittest.TestCase):
    def test_block_scalar_title(self):
        fm = "\ntitle: >-\n    折り返した題名の\n    続き\ncategory: concepts\n"
        self.assertEqual(candidates.parse_frontmatter(fm)["title"], "折り返した題名の 続き")

    def test_list_forms(self):
        fm = "\naliases: [a, b]\ntags:\n  - x\n  - y\n"
        got = candidates.parse_frontmatter(fm)
        self.assertEqual(got["aliases"], ["a", "b"])
        self.assertEqual(got["tags"], ["x", "y"])

    def test_relationship_targets_ignore_trailing_type(self):
        fm = 'relationships:\n  - target: "[x](../a/b.md)"\n    type: elaborates\nsources: [z]\n'
        self.assertEqual(candidates.relationship_targets(fm), {"b"})


class TestRendering(VaultCase):
    def test_render_states_scores_are_relative(self):
        res = self.build({
            "concepts/a.md": page("A", BODY_A),
            "concepts/b.md": page("B", BODY_B),
        })
        out = candidates.render(res)
        self.assertIn("閾値", out)
        self.assertIn("concepts/a", out)

    def test_empty_vault_does_not_crash(self):
        res = self.build({"index.md": page("索引", BODY_A)})
        self.assertEqual(res["pairs_evaluated"], 0)
        self.assertIn("比較できるページが足りない", candidates.render(res))


if __name__ == "__main__":
    unittest.main(verbosity=2)
