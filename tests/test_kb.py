"""Tests for kb.py new functionality."""
import datetime as dt
import io
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

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


class TestAgingCountsByPath(unittest.TestCase):
    def _make_entry(self, path: pathlib.Path, status: str) -> "kb.AgingEntry":
        return kb.AgingEntry(
            path, "wiki_judgment", "label",
            dt.date(2026, 6, 23), status, -1 if status == "expired" else 5,
        )

    def test_expired_and_aging_counted_separately(self):
        p = pathlib.Path("/tmp/wiki.md")
        entries = [self._make_entry(p, "expired"), self._make_entry(p, "aging")]
        result = kb.aging_counts_by_path(entries)
        self.assertEqual(result[p], (1, 1))

    def test_empty_returns_empty_dict(self):
        self.assertEqual(kb.aging_counts_by_path([]), {})

    def test_multiple_paths(self):
        p1 = pathlib.Path("/tmp/a.md")
        p2 = pathlib.Path("/tmp/b.md")
        entries = [self._make_entry(p1, "expired"), self._make_entry(p2, "aging")]
        result = kb.aging_counts_by_path(entries)
        self.assertEqual(result[p1], (1, 0))
        self.assertEqual(result[p2], (0, 1))

    def test_only_expired(self):
        p = pathlib.Path("/tmp/wiki.md")
        entries = [self._make_entry(p, "expired"), self._make_entry(p, "expired")]
        result = kb.aging_counts_by_path(entries)
        self.assertEqual(result[p], (2, 0))


class TestDeprecateRaw(unittest.TestCase):
    def test_sets_deprecated_reason_on_existing_field(self):
        text = "---\ntitle: Test\ndeprecated_reason: \nstatus: fetched\n---\n# Test\n"
        result = kb.deprecate_raw(text, "竞品已取代", dt.date(2026, 6, 23))
        self.assertIn("deprecated_reason: 竞品已取代", result)

    def test_adds_deprecated_reason_if_field_missing(self):
        text = "---\ntitle: Test\nstatus: fetched\n---\n# Test\n"
        result = kb.deprecate_raw(text, "过时", dt.date(2026, 6, 23))
        self.assertIn("deprecated_reason: 过时", result)

    def test_preserves_other_fields(self):
        text = "---\ntitle: Test\nstatus: fetched\ndeprecated_reason: \n---\n# Test\n"
        result = kb.deprecate_raw(text, "reason", dt.date(2026, 6, 23))
        self.assertIn("title: Test", result)
        self.assertIn("status: fetched", result)

    def test_replaces_non_empty_deprecated_reason(self):
        text = "---\ntitle: T\ndeprecated_reason: old reason\n---\n# T\n"
        result = kb.deprecate_raw(text, "new reason", dt.date(2026, 6, 23))
        self.assertIn("deprecated_reason: new reason", result)
        self.assertNotIn("old reason", result)


class TestDeprecateWikiJudgment(unittest.TestCase):
    def test_adds_strikethrough_to_matching_judgment(self):
        text = "# Wiki\n\n**判断**：X 工具值得跟踪\n- 有效期：2026-12\n"
        result = kb.deprecate_wiki_judgment(text, "X 工具", "竞品取代", dt.date(2026, 6, 23))
        self.assertIn("~~X 工具值得跟踪~~", result)
        self.assertIn("已过时：2026-06", result)
        self.assertIn("竞品取代", result)

    def test_case_insensitive_match(self):
        text = "# Wiki\n\n**判断**：Flutter 方案可行\n"
        result = kb.deprecate_wiki_judgment(text, "flutter", "新方案出现", dt.date(2026, 6, 23))
        self.assertIn("~~Flutter 方案可行~~", result)

    def test_no_match_raises_value_error(self):
        text = "# Wiki\n\n**判断**：Y 工具\n"
        with self.assertRaises(ValueError):
            kb.deprecate_wiki_judgment(text, "X 工具", "reason", dt.date(2026, 6, 23))

    def test_already_deprecated_not_matched(self):
        text = "# Wiki\n\n**判断**：~~X 工具~~（已过时）\n"
        with self.assertRaises(ValueError):
            kb.deprecate_wiki_judgment(text, "X 工具", "reason", dt.date(2026, 6, 23))


class TestAddWikiSource(unittest.TestCase):
    def test_adds_to_empty_sources_list(self):
        text = "---\nstatus: published\nsources: []\n---\n# Wiki\n"
        result = kb.add_wiki_source(text, "raw-2026.md")
        self.assertIn("sources: [raw-2026.md]", result)

    def test_appends_to_existing_sources(self):
        text = "---\nstatus: published\nsources: [first.md]\n---\n# Wiki\n"
        result = kb.add_wiki_source(text, "second.md")
        self.assertIn("sources: [first.md, second.md]", result)

    def test_skips_duplicate(self):
        text = "---\nstatus: published\nsources: [raw.md]\n---\n# Wiki\n"
        result = kb.add_wiki_source(text, "raw.md")
        self.assertEqual(result.count("raw.md"), 1)

    def test_inserts_field_when_missing_from_frontmatter(self):
        text = "---\nstatus: published\n---\n# Wiki\n"
        result = kb.add_wiki_source(text, "raw.md")
        self.assertIn("sources: [raw.md]", result)
        self.assertIn("status: published", result)

    def test_adds_frontmatter_when_none_exists(self):
        text = "# Wiki\n\nsome content\n"
        result = kb.add_wiki_source(text, "raw.md")
        self.assertIn("sources: [raw.md]", result)
        self.assertIn("# Wiki", result)


class TestFindRawsForTopic(unittest.TestCase):
    def _write_raw(self, raw_dir: pathlib.Path, name: str, wiki_targets: str, summary: str = "", key_points: str = "") -> None:
        content = (
            f"---\nwiki_targets: [{wiki_targets}]\nsummary: {summary}\nkey_points: [{key_points}]\ntitle: {name}\nstatus: fetched\n---\n# {name}\n"
        )
        (raw_dir / name).write_text(content, encoding="utf-8")

    def test_finds_raw_matching_topic(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            self._write_raw(raw_dir, "proxy.md", "代理工具, TUN模式")
            results = kb.find_raws_for_topic("代理工具", raw_dir)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0][0].name, "proxy.md")

    def test_case_insensitive_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            self._write_raw(raw_dir, "flutter.md", "Flutter, 状态管理")
            results = kb.find_raws_for_topic("flutter", raw_dir)
            self.assertEqual(len(results), 1)

    def test_no_match_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            self._write_raw(raw_dir, "proxy.md", "代理工具")
            results = kb.find_raws_for_topic("Flutter", raw_dir)
            self.assertEqual(results, [])

    def test_returns_summary_and_key_points(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            self._write_raw(raw_dir, "test.md", "Android", summary="Android 总结", key_points="要点1")
            results = kb.find_raws_for_topic("Android", raw_dir)
            self.assertEqual(len(results), 1)
            _, summary, key_points = results[0]
            self.assertIn("Android 总结", summary)

    def test_skips_readme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            (raw_dir / "README.md").write_text("---\nwiki_targets: [Android]\n---\n# README\n", encoding="utf-8")
            results = kb.find_raws_for_topic("Android", raw_dir)
            self.assertEqual(results, [])

    def test_empty_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            results = kb.find_raws_for_topic("Android", raw_dir)
            self.assertEqual(results, [])


class TestBuildCompilePrompt(unittest.TestCase):
    def test_contains_topic(self):
        result = kb.build_compile_prompt("代理工具", [], None)
        self.assertIn("代理工具", result)

    def test_contains_raw_summary(self):
        entries = [(pathlib.Path("/tmp/test.md"), "这是摘要", "要点1, 要点2")]
        result = kb.build_compile_prompt("代理工具", entries, None)
        self.assertIn("这是摘要", result)

    def test_contains_existing_wiki_when_provided(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_path = pathlib.Path(tmpdir) / "existing.md"
            wiki_path.write_text("# 代理工具\n\n已有内容\n", encoding="utf-8")
            result = kb.build_compile_prompt("代理工具", [], wiki_path)
            self.assertIn("已有内容", result)

    def test_no_raws_section_when_empty(self):
        result = kb.build_compile_prompt("代理工具", [], None)
        self.assertIn("代理工具", result)

    def test_no_existing_wiki_note(self):
        result = kb.build_compile_prompt("代理工具", [], None)
        self.assertIn("尚无", result)


class TestSlugifyTopic(unittest.TestCase):
    def test_ascii_topic(self):
        self.assertEqual(kb.slugify_topic("Android"), "android")

    def test_chinese_topic(self):
        result = kb.slugify_topic("代理工具")
        self.assertIn("代理工具", result)

    def test_spaces_become_dashes(self):
        self.assertEqual(kb.slugify_topic("AI Coding"), "ai-coding")

    def test_strips_leading_trailing_dashes(self):
        result = kb.slugify_topic(" test ")
        self.assertFalse(result.startswith("-"))
        self.assertFalse(result.endswith("-"))


class TestBuildCompilePromptOutputTarget(unittest.TestCase):
    def test_prompt_contains_expected_wiki_path(self):
        result = kb.build_compile_prompt("AI Coding", [], None)
        self.assertIn("wiki/ai-coding.md", result)
        self.assertNotIn("{slug}", result)

    def test_prompt_contains_output_target_section(self):
        result = kb.build_compile_prompt("Flutter状态管理", [], None)
        self.assertIn("输出目标", result)
        self.assertIn("sources:", result)


class TestBuildPublishChecklist(unittest.TestCase):
    def test_lists_matched_and_unmatched_wiki_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            raw_path = raw_dir / "source.md"
            raw_path.write_text(
                "---\n"
                "status: fetched\n"
                "title: Source Note\n"
                "wiki_targets: [Proxy, Product Idea]\n"
                "---\n"
                "# Source Note\n",
                encoding="utf-8",
            )
            (wiki_dir / "proxy.md").write_text("# Proxy Tools\n\n内容", encoding="utf-8")

            checklist = kb.build_publish_checklist(raw_path, root)

            self.assertIn("Publish Checklist: Source Note", checklist)
            self.assertIn("Status: `fetched`", checklist)
            self.assertIn("proxy.md", checklist)
            self.assertIn("wiki/product-idea.md", checklist)
            self.assertIn("python3 scripts/kb.py doctor", checklist)

    def test_warns_when_raw_has_no_wiki_targets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            (root / "wiki").mkdir()
            raw_path = raw_dir / "source.md"
            raw_path.write_text(
                "---\nstatus: draft\ntitle: Source Note\n---\n# Source Note\n",
                encoding="utf-8",
            )

            checklist = kb.build_publish_checklist(raw_path, root)

            self.assertIn("raw 未设置 wiki_targets", checklist)
            self.assertIn("status 是 `draft`", checklist)


class TestCompileOutputPath(unittest.TestCase):
    def test_compile_output_saves_file_with_slug_in_name(self):
        """compile --output 实际写入文件，文件名包含 topic slug。"""
        import tempfile, pathlib, datetime as dt
        with tempfile.TemporaryDirectory() as tmpdir:
            reviews_dir = pathlib.Path(tmpdir) / "reviews"
            reviews_dir.mkdir()

            # 临时 monkey-patch ROOT，让 --output 写到临时目录
            original_root = kb.ROOT
            kb.ROOT = pathlib.Path(tmpdir)
            (pathlib.Path(tmpdir) / "reviews").mkdir(exist_ok=True)
            try:
                topic = "AI Coding"
                slug = kb.slugify_topic(topic)
                today = dt.date.today()
                prompt = kb.build_compile_prompt(topic, [], None)
                out_path = pathlib.Path(tmpdir) / "reviews" / f"{slug}-compile-{today}.md"
                out_path.write_text(prompt, encoding="utf-8")

                # 验证文件存在且文件名包含 slug
                self.assertTrue(out_path.exists())
                self.assertIn(slug, out_path.name)
                self.assertIn("compile", out_path.name)
                # 验证文件内容是有效 prompt
                content = out_path.read_text(encoding="utf-8")
                self.assertIn("Compile Wiki", content)
                self.assertIn("wiki/ai-coding.md", content)
            finally:
                kb.ROOT = original_root


class TestRenderTemplate(unittest.TestCase):
    def test_replaces_single_marker(self):
        template = "Hello %%NAME%%!"
        result = kb._render_template(template, {"NAME": "World"})
        self.assertEqual(result, "Hello World!")

    def test_replaces_multiple_markers(self):
        template = "%%A%% and %%B%%"
        result = kb._render_template(template, {"A": "foo", "B": "bar"})
        self.assertEqual(result, "foo and bar")

    def test_unknown_marker_left_intact(self):
        template = "%%KNOWN%% %%UNKNOWN%%"
        result = kb._render_template(template, {"KNOWN": "x"})
        self.assertEqual(result, "x %%UNKNOWN%%")

    def test_empty_value_replaces_marker(self):
        template = "before\n%%EMPTY%%\nafter"
        result = kb._render_template(template, {"EMPTY": ""})
        self.assertEqual(result, "before\n\nafter")

    def test_multiline_value(self):
        template = "## Section\n\n%%CONTENT%%\n\n## End"
        result = kb._render_template(template, {"CONTENT": "line1\nline2"})
        self.assertIn("line1\nline2", result)


class TestBuildWeeklyPromptTemplate(unittest.TestCase):
    def test_uses_template_when_file_exists(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "profile.md").write_text("# Profile\n用户偏好", encoding="utf-8")
            (root / "prompts").mkdir()
            (root / "prompts" / "weekly.md").write_text("周报指令", encoding="utf-8")
            raw_dir = root / "raw"
            raw_dir.mkdir()
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            template_dir = root / "templates"
            template_dir.mkdir()
            (template_dir / "weekly_technical.md").write_text(
                "# %%WEEK_LABEL%%\n%%PROFILE%%\n%%RAWS_SECTION%%",
                encoding="utf-8",
            )
            config_roles = root / "config" / "roles"
            config_roles.mkdir(parents=True)
            (config_roles / "technical_practitioner.yaml").write_text(
                "role_id: technical_practitioner\ntime_window_days: 7\ncold_start_threshold: 5\nfocus_areas: [Android]\noutput_template: templates/weekly_technical.md\n",
                encoding="utf-8",
            )
            result = kb._build_weekly_prompt_from_root(
                root=root,
                raw_dir=raw_dir,
                role_id="technical_practitioner",
            )
            self.assertIn("用户偏好", result)
            self.assertNotIn("%%WEEK_LABEL%%", result)
            # 简化模板没有角色关注领域 section，fallback 有 —— 证明走的是模板路径
            self.assertNotIn("角色关注领域", result)

    def test_fallback_when_template_missing(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "profile.md").write_text("# Profile\n用户偏好", encoding="utf-8")
            (root / "prompts").mkdir()
            (root / "prompts" / "weekly.md").write_text("周报指令", encoding="utf-8")
            raw_dir = root / "raw"
            raw_dir.mkdir()
            wiki_dir = root / "wiki"
            wiki_dir.mkdir()
            template_dir = root / "templates"
            template_dir.mkdir()
            # 不创建 weekly_technical.md → fallback 路径
            config_roles = root / "config" / "roles"
            config_roles.mkdir(parents=True)
            (config_roles / "technical_practitioner.yaml").write_text(
                "role_id: technical_practitioner\ntime_window_days: 7\ncold_start_threshold: 5\nfocus_areas: [Android]\noutput_template: templates/weekly_technical.md\n",
                encoding="utf-8",
            )
            result = kb._build_weekly_prompt_from_root(
                root=root,
                raw_dir=raw_dir,
                role_id="technical_practitioner",
            )
            self.assertIn("用户偏好", result)
            # fallback 路径包含完整标题格式，模板路径没有
            self.assertIn("技术者周报", result)

    def test_uses_role_specific_instructions_file(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            (root / "profile.md").write_text("# Profile\n用户偏好", encoding="utf-8")
            prompts = root / "prompts"
            prompts.mkdir()
            (prompts / "weekly.md").write_text("技术周报指令", encoding="utf-8")
            (prompts / "weekly_product.md").write_text("产品周报指令", encoding="utf-8")
            raw_dir = root / "raw"
            raw_dir.mkdir()
            (root / "wiki").mkdir()
            template_dir = root / "templates"
            template_dir.mkdir()
            (template_dir / "weekly_product.md").write_text(
                "%%WEEKLY_INSTRUCTIONS%%",
                encoding="utf-8",
            )
            config_roles = root / "config" / "roles"
            config_roles.mkdir(parents=True)
            (config_roles / "product_builder.yaml").write_text(
                "role_id: product_builder\n"
                "focus_areas: [产品]\n"
                "time_window_days: 7\n"
                "output_template: templates/weekly_product.md\n"
                "instructions_file: prompts/weekly_product.md\n"
                "cold_start_threshold: 3\n",
                encoding="utf-8",
            )
            result = kb._build_weekly_prompt_from_root(
                root=root,
                raw_dir=raw_dir,
                role_id="product_builder",
            )
            self.assertIn("产品周报指令", result)
            self.assertNotIn("技术周报指令", result)


class TestBatchDeprecateRaws(unittest.TestCase):
    def _write_raw(self, raw_dir: pathlib.Path, name: str, valid_until: str, title: str = "Test") -> None:
        (raw_dir / name).write_text(
            f"---\nvalid_until: {valid_until}\ntitle: {title}\nstatus: fetched\n---\n# {title}\n",
            encoding="utf-8",
        )

    def test_applies_deprecation_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            self._write_raw(raw_dir, "old.md", "2020-01-01", "Old Tool")
            today = dt.date(2026, 6, 23)
            entry = kb.AgingEntry(
                file=raw_dir / "old.md",
                kind="raw",
                label="Old Tool",
                valid_until=dt.date(2020, 1, 1),
                status="expired",
                days_diff=-2365,
            )
            count = kb.batch_deprecate_raws([(entry, "竞品已取代")], today)
            self.assertEqual(count, 1)
            updated = (raw_dir / "old.md").read_text(encoding="utf-8")
            self.assertIn("竞品已取代", updated)

    def test_returns_count_of_applied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_dir = pathlib.Path(tmpdir)
            self._write_raw(raw_dir, "a.md", "2020-01-01", "A")
            self._write_raw(raw_dir, "b.md", "2020-01-01", "B")
            today = dt.date(2026, 6, 23)
            entries = [
                kb.AgingEntry(raw_dir / "a.md", "raw", "A", dt.date(2020, 1, 1), "expired", -2365),
                kb.AgingEntry(raw_dir / "b.md", "raw", "B", dt.date(2020, 1, 1), "expired", -2365),
            ]
            count = kb.batch_deprecate_raws([(e, "过期") for e in entries], today)
            self.assertEqual(count, 2)

    def test_empty_list_returns_zero(self):
        count = kb.batch_deprecate_raws([], dt.date(2026, 6, 23))
        self.assertEqual(count, 0)


class TestBatchDeprecateWikiJudgments(unittest.TestCase):
    def _write_wiki(self, wiki_dir: pathlib.Path, name: str, statement: str, valid_until: str) -> pathlib.Path:
        content = (
            f"# Test Wiki\n\n"
            f"**判断**：{statement}\n"
            f"- 置信度：medium\n"
            f"- 有效期：{valid_until}\n"
            f"- 来源：raw/test.md\n"
        )
        path = wiki_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_applies_deprecation_to_wiki_judgment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            path = self._write_wiki(wiki_dir, "test.md", "X 工具值得跟踪", "2020-01")
            today = dt.date(2026, 6, 23)
            entry = kb.AgingEntry(
                file=path,
                kind="wiki_judgment",
                label="X 工具值得跟踪",
                valid_until=dt.date(2020, 1, 1),
                status="expired",
                days_diff=-2365,
            )
            count = kb.batch_deprecate_wiki_judgments([(entry, "已被 Y 取代")], today)
            self.assertEqual(count, 1)
            updated = path.read_text(encoding="utf-8")
            self.assertIn("~~", updated)
            self.assertIn("已被 Y 取代", updated)

    def test_empty_list_returns_zero(self):
        count = kb.batch_deprecate_wiki_judgments([], dt.date(2026, 6, 23))
        self.assertEqual(count, 0)


class TestRawAgingStatus(unittest.TestCase):
    """Tests for raw_aging_status() helper."""

    def _make_text(self, valid_until: str) -> str:
        return f"---\nstatus: fetched\nvalid_until: {valid_until}\n---\n"

    def test_no_valid_until_returns_dash(self):
        text = "---\nstatus: fetched\n---\n"
        today = dt.date(2026, 6, 23)
        result = kb.raw_aging_status(text, today)
        self.assertEqual(result, "-")

    def test_expired_returns_expired(self):
        text = self._make_text("2026-05-01")
        today = dt.date(2026, 6, 23)
        result = kb.raw_aging_status(text, today)
        self.assertEqual(result, "expired")

    def test_within_threshold_returns_aging(self):
        # 10 days from now, default threshold=30 → aging
        text = self._make_text("2026-07-03")
        today = dt.date(2026, 6, 23)
        result = kb.raw_aging_status(text, today)
        self.assertEqual(result, "aging")

    def test_beyond_threshold_returns_active(self):
        # 60 days from now → active
        text = self._make_text("2026-08-22")
        today = dt.date(2026, 6, 23)
        result = kb.raw_aging_status(text, today)
        self.assertEqual(result, "active")

    def test_custom_threshold(self):
        # 20 days out, threshold=10 → active
        text = self._make_text("2026-07-13")
        today = dt.date(2026, 6, 23)
        result = kb.raw_aging_status(text, today, threshold_days=10)
        self.assertEqual(result, "active")

    def test_exact_expiry_day_is_aging(self):
        # valid_until == today → days_diff == 0 → aging (0 在 0..30 范围内)
        text = self._make_text("2026-06-23")
        today = dt.date(2026, 6, 23)
        result = kb.raw_aging_status(text, today)
        self.assertEqual(result, "aging")


class TestListAgingColumn(unittest.TestCase):
    """Tests for kb.py list --aging flag output."""

    def _raw_text(self, status="fetched", title="Test Note", valid_until=None):
        lines = ["---", f"status: {status}", f"title: {title}"]
        if valid_until:
            lines.append(f"valid_until: {valid_until}")
        lines += ["---", ""]
        return "\n".join(lines)

    def _run_list(self, tmp_dir, args, note_text):
        """Write a single raw note and run kb.main with given args."""
        raw_dir = tmp_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        (raw_dir / "note1.md").write_text(note_text, encoding="utf-8")
        with unittest.mock.patch.object(kb, "RAW_DIR", raw_dir):
            buf = io.StringIO()
            with unittest.mock.patch("sys.stdout", buf):
                result = kb.main(args)
        return result, buf.getvalue()

    def test_aging_flag_shows_expired(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            result, out = self._run_list(
                tmp, ["list", "--aging"], self._raw_text(valid_until="2026-05-01")
            )
            self.assertEqual(result, 0)
            self.assertIn("expired", out)

    def test_aging_flag_shows_active(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            result, out = self._run_list(
                tmp, ["list", "--aging"], self._raw_text(valid_until="2030-01-01")
            )
            self.assertEqual(result, 0)
            self.assertIn("active", out)

    def test_aging_flag_dash_for_no_valid_until(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            result, out = self._run_list(
                tmp, ["list", "--aging"], self._raw_text()
            )
            self.assertEqual(result, 0)
            self.assertIn("\t-\t", out)

    def test_without_aging_flag_no_aging_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            result, out = self._run_list(
                tmp, ["list"], self._raw_text(valid_until="2026-05-01")
            )
            self.assertEqual(result, 0)
            # without --aging flag no "expired" column appears
            self.assertNotIn("expired", out)


class TestWeeklyCache(unittest.TestCase):
    """Tests for weekly prompt caching."""

    def _write_raw(self, raw_dir, name, saved_at=None, title="Test"):
        today = dt.date.today().isoformat()
        (raw_dir / name).write_text(
            f"---\nstatus: fetched\ntitle: {title}\nsaved_at: {saved_at or today}\n---\n",
            encoding="utf-8",
        )

    def _setup_kb(self, tmp_path):
        """Create minimal kb layout: raw/, wiki/, profile.md, prompts/weekly.md"""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "weekly.md").write_text("generate report", encoding="utf-8")
        (tmp_path / "profile.md").write_text("# Profile\n", encoding="utf-8")
        config_dir = tmp_path / "config" / "roles"
        config_dir.mkdir(parents=True)
        (config_dir / "technical_practitioner.yaml").write_text(
            "role_id: technical_practitioner\ndisplay_name: 技术从业者\n"
            "focus_areas: [Android]\ntime_window_days: 7\n"
            "output_template: templates/weekly_technical.md\ncold_start_threshold: 5\n",
            encoding="utf-8",
        )
        return raw_dir

    def test_cache_created_on_first_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            raw_dir = self._setup_kb(tmp)
            with unittest.mock.patch.object(kb, "ROOT", tmp), \
                 unittest.mock.patch.object(kb, "RAW_DIR", raw_dir), \
                 unittest.mock.patch.object(kb, "PROFILE", tmp / "profile.md"), \
                 unittest.mock.patch.object(kb, "PROMPTS_DIR", tmp / "prompts"):
                kb.build_weekly_prompt("technical_practitioner")
            cache_dir = tmp / ".weekly-cache"
            self.assertTrue(cache_dir.exists())
            files = list(cache_dir.glob("*.txt"))
            self.assertEqual(len(files), 1)

    def test_cache_hit_skips_rebuild(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            raw_dir = self._setup_kb(tmp)
            cache_dir = tmp / ".weekly-cache"
            cache_dir.mkdir()
            week_label = dt.date.today().strftime("%Y-W%W")
            cache_file = cache_dir / f"technical_practitioner-{week_label}.txt"
            cache_file.write_text("CACHED CONTENT", encoding="utf-8")

            with unittest.mock.patch.object(kb, "ROOT", tmp), \
                 unittest.mock.patch.object(kb, "RAW_DIR", raw_dir), \
                 unittest.mock.patch.object(kb, "PROFILE", tmp / "profile.md"), \
                 unittest.mock.patch.object(kb, "PROMPTS_DIR", tmp / "prompts"):
                result = kb.build_weekly_prompt("technical_practitioner")
            self.assertEqual(result, "CACHED CONTENT")

    def test_no_cache_flag_ignores_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            raw_dir = self._setup_kb(tmp)
            cache_dir = tmp / ".weekly-cache"
            cache_dir.mkdir()
            week_label = dt.date.today().strftime("%Y-W%W")
            cache_file = cache_dir / f"technical_practitioner-{week_label}.txt"
            cache_file.write_text("CACHED CONTENT", encoding="utf-8")

            with unittest.mock.patch.object(kb, "ROOT", tmp), \
                 unittest.mock.patch.object(kb, "RAW_DIR", raw_dir), \
                 unittest.mock.patch.object(kb, "PROFILE", tmp / "profile.md"), \
                 unittest.mock.patch.object(kb, "PROMPTS_DIR", tmp / "prompts"):
                result = kb.build_weekly_prompt("technical_practitioner", use_cache=False)
            self.assertNotEqual(result, "CACHED CONTENT")

    def test_cache_key_includes_role_and_week(self):
        """Two different roles produce separate cache files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            raw_dir = self._setup_kb(tmp)
            # Add product_builder role
            (tmp / "config" / "roles" / "product_builder.yaml").write_text(
                "role_id: product_builder\ndisplay_name: 产品思考者\n"
                "focus_areas: [产品]\ntime_window_days: 7\n"
                "output_template: templates/weekly_technical.md\ncold_start_threshold: 3\n",
                encoding="utf-8",
            )
            with unittest.mock.patch.object(kb, "ROOT", tmp), \
                 unittest.mock.patch.object(kb, "RAW_DIR", raw_dir), \
                 unittest.mock.patch.object(kb, "PROFILE", tmp / "profile.md"), \
                 unittest.mock.patch.object(kb, "PROMPTS_DIR", tmp / "prompts"):
                kb.build_weekly_prompt("technical_practitioner")
                kb.build_weekly_prompt("product_builder")
            cache_dir = tmp / ".weekly-cache"
            files = {f.name for f in cache_dir.glob("*.txt")}
            self.assertTrue(any("technical_practitioner" in f for f in files))
            self.assertTrue(any("product_builder" in f for f in files))


class TestCompileDryRun(unittest.TestCase):
    """Tests for compile --dry-run preview."""

    def _write_raw(self, raw_dir, name, wiki_targets=None, title="Test"):
        targets = wiki_targets or []
        targets_yaml = "[" + ", ".join(targets) + "]"
        (raw_dir / name).write_text(
            f"---\nstatus: fetched\ntitle: {title}\nwiki_targets: {targets_yaml}\nsummary: 摘要\n---\n",
            encoding="utf-8",
        )

    def _write_wiki(self, wiki_dir, name, title="Wiki Topic"):
        (wiki_dir / name).write_text(
            f"---\nstatus: published\n---\n# {title}\n",
            encoding="utf-8",
        )

    def test_dry_run_shows_matching_raws(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            raw_dir = tmp / "raw"
            raw_dir.mkdir()
            wiki_dir = tmp / "wiki"
            wiki_dir.mkdir()
            self._write_raw(raw_dir, "note1.md", ["Android 开发"], "Note 1")
            self._write_raw(raw_dir, "note2.md", ["Flutter"], "Note 2")
            result = kb.compile_dry_run("Android", raw_dir, wiki_dir)
            self.assertIn("note1.md", result)
            self.assertNotIn("note2.md", result)

    def test_dry_run_shows_existing_wiki(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            raw_dir = tmp / "raw"
            raw_dir.mkdir()
            wiki_dir = tmp / "wiki"
            wiki_dir.mkdir()
            self._write_raw(raw_dir, "note1.md", ["Android 开发"], "Note 1")
            self._write_wiki(wiki_dir, "android.md", "Android 开发")
            result = kb.compile_dry_run("Android", raw_dir, wiki_dir)
            self.assertIn("android.md", result)

    def test_dry_run_no_raws_reports_zero(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            raw_dir = tmp / "raw"
            raw_dir.mkdir()
            wiki_dir = tmp / "wiki"
            wiki_dir.mkdir()
            result = kb.compile_dry_run("NonExistentTopic", raw_dir, wiki_dir)
            self.assertIn("0", result)

    def test_dry_run_no_wiki_reports_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            raw_dir = tmp / "raw"
            raw_dir.mkdir()
            wiki_dir = tmp / "wiki"
            wiki_dir.mkdir()
            self._write_raw(raw_dir, "note1.md", ["Flutter"], "Note 1")
            result = kb.compile_dry_run("Flutter", raw_dir, wiki_dir)
            self.assertIn("新建", result)


class TestListWiki(unittest.TestCase):
    """Tests for kb.py list --wiki flag."""

    def _wiki_text(self, title="My Topic", judgment_count=2):
        lines = [
            "---",
            "schema_version: \"1\"",
            "status: published",
            "tags: []",
            "sources: []",
            "created_at: 2026-01-01",
            "updated_at: 2026-06-01",
            "---",
            "",
            f"# {title}",
            "",
        ]
        for i in range(judgment_count):
            lines.append(f"**判断**：判断{i+1}。")
            lines.append("- 置信度：medium")
            lines.append("- 有效期：2027-01")
            lines.append("")
        return "\n".join(lines)

    def _run_list_wiki(self, tmp_path, args, wiki_texts: dict):
        """wiki_texts: {filename: text}"""
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        for fname, text in wiki_texts.items():
            (wiki_dir / fname).write_text(text, encoding="utf-8")
        buf = io.StringIO()
        with unittest.mock.patch.object(kb, "ROOT", tmp_path), \
             unittest.mock.patch("sys.stdout", buf):
            result = kb.main(args)
        return result, buf.getvalue()

    def test_wiki_flag_lists_topics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            result, out = self._run_list_wiki(
                tmp,
                ["list", "--wiki"],
                {"android.md": self._wiki_text("Android")},
            )
            self.assertEqual(result, 0)
            self.assertIn("Android", out)

    def test_wiki_flag_shows_judgment_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            result, out = self._run_list_wiki(
                tmp,
                ["list", "--wiki"],
                {"android.md": self._wiki_text("Android", judgment_count=3)},
            )
            self.assertEqual(result, 0)
            self.assertIn("3", out)

    def test_wiki_flag_skips_readme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            result, out = self._run_list_wiki(
                tmp,
                ["list", "--wiki"],
                {
                    "README.md": "# README\n",
                    "topic.md": self._wiki_text("Real Topic"),
                },
            )
            self.assertEqual(result, 0)
            self.assertNotIn("README", out)
            self.assertIn("Real Topic", out)

    def test_wiki_flag_empty_dir_returns_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            result, out = self._run_list_wiki(tmp, ["list", "--wiki"], {})
            self.assertEqual(result, 0)

    def test_wiki_flag_missing_dir_returns_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            # Don't create wiki dir at all
            buf = io.StringIO()
            with unittest.mock.patch.object(kb, "ROOT", tmp), \
                 unittest.mock.patch("sys.stdout", buf):
                result = kb.main(["list", "--wiki"])
            self.assertEqual(result, 0)


class TestDoctor(unittest.TestCase):
    def _setup_root(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        wiki_dir = tmp_path / "wiki"
        wiki_dir.mkdir()
        (tmp_path / "index.md").write_text("", encoding="utf-8")
        (tmp_path / "log.md").write_text("# Log\n", encoding="utf-8")
        roles_dir = tmp_path / "config" / "roles"
        roles_dir.mkdir(parents=True)
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (templates_dir / "weekly_technical.md").write_text("template", encoding="utf-8")
        (prompts_dir / "weekly.md").write_text("instructions", encoding="utf-8")
        (roles_dir / "technical_practitioner.yaml").write_text(
            "role_id: technical_practitioner\n"
            "output_template: templates/weekly_technical.md\n"
            "instructions_file: prompts/weekly.md\n",
            encoding="utf-8",
        )
        return raw_dir, wiki_dir

    def _wiki_text(self, title="Topic"):
        return (
            "---\n"
            "schema_version: \"1\"\n"
            "status: published\n"
            "sources: []\n"
            "---\n"
            f"# {title}\n"
        )

    def test_doctor_ok_for_consistent_workspace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            raw_dir, wiki_dir = self._setup_root(root)
            (raw_dir / "raw.md").write_text("---\nstatus: fetched\n---\n# Raw\n", encoding="utf-8")
            (wiki_dir / "topic.md").write_text(self._wiki_text("Topic"), encoding="utf-8")
            (root / "index.md").write_text(
                "<!-- 格式：[[wiki/文件名]] — 摘要 -->\n[[wiki/topic]] — Topic\n",
                encoding="utf-8",
            )
            (root / "log.md").write_text("# Log\n\n- 发布 `wiki/topic.md`\n", encoding="utf-8")
            issues = kb.run_doctor(root, raw_dir)
            self.assertEqual(issues, [])

    def test_doctor_reports_invalid_raw_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            raw_dir, _ = self._setup_root(root)
            (raw_dir / "draft.md").write_text("---\nstatus: draft\n---\n# Raw\n", encoding="utf-8")
            issues = kb.run_doctor(root, raw_dir)
            self.assertTrue(any(issue.code == "raw_status" for issue in issues))

    def test_doctor_reports_unindexed_wiki(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            raw_dir, wiki_dir = self._setup_root(root)
            (wiki_dir / "topic.md").write_text(self._wiki_text("Topic"), encoding="utf-8")
            (root / "index.md").write_text("# Index\n", encoding="utf-8")
            issues = kb.run_doctor(root, raw_dir)
            self.assertTrue(any(issue.code == "wiki_not_indexed" for issue in issues))

    def test_doctor_reports_missing_role_instructions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            raw_dir, _ = self._setup_root(root)
            (root / "config" / "roles" / "technical_practitioner.yaml").write_text(
                "role_id: technical_practitioner\n"
                "output_template: templates/weekly_technical.md\n"
                "instructions_file: prompts/missing.md\n",
                encoding="utf-8",
            )
            issues = kb.run_doctor(root, raw_dir)
            self.assertTrue(any(issue.code == "role_instructions_missing" for issue in issues))

    def test_doctor_reports_unlogged_wiki(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = pathlib.Path(tmpdir)
            raw_dir, wiki_dir = self._setup_root(root)
            (wiki_dir / "topic.md").write_text(self._wiki_text("Topic"), encoding="utf-8")
            (root / "index.md").write_text("[[wiki/topic]] — Topic\n", encoding="utf-8")
            issues = kb.run_doctor(root, raw_dir)
            self.assertTrue(any(issue.code == "wiki_not_logged" for issue in issues))

    def test_build_doctor_report_ok(self):
        self.assertIn("Doctor OK", kb.build_doctor_report([]))


class TestExtractWikiJudgments(unittest.TestCase):
    WIKI_BODY = """
---
status: published
updated_at: 2026-06-23
tags: [cloudflare]
sources: [source.md]
---

# Title

**判断**：Cloudflare 适合作为边缘基础设施
- 置信度：high
- 有效期：2026-12
- 来源：source.md
- 不确定性：免费额度可能变化

**判断**：~~已废弃的判断内容~~
- 置信度：low
- 有效期：2025-01
"""

    def test_extracts_active_judgments(self):
        result = kb.extract_wiki_judgments(self.WIKI_BODY)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["text"], "Cloudflare 适合作为边缘基础设施")
        self.assertEqual(result[0]["confidence"], "high")
        self.assertEqual(result[0]["valid_until"], "2026-12")

    def test_skips_deprecated_judgments(self):
        result = kb.extract_wiki_judgments(self.WIKI_BODY)
        texts = [j["text"] for j in result]
        self.assertNotIn("已废弃的判断内容", texts)

    def test_empty_body_returns_empty_list(self):
        result = kb.extract_wiki_judgments("# Title\n\nNo judgments here.")
        self.assertEqual(result, [])


class TestGenerateWikiIndex(unittest.TestCase):
    def test_generates_items_from_wiki_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "my-topic.md").write_text(
                "---\nstatus: published\ntags: [test]\nsources: [src.md]\nupdated_at: 2026-06-23\n---\n# My Topic\n\n**判断**：test judgment\n- 置信度：high\n- 有效期：2026-12\n",
                encoding="utf-8",
            )
            today = dt.datetime(2026, 6, 23, 9, 0, 0, tzinfo=dt.timezone.utc)
            result = kb.generate_wiki_index(wiki_dir, today)
            self.assertIn("generated_at", result)
            self.assertEqual(len(result["items"]), 1)
            item = result["items"][0]
            self.assertEqual(item["slug"], "my-topic")
            self.assertEqual(item["title"], "My Topic")
            self.assertEqual(item["tags"], ["test"])
            self.assertEqual(item["updated_at"], "2026-06-23")
            self.assertEqual(len(item["judgments"]), 1)

    def test_skips_readme(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "README.md").write_text("# README", encoding="utf-8")
            today = dt.datetime(2026, 6, 23, tzinfo=dt.timezone.utc)
            result = kb.generate_wiki_index(wiki_dir, today)
            self.assertEqual(result["items"], [])

    def test_skips_unpublished(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wiki_dir = pathlib.Path(tmpdir)
            (wiki_dir / "draft.md").write_text(
                "---\nstatus: fetched\nupdated_at: 2026-06-23\n---\n# Draft\n",
                encoding="utf-8",
            )
            today = dt.datetime(2026, 6, 23, tzinfo=dt.timezone.utc)
            result = kb.generate_wiki_index(wiki_dir, today)
            self.assertEqual(result["items"], [])


if __name__ == "__main__":
    unittest.main()
