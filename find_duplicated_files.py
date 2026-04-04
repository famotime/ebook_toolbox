"""
查找重复文件：
1. 在指定目录及子目录查找重复文件；
2. 优先使用统一的 SQLite 文件索引；
3. 比较内容时按 size -> quick hash -> full hash 逐层收敛；
4. 导出 Markdown 报告供后续删除。
"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Union
from datetime import datetime

from duplicate_finder_workflow import (
    FileInfoRecord as FileInfo,
    format_duplicate_report,
    select_preferred_file,
)
from library_index import (
    IndexedFileRecord,
    ensure_hashes_for_paths,
    generate_file_index,
    get_index_db_path,
    load_index_records,
)


class DuplicateFinder:
    def __init__(self, root_dir: str | Path, rebuild_index: bool = False):
        self.root_dir = Path(root_dir).resolve()
        self.output_dir = Path(__file__).parent / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.index_file = get_index_db_path(self.root_dir)
        self.file_index: list[IndexedFileRecord] = []
        if rebuild_index:
            self._rebuild_index()

    def _rebuild_index(self) -> None:
        print(f"正在重建索引文件：{self.index_file}")
        generate_file_index(self.root_dir, allowed_extensions=None)
        self.file_index = load_index_records(self.root_dir, allowed_extensions=None)

    def build_file_index(self, recursive: bool = True) -> None:
        print("正在建立文件索引...")
        generate_file_index(self.root_dir, allowed_extensions=None, recursive=recursive)
        self.file_index = load_index_records(self.root_dir, allowed_extensions=None)
        print(f"文件索引建立完成，共处理 {len(self.file_index)} 个文件")

    def load_index(self) -> bool:
        records = load_index_records(self.root_dir, allowed_extensions=None)
        if not records:
            return False
        self.file_index = records
        print(f"已加载索引文件：{self.index_file}")
        return True

    def find_duplicates(
        self,
        include_path: Union[str, List[str]] = None,
        exclude_path: Union[str, List[str]] = None,
        shortest_path: bool = True,
        compare_content: bool = True,
        recursive: bool = True,
        rebuild_index: bool = False,
    ) -> Dict[str, List[Path]]:
        print(f"开始在目录 {self.root_dir} 中查找重复文件...")

        if rebuild_index:
            self._rebuild_index()
        elif not self.file_index:
            if not self.load_index():
                print("未找到匹配的索引文件，开始建立新索引...")
                self.build_file_index(recursive=recursive)
            else:
                print(f"使用现有索引文件：{self.index_file}")

        existing_files = [
            record for record in self.file_index
            if record.path.exists() and (recursive or record.path.parent == self.root_dir)
        ]

        duplicate_groups = (
            self._group_by_content(existing_files)
            if compare_content
            else self._group_by_name_and_size(existing_files)
        )

        duplicates: Dict[str, List[Path]] = {}
        total_groups = 0
        duplicate_files = 0

        for group in duplicate_groups:
            if len(group) <= 1:
                continue
            total_groups += 1
            duplicate_files += len(group) - 1
            selected = self._select_file(group, include_path, exclude_path, shortest_path)
            duplicates[str(selected)] = [record.path for record in group if record.path != selected]

        print(f"查找完成！发现 {total_groups} 组重复文件，共 {duplicate_files} 个重复文件")
        if not compare_content:
            print("注意：当前仅按文件名和大小比较，未验证文件内容是否相同")
        return duplicates

    def _group_by_name_and_size(self, files: List[IndexedFileRecord]) -> List[List[IndexedFileRecord]]:
        groups: dict[tuple[str, int], list[IndexedFileRecord]] = defaultdict(list)
        for file_info in files:
            groups[(file_info.name, file_info.size)].append(file_info)
        return [group for group in groups.values() if len(group) > 1]

    def _group_by_content(self, files: List[IndexedFileRecord]) -> List[List[IndexedFileRecord]]:
        size_groups: dict[int, list[IndexedFileRecord]] = defaultdict(list)
        for file_info in files:
            size_groups[file_info.size].append(file_info)

        content_groups: list[list[IndexedFileRecord]] = []
        for same_size_files in size_groups.values():
            if len(same_size_files) <= 1:
                continue

            quick_hashes = ensure_hashes_for_paths(
                self.root_dir,
                [file_info.path for file_info in same_size_files],
                include_full_hash=False,
            )
            quick_groups: dict[str, list[IndexedFileRecord]] = defaultdict(list)
            for file_info in same_size_files:
                quick_groups[quick_hashes[file_info.path.resolve()][0]].append(file_info)

            for same_quick_files in quick_groups.values():
                if len(same_quick_files) <= 1:
                    continue

                full_hashes = ensure_hashes_for_paths(
                    self.root_dir,
                    [file_info.path for file_info in same_quick_files],
                    include_full_hash=True,
                )
                full_groups: dict[str, list[IndexedFileRecord]] = defaultdict(list)
                for file_info in same_quick_files:
                    full_groups[full_hashes[file_info.path.resolve()][1]].append(file_info)
                content_groups.extend(group for group in full_groups.values() if len(group) > 1)

        return content_groups

    def _select_file(
        self,
        files: List[IndexedFileRecord],
        include_path: Union[str, List[str]] = None,
        exclude_path: Union[str, List[str]] = None,
        shortest_path: bool = True,
    ) -> Path:
        return select_preferred_file(
            [
                FileInfo(path=file_info.path, size=file_info.size, name=file_info.name)
                for file_info in files
            ],
            include_path=include_path,
            exclude_path=exclude_path,
            shortest_path=shortest_path,
        )

    def export_to_markdown(self, duplicates: Dict[str, List[Path]], output_file: str = None) -> None:
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"duplicates_{self.root_dir.name}_{timestamp}.md"

        output_path = self.output_dir / output_file

        with output_path.open("w", encoding="utf-8") as file_handle:
            file_handle.write(format_duplicate_report(self.root_dir, duplicates))

        print(f"报告已保存到：{output_path}")


if __name__ == "__main__":
    paths_to_check = r"H:\个人图片及视频"

    print(f"\n处理目录：{paths_to_check}")
    finder = DuplicateFinder(paths_to_check)

    duplicates = finder.find_duplicates(
        compare_content=False,
        recursive=True,
        rebuild_index=False,
        include_path=[],
        exclude_path=["待整理"],
        shortest_path=False,
    )

    finder.export_to_markdown(duplicates)
