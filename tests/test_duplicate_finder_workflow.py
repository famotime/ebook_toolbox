import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from duplicate_finder_workflow import (
    FileInfoRecord,
    format_duplicate_report,
    generate_index_name,
    parse_checked_paths_from_report,
    select_preferred_file,
)
from find_duplicated_files import DuplicateFinder


class DuplicateFinderWorkflowTests(unittest.TestCase):
    def test_generate_index_name_replaces_illegal_chars_and_hashes_long_paths(self):
        short_name = generate_index_name(Path("H:/个人图片及视频"))
        long_path = Path("H:/" + "/".join(["very_long_directory_name"] * 10))
        long_name = generate_index_name(long_path)

        self.assertNotIn(":", short_name)
        self.assertNotIn("/", short_name)
        self.assertEqual(long_name, hashlib.md5(str(long_path.resolve()).encode("utf-8")).hexdigest())

    def test_select_preferred_file_honors_exclude_include_and_path_length(self):
        files = [
            FileInfoRecord(path=Path("H:/待整理/a.jpg"), size=1, name="a.jpg"),
            FileInfoRecord(path=Path("H:/归档/精选/a.jpg"), size=1, name="a.jpg"),
            FileInfoRecord(path=Path("H:/归档/a.jpg"), size=1, name="a.jpg"),
        ]

        selected = select_preferred_file(
            files=files,
            include_path="归档",
            exclude_path="待整理",
            shortest_path=True,
        )

        self.assertEqual(selected, Path("H:/归档/a.jpg"))

    def test_format_duplicate_report_marks_kept_and_duplicate_files(self):
        report = format_duplicate_report(
            root_dir=Path("H:/个人图片及视频"),
            duplicates={
                "H:/keep/a.jpg": [Path("H:/dup/a.jpg"), Path("H:/dup2/a.jpg")],
            },
            generated_at="2026-04-04 12:00:00",
        )

        self.assertIn("# 重复文件报告", report)
        self.assertIn("- [ ] H:/keep/a.jpg", report)
        self.assertIn(r"- [x] H:\dup\a.jpg", report)
        self.assertIn(r"- [x] H:\dup2\a.jpg", report)
        self.assertIn("---", report)

    def test_parse_checked_paths_from_report_only_returns_selected_lines(self):
        report = (
            "# 重复文件报告\n\n"
            "- [ ] H:/keep/a.jpg\n"
            "- [x] H:/dup/a.jpg\n"
            "- [x] H:/dup2/a.jpg\n"
        )

        checked_paths = parse_checked_paths_from_report(report)

        self.assertEqual(checked_paths, ["H:/dup/a.jpg", "H:/dup2/a.jpg"])

    def test_duplicate_finder_detects_same_content_even_when_filenames_differ(self):
        with TemporaryDirectory() as temp_dir:
            root_dir = Path(temp_dir)
            kept_file = root_dir / "归档" / "a.txt"
            duplicate_file = root_dir / "待整理" / "b.txt"
            kept_file.parent.mkdir()
            duplicate_file.parent.mkdir()
            kept_file.write_bytes(b"same-content")
            duplicate_file.write_bytes(b"same-content")

            finder = DuplicateFinder(root_dir, rebuild_index=True)
            duplicates = finder.find_duplicates(
                compare_content=True,
                include_path="归档",
                recursive=True,
            )

            self.assertEqual(duplicates, {str(kept_file.resolve()): [duplicate_file.resolve()]})


if __name__ == "__main__":
    unittest.main()
