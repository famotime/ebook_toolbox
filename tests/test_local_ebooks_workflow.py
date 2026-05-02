import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import collect_local_ebooks

from local_ebooks_workflow import (
    classify_list_file,
    extract_previously_copied_books,
    resolve_output_dir,
)


class LocalEbooksWorkflowTests(unittest.TestCase):
    def tearDown(self):
        if hasattr(collect_local_ebooks.search_file, "_file_cache"):
            delattr(collect_local_ebooks.search_file, "_file_cache")

    def test_extract_book_names_cleans_html_entities_and_deduplicates(self):
        content = """
        今日书单
        《<b>三体</b>》
        《三体》
        《 The&nbsp;Pragmatic   Programmer 》
        《Clean/Code》
        """

        book_names = collect_local_ebooks.extract_book_names(content)

        self.assertEqual(
            book_names,
            ["三体", "The Pragmatic Programmer", "Clean Code"],
        )

    def test_resolve_output_dir_uses_single_book_bucket_and_multi_book_stem(self):
        base_output_dir = Path("J:/书单")

        single_book_dir = resolve_output_dir(
            base_output_dir=base_output_dir,
            list_path=Path("D:/lists/一个好书单.md"),
            book_names=["三体"],
            from_clipboard=False,
        )
        multi_book_dir = resolve_output_dir(
            base_output_dir=base_output_dir,
            list_path=Path("D:/lists/年度书单.md"),
            book_names=["三体", "银河帝国"],
            from_clipboard=False,
        )
        clipboard_dir = resolve_output_dir(
            base_output_dir=base_output_dir,
            list_path=Path("D:/lists"),
            book_names=["三体", "银河帝国"],
            from_clipboard=True,
            clipboard_dir_name="科幻合集",
        )

        self.assertEqual(single_book_dir, base_output_dir / "单本好书")
        self.assertEqual(multi_book_dir, base_output_dir / "年度书单")
        self.assertEqual(clipboard_dir, Path("D:/lists") / "科幻合集")

    def test_extract_previously_copied_books_reads_result_section_only(self):
        content = (
            "处理总结：\n"
            "已找到并复制的文件：\n"
            "- 《三体》\n"
            "- 《银河帝国》\n"
            "\n"
            "未找到的文件清单：\n"
            "- 《沙丘》\n"
        )

        previously_copied = extract_previously_copied_books(content)

        self.assertEqual(previously_copied, {"三体", "银河帝国"})

    def test_classify_list_file_distinguishes_processed_existing_and_pending(self):
        processed_file = Path("D:/lists/already_done.md")
        existing_dir_file = Path("D:/lists/年度书单.md")
        pending_file = Path("D:/lists/新书单.md")

        self.assertEqual(
            classify_list_file(
                file_path=processed_file,
                processed_files={str(processed_file)},
                existing_dirs={"年度书单"},
            ),
            "processed",
        )
        self.assertEqual(
            classify_list_file(
                file_path=existing_dir_file,
                processed_files=set(),
                existing_dirs={"年度书单"},
            ),
            "existing_dir",
        )
        self.assertEqual(
            classify_list_file(
                file_path=pending_file,
                processed_files=set(),
                existing_dirs={"年度书单"},
            ),
            "pending",
        )

    def test_process_book_list_directory_uses_explicit_output_dir(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            list_dir = temp_path / "lists"
            search_dir = temp_path / "library"
            output_dir = temp_path / "output"
            list_dir.mkdir()
            search_dir.mkdir()
            output_dir.mkdir()

            list_file = list_dir / "科幻书单.md"
            list_file.write_text("《三体》\n《银河帝国》\n", encoding="utf-8")

            captured_calls = []

            def fake_process_book_list(file_path, search_dir_arg, from_clipboard=False, output_dir=None):
                captured_calls.append(
                    (Path(file_path), Path(search_dir_arg), from_clipboard, Path(output_dir))
                )

            with patch.object(collect_local_ebooks, "process_book_list", side_effect=fake_process_book_list):
                collect_local_ebooks.process_book_list_directory(
                    list_dir=list_dir,
                    search_dir=search_dir,
                    output_dir=output_dir,
                )

            self.assertEqual(len(captured_calls), 1)
            self.assertEqual(captured_calls[0][0], list_file)
            self.assertEqual(captured_calls[0][1], search_dir)
            self.assertFalse(captured_calls[0][2])
            self.assertEqual(captured_calls[0][3], output_dir)
            self.assertTrue((output_dir / "科幻书单" / "科幻书单.md").exists())

    def test_search_file_prefers_extension_priority_then_larger_size(self):
        with TemporaryDirectory() as temp_dir:
            library_dir = Path(temp_dir)
            (library_dir / "三体.pdf").write_bytes(b"pdf")
            (library_dir / "三体.epub").write_bytes(b"epub")
            preferred_epub = library_dir / "三体(修订版).epub"
            preferred_epub.write_bytes(b"epub with more content")

            collect_local_ebooks.generate_file_list(library_dir)

            matched_file = collect_local_ebooks.search_file("三体", library_dir)

            self.assertEqual(Path(matched_file).resolve(), preferred_epub.resolve())
            self.assertTrue((library_dir / "_file_index.sqlite3").exists())
            self.assertFalse((library_dir / "_file_list.txt").exists())

    def test_search_file_uses_regenerated_index_instead_of_stale_cache(self):
        with TemporaryDirectory() as temp_dir:
            library_dir = Path(temp_dir)
            pdf_file = library_dir / "三体.pdf"
            pdf_file.write_bytes(b"pdf")

            collect_local_ebooks.generate_file_list(library_dir)
            first_match = collect_local_ebooks.search_file("三体", library_dir)

            preferred_epub = library_dir / "三体.epub"
            preferred_epub.write_bytes(b"epub with more content")
            collect_local_ebooks.generate_file_list(library_dir)
            second_match = collect_local_ebooks.search_file("三体", library_dir)

            self.assertEqual(Path(first_match).resolve(), pdf_file.resolve())
            self.assertEqual(Path(second_match).resolve(), preferred_epub.resolve())

    def test_process_book_list_skips_copy_when_output_has_same_content_with_different_name(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            library_dir = temp_path / "library"
            output_dir = temp_path / "output"
            list_file = temp_path / "书单.md"
            library_dir.mkdir()
            output_dir.mkdir()

            source_file = library_dir / "三体.epub"
            source_file.write_bytes(b"same-book-content")
            collect_local_ebooks.generate_file_list(library_dir)

            target_dir = output_dir / "单本好书"
            target_dir.mkdir()
            existing_duplicate = target_dir / "三体典藏版.epub"
            existing_duplicate.write_bytes(b"same-book-content")
            list_file.write_text("《三体》", encoding="utf-8")

            collect_local_ebooks.process_book_list(
                list_file=list_file,
                search_dir=library_dir,
                output_dir=output_dir,
            )

            epub_files = list(target_dir.glob("*.epub"))
            self.assertEqual(len(epub_files), 1)
            self.assertEqual(epub_files[0].resolve(), existing_duplicate.resolve())
            result_content = (target_dir / "处理结果.txt").read_text(encoding="utf-8")
            self.assertIn("相同内容", result_content)


if __name__ == "__main__":
    unittest.main()
