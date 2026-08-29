#!/usr/bin/env python3
"""linkgraph.py のテスト。

    python3 llm-tpl/wiki/skills/wiki-lint/scripts/tests/test_linkgraph.py

実 vault で確認した誤検出（外部 URL の .md / ドメイン名の中の .md / コード例の
リンク記法 / basename の衝突）を、それぞれ回帰テストとして固定してある。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import linkgraph  # noqa: E402


class VaultCase(unittest.TestCase):
    """一時ディレクトリに vault を組み立てて解析するための土台。"""

    def build(self, files: dict[str, str]) -> dict:
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        root = Path(tmp)
        for rel, body in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body, encoding="utf-8")
        return linkgraph.analyse(root)

    def targets(self, body: str) -> list[str]:
        return [t for _kind, t in linkgraph.extract_targets(body)]

    def kinds(self, body: str) -> list[tuple[str, str]]:
        return linkgraph.extract_targets(body)

    def linked(self, result: dict) -> dict[str, int]:
        """incoming のうち 0 でないものだけ。「どこに辺が入ったか」を見るため。"""
        return {k: v for k, v in result["incoming"].items() if v}


class TestCodeRegions(VaultCase):
    def test_fenced_block_is_not_a_link(self):
        body = "本文 [[real]]\n\n```md\n[[example]]\n```\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_unclosed_fence_strips_to_eof(self):
        body = "[[real]]\n\n```\n[[a]]\n[[b]]\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_tilde_fence(self):
        body = "[[real]]\n~~~\n[[nope]]\n~~~\n[[also-real]]\n"
        self.assertEqual(self.targets(body), ["real", "also-real"])

    def test_inline_code_is_not_a_link(self):
        body = "記法は `[[wikilink]]` と書く。実体は [[real]]。\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_double_backtick_span_strips_whole(self):
        # ``code with ` inside`` は丸ごと落ちる（CommonMark: N 個は ちょうど N 個で閉じる）
        body = "``[[x]] and ` inside`` のあと [[real]]\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_unmatched_backtick_survives(self):
        body = "対応の取れない ` バッククォート [[real]]\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_fence_keeps_line_numbers(self):
        # 行番号を報告に使うので、フェンス内は削除ではなく空行へ
        body = "a\n```\nx\ny\n```\nb\n"
        self.assertEqual(len(linkgraph.strip_code_regions(body).split("\n")),
                         len(body.split("\n")))


class TestMarkdownLinks(VaultCase):
    def test_external_url_ending_in_md_is_not_a_link(self):
        body = "[docs](https://code.claude.com/docs/en/memory.md) と [[real]]\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_md_inside_domain_name_is_not_a_link(self):
        # 上流 Ar9av の `[^)]+\.md[^)]*` はこれを拾って [[68]] を broken と報告した
        body = "[論文](https://www.mdpi.com/2227-9091/8/3/68)\n[[real]]\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_relative_md_link_is_a_link(self):
        # 抽出は生の href のまま返す（.md を落とすのは resolve 側）
        body = "[仕様](../alpha-prediction/build-spec.md)\n"
        self.assertEqual(self.targets(body), ["../alpha-prediction/build-spec.md"])

    def test_md_link_with_anchor_and_title(self):
        body = '[x](./page.md#sec) [y](./other.md "タイトル")\n'
        self.assertEqual(self.targets(body), ["./page.md", "./other.md"])


class TestWikilinkForms(VaultCase):
    def test_pipe_and_anchor_are_stripped(self):
        body = "[[foo|表示名]] [[bar#見出し]]\n"
        self.assertEqual(self.targets(body), ["foo", "bar"])

    def test_asset_embed_is_ignored(self):
        body = "![[diagram.png]] ![[deck.pdf]] [[real]]\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_heading_only_link_is_ignored(self):
        body = "[[#見出しだけ]] [[real]]\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_template_placeholder_is_ignored(self):
        body = "[[{{title}}]] [[real]]\n"
        self.assertEqual(self.targets(body), ["real"])


class TestResolution(VaultCase):
    def test_md_link_without_dot_slash_is_source_relative(self):
        # markdown の `[x](spec.md)` は同ディレクトリの相対パス。vault 全体の
        # basename 解決にすると、同名ページがある vault で ambiguous に化ける
        r = self.build({
            "alpha/a.md": "[仕様](spec.md)\n",
            "alpha/spec.md": "x\n",
            "beta/spec.md": "y\n",
            "beta/b.md": "[仕様](spec.md)\n",
        })
        self.assertEqual(r["ambiguous"], [])
        self.assertEqual(r["broken"], [])
        self.assertEqual(self.linked(r), {"alpha/spec.md": 1, "beta/spec.md": 1})

    def test_wikilink_bare_name_stays_vault_wide(self):
        # 対して `[[spec]]` は Obsidian の参照なので vault 全体で引く（1 件なら解決）
        r = self.build({"alpha/a.md": "[[spec]]\n", "beta/spec.md": "y\n"})
        self.assertEqual(r["broken"], [])
        self.assertEqual(self.linked(r), {"beta/spec.md": 1})

    def test_md_link_falls_back_to_vault_root(self):
        r = self.build({"deep/dir/a.md": "[x](concepts/b.md)\n", "concepts/b.md": "y\n"})
        self.assertEqual(r["broken"], [])
        self.assertEqual(self.linked(r), {"concepts/b.md": 1})

    def test_basename_collision_is_ambiguous(self):
        # 実 vault で見た「隣接する 2 ディレクトリに同名ページがある」状況
        r = self.build({
            "a.md": "[[spec]]\n",
            "alpha/spec.md": "x\n",
            "beta/spec.md": "y\n",
        })
        self.assertEqual(len(r["ambiguous"]), 1)
        self.assertEqual(r["broken"], [])

    def test_path_form_disambiguates_collision(self):
        r = self.build({
            "a.md": "[[beta/spec]]\n",
            "alpha/spec.md": "x\n",
            "beta/spec.md": "y\n",
        })
        self.assertEqual(r["ambiguous"], [])
        self.assertEqual(r["broken"], [])
        self.assertEqual(self.linked(r), {"beta/spec.md": 1})

    def test_source_relative_resolution(self):
        r = self.build({
            "concepts/a.md": "[link](../entities/b.md)\n",
            "entities/b.md": "x\n",
        })
        self.assertEqual(r["broken"], [])
        self.assertEqual(self.linked(r), {"entities/b.md": 1})

    def test_relative_escaping_vault_is_broken(self):
        r = self.build({"a.md": "[x](../../outside.md)\n"})
        self.assertEqual(len(r["broken"]), 1)

    def test_alias_resolves(self):
        r = self.build({
            "a.md": "[[べつめい]]\n",
            "b.md": "---\naliases:\n  - べつめい\n---\n\nx\n",
        })
        self.assertEqual(r["broken"], [])
        self.assertEqual(self.linked(r), {"b.md": 1})

    def test_inline_alias_list_resolves(self):
        r = self.build({
            "a.md": "[[alt]]\n",
            "b.md": "---\naliases: [alt, other]\n---\n\nx\n",
        })
        self.assertEqual(r["broken"], [])

    def test_case_and_space_are_normalised(self):
        r = self.build({"a.md": "[[My Page]]\n", "my-page.md": "x\n"})
        self.assertEqual(r["broken"], [])


class TestOrphans(VaultCase):
    def test_orphan_needs_both_directions_zero(self):
        # 出リンクだけ持つページは orphan ではない（上流 lint.py:236-238 と同じ定義）
        r = self.build({"a.md": "[[b]]\n", "b.md": "x\n", "lonely.md": "何もなし\n"})
        self.assertEqual(r["orphans"], ["lonely.md"])

    def test_reserved_pages_are_never_orphans(self):
        r = self.build({
            "index.md": "空\n", "log.md": "空\n", "hot.md": "空\n", "_insights.md": "空\n",
        })
        self.assertEqual(r["orphans"], [])

    def test_self_link_is_not_an_edge(self):
        r = self.build({"a.md": "[[a]]\n"})
        self.assertEqual(r["orphans"], ["a.md"])

    def test_frontmatter_relationship_counts_as_edge(self):
        # typed relationship だけを持つページを orphan にしない
        r = self.build({
            "a.md": '---\nrelationships:\n  - target: "[[b]]"\n    type: uses\n---\n\n本文\n',
            "b.md": "x\n",
        })
        self.assertEqual(r["orphans"], [])
        self.assertEqual(self.linked(r), {"b.md": 1})


class TestSkipping(VaultCase):
    def test_underscore_dirs_are_skipped(self):
        r = self.build({
            "a.md": "[[b]]\n", "b.md": "x\n",
            "_raw/draft.md": "下書き\n", "_source_docs/spec.md": "一次資料\n",
        })
        self.assertEqual(r["stats"]["pages"], 2)
        self.assertEqual(r["orphans"], [])

    def test_wikilintignore_adds_dirs(self):
        r = self.build({
            ".wikilintignore": "# 読み物版はページではない\nreports/\n",
            "a.md": "[[b]]\n", "b.md": "x\n",
            "reports/long.md": "レポート\n",
        })
        self.assertEqual(r["stats"]["pages"], 2)
        self.assertEqual(r["orphans"], [])

    def test_dot_dirs_are_skipped(self):
        r = self.build({"a.md": "x\n", ".obsidian/plugin.md": "設定\n"})
        self.assertEqual(r["stats"]["pages"], 1)

    def test_wikilintignore_supports_globs(self):
        r = self.build({
            ".wikilintignore": "drafts/*.md\n",
            "a.md": "[[b]]\n", "b.md": "x\n", "drafts/wip.md": "下書き\n",
        })
        self.assertEqual(r["stats"]["pages"], 2)

    def test_wikilintignore_with_bom(self):
        # BOM 付きで保存されると先頭行のパターンが黙って無効になっていた
        r = self.build({
            ".wikilintignore": "﻿reports/\n",
            "a.md": "[[b]]\n", "b.md": "x\n", "reports/r.md": "レポート\n",
        })
        self.assertEqual(r["stats"]["pages"], 2)

    def test_link_into_excluded_dir_is_not_broken(self):
        # 除外先のファイルは実在する。broken と報告すると直しようのない指摘になる
        r = self.build({
            ".wikilintignore": "reports/\n",
            "a.md": "[詳細](reports/long.md)\n",
            "reports/long.md": "レポート\n",
        })
        self.assertEqual(r["broken"], [])
        self.assertEqual(len(r["links_to_excluded"]), 1)
        self.assertEqual(r["orphans"], ["a.md"])  # 辺にはならない

    def test_unreadable_file_does_not_abort_the_run(self):
        r = self.build({"a.md": "[[b]]\n", "b.md": "x\n"})
        # 壊れた symlink を足しても解析は続く
        import os, tempfile
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        (tmp / "a.md").write_text("[[b]]\n", encoding="utf-8")
        (tmp / "b.md").write_text("x\n", encoding="utf-8")
        os.symlink(tmp / "does-not-exist.md", tmp / "dangling.md")
        r = linkgraph.analyse(tmp)
        self.assertEqual(r["stats"]["pages"], 2)
        self.assertEqual(r["unreadable"], ["dangling.md"])


class TestGraphOutput(VaultCase):
    """wiki-lint の orphan 判定と共起カウントがこの形に依存している。"""

    def test_returns_pages_incoming_outgoing_edges(self):
        r = self.build({"a.md": "[[b]]\n", "b.md": "x\n", "lonely.md": "何もなし\n"})
        self.assertEqual(sorted(r["pages"]), ["a.md", "b.md", "lonely.md"])
        self.assertEqual(r["edges"], [{"from": "a.md", "to": "b.md"}])
        self.assertEqual(r["outgoing"], {"a.md": 1, "b.md": 0, "lonely.md": 0})
        self.assertEqual(r["incoming"], {"b.md": 1, "a.md": 0, "lonely.md": 0})

    def test_incoming_counts_pages_not_links(self):
        # 1 ページから 3 回張られても「1 ページに参照されている」。ハブ判定が歪むため
        r = self.build({"a.md": "[[b]] [[b]] [[b]]\n", "b.md": "x\n"})
        self.assertEqual(r["incoming"]["b.md"], 1)
        self.assertEqual(r["incoming_links"]["b.md"], 3)
        self.assertEqual(r["outgoing"]["a.md"], 3)


class TestFenceEdgeCases(VaultCase):
    def test_four_backtick_fence_is_not_closed_by_three(self):
        # ```` で開いたフェンスの中の ``` は閉じない（CommonMark）
        body = "````\n```\n[[nope]]\n```\n````\n[[real]]\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_tilde_fence_not_closed_by_backticks(self):
        body = "~~~\n```\n[[nope]]\n~~~\n[[real]]\n"
        self.assertEqual(self.targets(body), ["real"])

    def test_indented_fence(self):
        body = "  ```\n  [[nope]]\n  ```\n[[real]]\n"
        self.assertEqual(self.targets(body), ["real"])


class TestMdLinkStrictness(VaultCase):
    def test_md_link_does_not_fall_back_to_basename(self):
        # パスが外れた markdown リンクは broken。vault 中の同名を勝手に拾わない
        r = self.build({
            "concepts/a.md": "[x](./nowhere/spec.md)\n",
            "other/spec.md": "無関係なページ\n",
        })
        self.assertEqual(len(r["broken"]), 1)
        self.assertEqual(r["incoming"]["other/spec.md"], 0)

    def test_bare_md_link_missing_in_both_places_is_broken(self):
        r = self.build({"deep/a.md": "[x](spec.md)\n", "other/spec.md": "無関係\n"})
        self.assertEqual(len(r["broken"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
