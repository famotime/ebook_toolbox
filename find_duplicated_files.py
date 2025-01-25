"""
查找重复文件：
1. 在指定目录及子目录查找重复文件；
    - 重复条件：文件名称和大小完全相同的文件，或者文件内容相同；
    - 优先读取磁盘文件索引并根据索引查找重复文件；
    - 如果未找到索引文件则先建立磁盘索引文件，再查找重复文件；
2. 按指定规则选择其中的一个或多个重复文件；
    - 文件路径包含或不包含指定名称的文件；（设置参数）
    - 文件路径最短或最长的路径；（设置参数）
3. 将发现的重复文件包含按上述规则选定的完整文件路径，输出到一个Markdown文本文件，待删除不保留的文件为选中状态，示例如下：
```
- [x] H:\个人图片及视频\temp\待整理\1.jpg
- [x] H:\个人图片及视频\temp\123\1.jpg
- [ ] H:\个人图片及视频\temp\123\123\1.jpg
```
"""

from pathlib import Path
import json
from typing import Dict, List, Set, Tuple, Union
from dataclasses import dataclass
import hashlib
from datetime import datetime

@dataclass
class FileInfo:
    path: Path
    size: int
    name: str

class DuplicateFinder:
    def __init__(self, root_dir: str, rebuild_index: bool = False):
        """初始化查重器

        Args:
            root_dir: 要搜索的根目录
            rebuild_index: 是否强制重建索引
        """
        self.root_dir = Path(root_dir).resolve()  # 转换为绝对路径

        # 创建output目录
        self.output_dir = Path(__file__).parent / "output"
        self.output_dir.mkdir(exist_ok=True)

        # 生成索引文件名：使用目录的完整路径生成唯一标识
        index_name = self._generate_index_name(self.root_dir)
        self.index_file = self.output_dir / f"file_index_{index_name}.json"

        self.file_index: Dict[str, List[FileInfo]] = {}
        if rebuild_index:
            self._rebuild_index()

    def _generate_index_name(self, path: Path) -> str:
        """根据完整路径生成索引文件名

        将路径转换为合法的文件名，保持唯一性
        """
        # 获取规范化的绝对路径
        full_path = str(path.resolve())

        # 替换非法字符
        # 将盘符中的冒号替换为下划线
        # 将路径分隔符替换为下划线
        # 移除其他可能的非法字符
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            full_path = full_path.replace(char, '_')

        # 如果文件名过长，使用哈希值缩短
        if len(full_path) > 100:
            import hashlib
            hash_obj = hashlib.md5(full_path.encode('utf-8'))
            return hash_obj.hexdigest()

        return full_path

    def _rebuild_index(self) -> None:
        """强制重建索引"""
        print(f"正在重建索引文件：{self.index_file}")
        self.file_index.clear()
        if self.index_file.exists():
            self.index_file.unlink()
        self.build_file_index()
        self.save_index()

    def build_file_index(self, recursive: bool = True) -> None:
        """建立文件索引
        按文件名称和大小建立索引，key格式为：'文件名_文件大小'
        """
        print("正在建立文件索引...")
        total_files = 0

        # 根据recursive参数选择搜索方法
        search_method = self.root_dir.rglob if recursive else self.root_dir.glob

        for file_path in search_method("*"):
            if file_path.is_file():
                try:
                    file_stat = file_path.stat()
                    file_info = FileInfo(
                        path=file_path,
                        size=file_stat.st_size,
                        name=file_path.name
                    )
                    key = f"{file_info.name}_{file_info.size}"
                    if key not in self.file_index:
                        self.file_index[key] = []
                    self.file_index[key].append(file_info)
                    total_files += 1
                    if total_files % 1000 == 0:  # 每处理1000个文件显示一次进度
                        print(f"已处理 {total_files} 个文件...")
                except (PermissionError, OSError) as e:
                    print(f"无法访问文件 {file_path}: {e}")

        print(f"文件索引建立完成，共处理 {total_files} 个文件")

    def save_index(self) -> None:
        """保存索引到文件，同时记录索引的目录路径"""
        index_data = {
            "root_dir": str(self.root_dir),
            "last_update": datetime.now().isoformat(),
            "files": {
                k: [(str(f.path), f.size, f.name) for f in v]
                for k, v in self.file_index.items()
            }
        }

        with self.index_file.open('w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
        print(f"索引已保存到：{self.index_file}")

    def load_index(self) -> bool:
        """从文件加载索引，验证索引是否匹配当前搜索目录"""
        if not self.index_file.exists():
            return False

        try:
            with self.index_file.open('r', encoding='utf-8') as f:
                data = json.load(f)

            # 验证索引文件是否匹配当前搜索目录
            if data.get("root_dir") != str(self.root_dir):
                print("索引文件与当前搜索目录不匹配")
                return False

            self.file_index = {
                k: [FileInfo(Path(p), s, n) for p, s, n in v]
                for k, v in data["files"].items()
            }

            print(f"已加载索引文件：{self.index_file}")
            print(f"索引更新时间：{data.get('last_update', '未知')}")
            return True

        except Exception as e:
            print(f"加载索引文件失败：{e}")
            return False

    def find_duplicates(
        self,
        include_path: Union[str, List[str]] = None,
        exclude_path: Union[str, List[str]] = None,
        shortest_path: bool = True,
        compare_content: bool = True,
        recursive: bool = True,
        rebuild_index: bool = False
    ) -> Dict[str, List[Path]]:
        """查找重复文件

        Args:
            include_path: 要包含的路径关键词或关键词列表
            exclude_path: 要排除的路径关键词或关键词列表
            shortest_path: True表示保留最短路径，False表示保留最长路径
            compare_content: True表示比较文件内容，False仅比较文件名和大小
            recursive: True表示递归搜索子目录，False仅搜索当前目录
            rebuild_index: True表示强制重建索引
        """
        print(f"开始在目录 {self.root_dir} 中查找重复文件...")

        # 处理索引
        if rebuild_index:
            self._rebuild_index()
        elif not self.file_index:
            if not self.load_index():
                print("未找到匹配的索引文件，开始建立新索引...")
                self.build_file_index(recursive)
                self.save_index()
            else:
                print(f"使用现有索引文件：{self.index_file}")

        duplicates = {}
        total_groups = 0
        duplicate_files = 0

        # 首先找出文件名和大小相同的文件组
        for key, files in self.file_index.items():
            if len(files) > 1:  # 只处理有重复的文件组
                # 验证文件是否仍然存在，并根据recursive参数过滤
                existing_files = [
                    f for f in files
                    if f.path.exists() and (recursive or len(f.path.parents) <= len(self.root_dir.parents))
                ]

                if len(existing_files) > 1:
                    if compare_content:
                        # 根据内容进一步分组
                        file_groups = self._group_by_content(existing_files)
                        for group in file_groups:
                            if len(group) > 1:  # 确认内容也相同
                                total_groups += 1
                                duplicate_files += len(group) - 1
                                selected = self._select_file(group, include_path, exclude_path, shortest_path)
                                duplicates[str(selected)] = [f.path for f in group if f.path != selected]
                    else:
                        # 仅按文件名和大小分组
                        total_groups += 1
                        duplicate_files += len(existing_files) - 1
                        selected = self._select_file(existing_files, include_path, exclude_path, shortest_path)
                        duplicates[str(selected)] = [f.path for f in existing_files if f.path != selected]

        print(f"查找完成！发现 {total_groups} 组重复文件，共 {duplicate_files} 个重复文件")
        if not compare_content:
            print("注意：当前仅按文件名和大小比较，未验证文件内容是否相同")
        return duplicates

    def _group_by_content(self, files: List[FileInfo]) -> List[List[FileInfo]]:
        """根据文件内容分组

        使用MD5哈希值验证文件内容是否相同
        """
        content_groups: Dict[str, List[FileInfo]] = {}
        for file_info in files:
            try:
                file_hash = self._calculate_file_hash(file_info.path)
                if file_hash not in content_groups:
                    content_groups[file_hash] = []
                content_groups[file_hash].append(file_info)
            except (PermissionError, OSError) as e:
                print(f"无法读取文件 {file_info.path}: {e}")

        return list(content_groups.values())

    def _calculate_file_hash(self, file_path: Path, chunk_size: int = 8192) -> str:
        """计算文件哈希值"""
        hasher = hashlib.md5()
        with file_path.open('rb') as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _select_file(self, files: List[FileInfo], include_path: Union[str, List[str]] = None,
                    exclude_path: Union[str, List[str]] = None, shortest_path: bool = True) -> Path:
        """选择要保留的文件

        Args:
            files: 重复文件列表
            include_path: 要包含的路径关键词或关键词列表
            exclude_path: 要排除的路径关键词或关键词列表
            shortest_path: True表示保留最短路径，False表示保留最长路径
        """
        candidates = files.copy()

        # 转换输入为列表格式
        exclude_paths = [exclude_path] if isinstance(exclude_path, str) else exclude_path
        include_paths = [include_path] if isinstance(include_path, str) else include_path

        # 首先应用排除规则
        if exclude_paths:
            candidates = [f for f in candidates
                        if not any(ep in str(f.path) for ep in exclude_paths if ep)]
            if candidates:  # 如果还有文件剩余，就从这些文件中选择
                files = candidates

        # 然后应用包含规则
        if include_paths:
            included = [f for f in files
                       if any(ip in str(f.path) for ip in include_paths if ip)]
            if included:  # 如果找到符合包含规则的文件，就从这些文件中选择
                files = included

        paths = [f.path for f in files]
        return min(paths, key=lambda p: len(str(p))) if shortest_path else max(paths, key=lambda p: len(str(p)))

    def export_to_markdown(self, duplicates: Dict[str, List[Path]], output_file: str = None) -> None:
        """导出重复文件信息到Markdown文件

        Args:
            duplicates: 重复文件信息
            output_file: 输出文件名，如果为None则自动生成
        """
        if output_file is None:
            # 使用目录名和时间戳生成输出文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"duplicates_{self.root_dir.name}_{timestamp}.md"

        output_path = self.output_dir / output_file

        with output_path.open('w', encoding='utf-8') as f:
            f.write("# 重复文件报告\n\n")
            f.write(f"搜索目录: {self.root_dir}\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for kept_file, duplicate_files in duplicates.items():
                # 保留文件标记为未选中
                f.write(f"- [ ] {kept_file}\n")
                # 重复文件标记为选中（待删除）
                for dup in duplicate_files:
                    f.write(f"- [x] {dup}\n")
                f.write("\n---\n\n")

        print(f"报告已保存到：{output_path}")

if __name__ == "__main__":
    paths_to_check = r"H:\个人图片及视频"

    print(f"\n处理目录：{paths_to_check}")
    finder = DuplicateFinder(paths_to_check)

    duplicates = finder.find_duplicates(
        compare_content=False, # True表示比较文件内容，False仅比较文件名和大小
        recursive=True, # True表示递归搜索子目录，False仅搜索当前目录
        rebuild_index=False, # True表示强制重建索引
        include_path=[], # 要包含的路径关键词（待保留文件所在目录）
        exclude_path=["待整理"], # 要排除的路径关键词(优先删除文件所在目录)
        shortest_path=False, # True表示保留最短路径文件，False表示保留最长路径文件
    )

    finder.export_to_markdown(duplicates)