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


class TestFindMatchingWikis(unittest.TestCase):
    def test_matched(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "proxy.md").write_text(
                "# 代理工具 TUN 模式下国内网站断网问题\n\n内容",
                encoding="utf-8",
            )
            matched, unmatched = kb.find_matching_wikis(["代理工具"], wiki_dir)
            self.assertEqual(len(matched), 1)
            self.assertEqual(matched[0][0], "代理工具")
            self.assertIn("代理工具", matched[0][2])
            self.assertEqual(unmatched, [])

    def test_matched_case_insensitive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "flutter.md").write_text(
                "# Flutter 状态管理对比\n\n内容",
                encoding="utf-8",
            )
            matched, unmatched = kb.find_matching_wikis(["flutter"], wiki_dir)
            self.assertEqual(len(matched), 1)
            self.assertEqual(unmatched, [])

    def test_unmatched(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "proxy.md").write_text(
                "# 代理工具 TUN 模式\n\n内容",
                encoding="utf-8",
            )
            matched, unmatched = kb.find_matching_wikis(["Flutter"], wiki_dir)
            self.assertEqual(matched, [])
            self.assertEqual(unmatched, ["Flutter"])

    def test_empty_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            matched, unmatched = kb.find_matching_wikis([], wiki_dir)
            self.assertEqual(matched, [])
            self.assertEqual(unmatched, [])

    def test_skips_readme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "README.md").write_text("# README\n\n内容", encoding="utf-8")
            matched, unmatched = kb.find_matching_wikis(["README"], wiki_dir)
            self.assertEqual(matched, [])
            self.assertEqual(unmatched, ["README"])

    def test_wiki_without_h1_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "no_title.md").write_text("普通段落\n没有标题", encoding="utf-8")
            matched, unmatched = kb.find_matching_wikis(["no_title"], wiki_dir)
            self.assertEqual(matched, [])
            self.assertEqual(unmatched, ["no_title"])

    def test_target_matches_multiple_wikis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "a.md").write_text("# Flutter 状态管理\n\n内容", encoding="utf-8")
            (wiki_dir / "b.md").write_text("# Flutter 渲染原理\n\n内容", encoding="utf-8")
            matched, unmatched = kb.find_matching_wikis(["Flutter"], wiki_dir)
            self.assertEqual(len(matched), 2)
            self.assertEqual(unmatched, [])


class TestScanAgingRaws(unittest.TestCase):
    def _write_raw(self, raw_dir: pathlib.Path, name: str, valid_until: str, title: str = "Test") -> None:
        (raw_dir / name).write_text(
            f"---\nvalid_until: {valid_until}\ntitle: {title}\nstatus: fetched\n---\n# {title}\n",
            encoding="utf-8",
        )

    def test_expired_entry_returned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            self._write_raw(raw_dir, "old.md", "2020-01-01", "Old Thing")
            today = dt.date(2026, 6, 23)
            results = kb.scan_aging_raws(raw_dir, today)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "expired")
            self.assertEqual(results[0].label, "Old Thing")
            self.assertLess(results[0].days_diff, 0)

    def test_aging_entry_returned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            future = dt.date(2026, 6, 23) + dt.timedelta(days=10)
            self._write_raw(raw_dir, "soon.md", future.isoformat(), "Soon Thing")
            today = dt.date(2026, 6, 23)
            results = kb.scan_aging_raws(raw_dir, today, aging_threshold_days=30)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "aging")
            self.assertEqual(results[0].days_diff, 10)

    def test_ok_entry_not_returned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            future = dt.date(2026, 6, 23) + dt.timedelta(days=60)
            self._write_raw(raw_dir, "fine.md", future.isoformat(), "Fine Thing")
            today = dt.date(2026, 6, 23)
            results = kb.scan_aging_raws(raw_dir, today, aging_threshold_days=30)
            self.assertEqual(results, [])

    def test_missing_valid_until_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            (raw_dir / "no_date.md").write_text(
                "---\ntitle: No Date\nstatus: fetched\n---\n# No Date\n",
                encoding="utf-8",
            )
            results = kb.scan_aging_raws(raw_dir, dt.date(2026, 6, 23))
            self.assertEqual(results, [])

    def test_readme_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            (raw_dir / "README.md").write_text(
                "---\nvalid_until: 2020-01-01\ntitle: README\n---\n# README\n",
                encoding="utf-8",
            )
            results = kb.scan_aging_raws(raw_dir, dt.date(2026, 6, 23))
            self.assertEqual(results, [])

    def test_year_month_format_parsed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            self._write_raw(raw_dir, "ym.md", "2020-01", "Year Month")
            results = kb.scan_aging_raws(raw_dir, dt.date(2026, 6, 23))
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "expired")


class TestScanAgingWikis(unittest.TestCase):
    def _write_wiki(self, wiki_dir: pathlib.Path, name: str, content: str) -> None:
        (wiki_dir / name).write_text(content, encoding="utf-8")

    def _judgment_block(self, statement: str, valid_until: str, deprecated: bool = False) -> str:
        stmt = f"~~{statement}~~" if deprecated else statement
        return (
            f"**判断**：{stmt}\n"
            f"- 置信度：medium\n"
            f"- 有效期：{valid_until}\n"
            f"- 来源：raw/test.md\n"
        )

    def test_expired_judgment_returned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            content = "# Test Wiki\n\n" + self._judgment_block("X 工具值得跟踪", "2020-01")
            self._write_wiki(wiki_dir, "test.md", content)
            results = kb.scan_aging_wikis(wiki_dir, dt.date(2026, 6, 23))
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "expired")
            self.assertEqual(results[0].label, "X 工具值得跟踪")
            self.assertLess(results[0].days_diff, 0)

    def test_aging_judgment_returned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            future = dt.date(2026, 6, 23) + dt.timedelta(days=10)
            valid_until = future.strftime("%Y-%m")
            content = "# Test Wiki\n\n" + self._judgment_block("Y 工具稳定", valid_until)
            self._write_wiki(wiki_dir, "test.md", content)
            results = kb.scan_aging_wikis(wiki_dir, dt.date(2026, 6, 23), aging_threshold_days=30)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].status, "aging")

    def test_ok_judgment_not_returned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            content = "# Test Wiki\n\n" + self._judgment_block("Z 工具好用", "2028-01")
            self._write_wiki(wiki_dir, "test.md", content)
            results = kb.scan_aging_wikis(wiki_dir, dt.date(2026, 6, 23), aging_threshold_days=30)
            self.assertEqual(results, [])

    def test_deprecated_judgment_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            content = "# Test Wiki\n\n" + self._judgment_block("旧工具", "2020-01", deprecated=True)
            self._write_wiki(wiki_dir, "test.md", content)
            results = kb.scan_aging_wikis(wiki_dir, dt.date(2026, 6, 23))
            self.assertEqual(results, [])

    def test_judgment_without_valid_until_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            content = "# Test Wiki\n\n**判断**：A 工具好用\n- 置信度：high\n- 来源：raw/x.md\n"
            self._write_wiki(wiki_dir, "test.md", content)
            results = kb.scan_aging_wikis(wiki_dir, dt.date(2026, 6, 23))
            self.assertEqual(results, [])

    def test_readme_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            content = "# README\n\n" + self._judgment_block("Some thing", "2020-01")
            self._write_wiki(wiki_dir, "README.md", content)
            results = kb.scan_aging_wikis(wiki_dir, dt.date(2026, 6, 23))
            self.assertEqual(results, [])

    def test_multiple_judgments_in_one_wiki(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            content = (
                "# Test Wiki\n\n"
                + self._judgment_block("A 工具", "2020-01")
                + "\n"
                + self._judgment_block("B 工具", "2028-01")
            )
            self._write_wiki(wiki_dir, "test.md", content)
            results = kb.scan_aging_wikis(wiki_dir, dt.date(2026, 6, 23), aging_threshold_days=30)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].label, "A 工具")


class TestBuildAgingReport(unittest.TestCase):
    def _make_entry(self, name: str, kind: str, label: str, days_diff: int) -> kb.AgingEntry:
        status = "expired" if days_diff < 0 else "aging"
        valid_until = dt.date(2026, 6, 23) + dt.timedelta(days=days_diff)
        return kb.AgingEntry(
            file=pathlib.Path(f"/tmp/{name}"),
            kind=kind,
            label=label,
            valid_until=valid_until,
            status=status,
            days_diff=days_diff,
        )

    def test_expired_raw_shows_expired_tag(self):
        entry = self._make_entry("raw/old.md", "raw", "Old Tool", -10)
        report = kb.build_aging_report([entry], [], dt.date(2026, 6, 23))
        self.assertIn("EXPIRED", report)
        self.assertIn("Old Tool", report)
        self.assertIn("已过期 10 天", report)

    def test_aging_raw_shows_aging_tag(self):
        entry = self._make_entry("raw/soon.md", "raw", "Soon Tool", 5)
        report = kb.build_aging_report([entry], [], dt.date(2026, 6, 23))
        self.assertIn("AGING", report)
        self.assertIn("还剩 5 天", report)

    def test_wiki_judgment_in_wiki_section(self):
        entry = self._make_entry("wiki/test.md", "wiki_judgment", "Some judgment", -30)
        report = kb.build_aging_report([], [entry], dt.date(2026, 6, 23))
        self.assertIn("Wiki 判断", report)
        self.assertIn("Some judgment", report)

    def test_empty_entries_show_placeholder(self):
        report = kb.build_aging_report([], [], dt.date(2026, 6, 23))
        self.assertIn("无到期或即将到期条目", report)
        self.assertIn("无到期或即将到期判断", report)

    def test_report_header_contains_date(self):
        report = kb.build_aging_report([], [], dt.date(2026, 6, 23))
        self.assertIn("2026-06-23", report)


class TestParseValidUntil(unittest.TestCase):
    def test_full_date(self):
        result = kb._parse_valid_until("2026-12-31")
        self.assertEqual(result, dt.date(2026, 12, 31))

    def test_year_month_becomes_first_of_month(self):
        result = kb._parse_valid_until("2026-12")
        self.assertEqual(result, dt.date(2026, 12, 1))

    def test_empty_string_returns_none(self):
        result = kb._parse_valid_until("")
        self.assertIsNone(result)

    def test_invalid_string_returns_none(self):
        result = kb._parse_valid_until("not-a-date")
        self.assertIsNone(result)


class TestBuildAgingBlock(unittest.TestCase):
    def _make_entry(self, status: str, days_diff: int, label: str, file_name: str = "test.md") -> "kb.AgingEntry":
        valid_until = dt.date(2026, 6, 23) + dt.timedelta(days=days_diff)
        return kb.AgingEntry(pathlib.Path(f"/tmp/{file_name}"), "raw", label, valid_until, status, days_diff)

    def test_empty_when_no_entries(self):
        result = kb.build_aging_block([], [])
        self.assertEqual(result, "")

    def test_expired_entry_appears(self):
        entry = self._make_entry("expired", -10, "过期文章")
        result = kb.build_aging_block([entry], [])
        self.assertIn("[EXPIRED]", result)
        self.assertIn("过期文章", result)

    def test_aging_entry_appears(self):
        entry = self._make_entry("aging", 5, "即将过期文章")
        result = kb.build_aging_block([entry], [])
        self.assertIn("[AGING", result)
        self.assertIn("即将过期文章", result)

    def test_section_header_present(self):
        entry = self._make_entry("expired", -1, "任意标题")
        result = kb.build_aging_block([entry], [])
        self.assertIn("知识老化预警", result)

    def test_wiki_entries_included(self):
        entry = self._make_entry("expired", -5, "Wiki判断", "wiki.md")
        result = kb.build_aging_block([], [entry])
        self.assertIn("[EXPIRED]", result)
        self.assertIn("Wiki判断", result)


class TestFormatAgingLogEntry(unittest.TestCase):
    def _make_entry(self, status: str) -> "kb.AgingEntry":
        return kb.AgingEntry(
            pathlib.Path("/tmp/test.md"), "raw", "label",
            dt.date(2026, 6, 23), status, -1 if status == "expired" else 5,
        )

    def test_counts_expired_and_aging_raws(self):
        raw_entries = [self._make_entry("expired"), self._make_entry("aging")]
        result = kb.format_aging_log_entry(
            dt.date(2026, 6, 23), raw_entries, [], pathlib.Path("/tmp/report.md")
        )
        self.assertIn("Raw: 1 已过期，1 即将过期", result)

    def test_counts_expired_and_aging_wikis(self):
        wiki_entries = [self._make_entry("expired"), self._make_entry("expired")]
        result = kb.format_aging_log_entry(
            dt.date(2026, 6, 23), [], wiki_entries, pathlib.Path("/tmp/report.md")
        )
        self.assertIn("Wiki 判断: 2 已过期，0 即将过期", result)

    def test_contains_date(self):
        result = kb.format_aging_log_entry(
            dt.date(2026, 6, 23), [], [], pathlib.Path("/tmp/report.md")
        )
        self.assertIn("2026-06-23", result)

    def test_contains_report_path(self):
        result = kb.format_aging_log_entry(
            dt.date(2026, 6, 23), [], [], pathlib.Path("/tmp/my-report.md")
        )
        self.assertIn("my-report.md", result)

    def test_empty_entries_show_zero_counts(self):
        result = kb.format_aging_log_entry(
            dt.date(2026, 6, 23), [], [], pathlib.Path("/tmp/report.md")
        )
        self.assertIn("Raw: 0 已过期，0 即将过期", result)
        self.assertIn("Wiki 判断: 0 已过期，0 即将过期", result)


if __name__ == "__main__":
    unittest.main()
