import unittest
from pathlib import Path

import clean_booknames
import doc2md
import pull_md_images_to_local
import rename_epub_with_catalog


class SmallToolEntrypointTests(unittest.TestCase):
    def test_clean_booknames_parser_accepts_directory_and_index_file(self):
        parser = clean_booknames.build_parser()

        args = parser.parse_args(["--directory", "D:/books", "--index-file", "D:/_file_list.txt"])

        self.assertEqual(args.directory, Path("D:/books"))
        self.assertEqual(args.index_file, Path("D:/_file_list.txt"))

    def test_pull_md_images_parser_accepts_required_markdown_file(self):
        parser = pull_md_images_to_local.build_parser()

        args = parser.parse_args(["--md-file", "D:/notes/article.md"])

        self.assertEqual(args.md_file, Path("D:/notes/article.md"))
        self.assertIsNone(args.image_dir)

    def test_doc2md_resolves_default_output_file_inside_input_directory(self):
        output_path = doc2md.resolve_output_markdown(Path("D:/docs"), None)

        self.assertEqual(output_path, Path("D:/docs/output.md"))

    def test_rename_epub_parser_accepts_multiple_target_directories(self):
        parser = rename_epub_with_catalog.build_parser()

        args = parser.parse_args(["--target-dir", "J:/zlibrary", "K:/ebooks"])

        self.assertEqual(args.target_dirs, [Path("J:/zlibrary"), Path("K:/ebooks")])


if __name__ == "__main__":
    unittest.main()
