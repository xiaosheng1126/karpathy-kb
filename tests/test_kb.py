"""Tests for kb.py new functionality."""
import datetime as dt
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "scripts"))
import kb


class TestFrontmatterValue(unittest.TestCase):
    def test_reads_saved_at(self):
        text = "---\nsaved_at: 2026-06-15\nstatus: fetched\n---\n# Title"
        self.assertEqual(kb.frontmatter_value(text, "saved_at"), "2026-06-15")

    def test_missing_field_returns_empty(self):
        text = "---\nstatus: fetched\n---\n# Title"
        self.assertEqual(kb.frontmatter_value(text, "saved_at"), "")


class TestParseSimpleYaml(unittest.TestCase):
    def test_string_value(self):
        result = kb._parse_simple_yaml("role_id: technical_practitioner\n")
        self.assertEqual(result["role_id"], "technical_practitioner")

    def test_int_value(self):
        result = kb._parse_simple_yaml("time_window_days: 7\n")
        self.assertEqual(result["time_window_days"], 7)

    def test_inline_list(self):
        result = kb._parse_simple_yaml("focus_areas: [Android, Flutter, AI Coding]\n")
        self.assertEqual(result["focus_areas"], ["Android", "Flutter", "AI Coding"])

    def test_empty_list(self):
        result = kb._parse_simple_yaml("items: []\n")
        self.assertEqual(result["items"], [])


class TestRawsInWindow(unittest.TestCase):
    def test_filters_by_saved_at(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            # Write a raw that's within the window
            (raw_dir / "recent.md").write_text(
                "---\nsaved_at: 2026-06-20\nstatus: fetched\ntitle: Recent\n---\n",
                encoding="utf-8",
            )
            # Write a raw that's outside the window
            (raw_dir / "old.md").write_text(
                "---\nsaved_at: 2026-01-01\nstatus: fetched\ntitle: Old\n---\n",
                encoding="utf-8",
            )
            cutoff = dt.date(2026, 6, 14)
            results = kb._raws_in_window(raw_dir, cutoff)
            filenames = [p.name for p, _, _ in results]
            self.assertIn("recent.md", filenames)
            self.assertNotIn("old.md", filenames)

    def test_falls_back_to_fetched_at(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            (raw_dir / "no_saved_at.md").write_text(
                "---\nfetched_at: 2026-06-20T10:00:00\nstatus: fetched\ntitle: Test\n---\n",
                encoding="utf-8",
            )
            cutoff = dt.date(2026, 6, 14)
            results = kb._raws_in_window(raw_dir, cutoff)
            self.assertEqual(len(results), 1)


class TestFrontmatterListValue(unittest.TestCase):
    def test_reads_wiki_targets(self):
        text = "---\nwiki_targets: [代理工具, TUN模式]\nstatus: fetched\n---\n# Title"
        result = kb.frontmatter_list_value(text, "wiki_targets")
        self.assertEqual(result, ["代理工具", "TUN模式"])

    def test_empty_list(self):
        text = "---\nwiki_targets: []\nstatus: fetched\n---\n# Title"
        result = kb.frontmatter_list_value(text, "wiki_targets")
        self.assertEqual(result, [])

    def test_missing_key_returns_empty(self):
        text = "---\nstatus: fetched\n---\n# Title"
        result = kb.frontmatter_list_value(text, "wiki_targets")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
