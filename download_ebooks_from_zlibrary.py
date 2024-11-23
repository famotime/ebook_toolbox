"""
从ZLibrary批量下载电子书：
1. 在指定根目录下搜索所有的"处理结果.txt"文件；
2. 从每个"处理结果.txt"中读取未找到的文件清单；
3. 使用ZLibrary API搜索并下载epub格式的电子书；
4. 将下载的文件保存到对应的"处理结果.txt"所在目录；
5. 更新每个"处理结果.txt"的内容，移除已下载图书。

注意：
- 需要提供ZLibrary的账号信息（支持email/password或remix token认证）
- 自动处理每日下载限制
- 包含请求延时以避免频繁访问
"""

from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime
import time
from Zlibrary import Zlibrary
import json

@dataclass
class ZLibraryConfig:
    target_dir: Path = Path("ebooks")
    result_file: Path = Path("处理结果.txt")
    # 移除email和password字段，只保留remix token相关字段
    remix_userid: str = ""
    remix_userkey: str = ""

    @classmethod
    def load_account_info(cls, config_path: Path = None):
        """从配置文件加载账号信息，并获取remix token"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "account" / "web_accounts.json"

        try:
            with config_path.open('r', encoding='utf-8') as f:
                accounts = json.load(f)
                zlibrary_account = accounts.get("zlibrary", {})

                # 如果配置中有email和password，则先获取remix token
                if zlibrary_account.get("email") and zlibrary_account.get("password"):
                    temp_client = Zlibrary(
                        email=zlibrary_account["email"],
                        password=zlibrary_account["password"]
                    )
                    profile = temp_client.getProfile()["user"]
                    return cls(
                        remix_userid=str(profile["id"]),
                        remix_userkey=profile["remix_userkey"]
                    )

                # 否则直接使用配置中的remix token
                return cls(
                    remix_userid=zlibrary_account.get("remix_userid", ""),
                    remix_userkey=zlibrary_account.get("remix_userkey", "")
                )
        except Exception as e:
            print(f"读取账号配置文件失败: {e}")
            return cls()

@dataclass
class DownloadStats:
    total_files: int = 0
    processed_files: int = 0
    total_books: int = 0
    downloaded_books: int = 0
    failed_books: int = 0
    last_processed_file: str = ""
    start_time: str = ""

    def save_progress(self, progress_file: Path):
        """保存进度到文件"""
        with progress_file.open('w', encoding='utf-8') as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load_progress(cls, progress_file: Path):
        """从文件加载进度"""
        if not progress_file.exists():
            return cls(start_time=datetime.now().isoformat())
        try:
            with progress_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
                return cls(**data)
        except Exception as e:
            print(f"加载进度文件失败: {e}")
            return cls(start_time=datetime.now().isoformat())

class ZLibraryDownloader:
    def __init__(self, config: ZLibraryConfig = None, stats: DownloadStats = None):
        self.config = config or ZLibraryConfig()
        self.stats = stats or DownloadStats()

        # 确保目标目录存在
        self.config.target_dir.mkdir(exist_ok=True)

        # 初始化API客户端，只使用remix token认证
        if not self.config.remix_userid or not self.config.remix_userkey:
            raise ValueError("缺少必要的认证信息：remix_userid 和 remix_userkey")

        self.client = Zlibrary(
            remix_userid=self.config.remix_userid,
            remix_userkey=self.config.remix_userkey
        )

    def read_missing_books(self):
        """读取处理结果文件中未找到的书籍清单"""
        if not self.config.result_file.exists():
            return []

        missing_books = []
        is_missing_section = False
        with self.config.result_file.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line == "未找到的文件清单：":
                    is_missing_section = True
                    continue
                if is_missing_section and line.startswith("- "):
                    book_name = line[2:].strip('《》')
                    missing_books.append(book_name)
                elif is_missing_section and line == "":
                    break
        return missing_books

    def search_and_download_book(self, book_name: str):
        """搜索并下载图书"""
        try:
            # 搜索图书
            results = self.client.search(message=book_name, extensions=["epub"])
            if not results.get("books"):
                print(f"未找到: 《{book_name}》")
                return None

            # 获取搜索结果中文件名包含书名的图书
            found_book = None
            for book in results["books"]:
                if book_name.lower() in book['title'].lower():
                    found_book = book
                    break

            if not found_book:
                self.stats.failed_books += 1
                print(f"未找到: 《{book_name}》")
                return None

            print(f"找到: 《{found_book['title']}》 by {found_book.get('author', '未知作者')}")

            # 检查剩余下载次数
            downloads_left = self.client.getDownloadsLeft()
            print(f"今日剩余下载次数: {downloads_left}")
            if downloads_left <= 0:
                print("今日下载次数已用完")
                return None

            # 下载图书
            filename, content = self.client.downloadBook(found_book)
            if not content:
                self.stats.failed_books += 1
                print(f"下载失败: 《{book_name}》")
                return None

            # 直接保存到目标目录
            file_path = self.config.target_dir / filename
            with file_path.open('wb') as f:
                f.write(content)

            # 更新结果文件，传入实际的文件名
            self.update_result_file(book_name, success=True, filename=filename)
            self.stats.downloaded_books += 1
            return file_path

        except Exception as e:
            self.stats.failed_books += 1
            print(f"处理图书时出错: {e}")
            self.update_result_file(book_name, success=False)
            return None

    def update_result_file(self, book_name: str, success: bool, filename: str = None):
        """更新处理结果文件"""
        with self.config.result_file.open('r', encoding='utf-8') as f:
            lines = f.readlines()

        new_lines = []
        found_section = False
        missing_section = False
        skip_next_line = False

        for line in lines:
            if skip_next_line:
                skip_next_line = False
                continue

            # 检查是否进入"已找到并复制的文件："部分
            if line.strip() == "已找到并复制的文件：":
                found_section = True
                new_lines.append(line)
                if success:
                    new_lines.append(f"- 《{book_name}》 -> {filename} \n")
                continue

            # 检查是否进入"未找到的文件清单："部分
            if line.strip() == "未找到的文件清单：":
                missing_section = True
                new_lines.append(line)
                continue

            # 如果在未找到部分且当前行是要处理的书名，跳过该行
            if missing_section and line.strip() == f"- 《{book_name}》":
                continue

            new_lines.append(line)

        with self.config.result_file.open('w', encoding='utf-8') as f:
            f.writelines(new_lines)

    def run(self):
        """运行下载流程"""
        missing_books = self.read_missing_books()
        print(f"找到 {len(missing_books)} 本待下载的图书")

        for book_name in missing_books:
            print(f"\n正在处理: 《{book_name}》")

            # 搜索并下载
            file_path = self.search_and_download_book(book_name)
            if not file_path:
                continue

            print(f"成功下载到: {file_path}")

            # 添加延时避免请求过于频繁
            time.sleep(2)

def find_result_files(root_dir: Path) -> list[Path]:
    """搜索指定目录及子目录下的所有处理结果文件"""
    return list(root_dir.rglob("处理结果.txt"))

if __name__ == "__main__":
    root_dir = Path("J:/书单")
    progress_file = root_dir / "download_progress.json"

    # 加载进度
    stats = DownloadStats.load_progress(progress_file)
    config = ZLibraryConfig.load_account_info()

    # 查找所有处理结果文件
    result_files = find_result_files(root_dir)
    stats.total_files = len(result_files)
    print(f"找到 {stats.total_files} 个处理结果文件")

    # 从上次处理的文件继续
    if stats.last_processed_file:
        start_index = next((i for i, f in enumerate(result_files)
                          if str(f) == stats.last_processed_file), 0)
        result_files = result_files[start_index:]

    for result_file in result_files:
        print(f"\n开始处理目录: {result_file.parent}")
        stats.last_processed_file = str(result_file)

        config.result_file = result_file
        config.target_dir = result_file.parent

        try:
            downloader = ZLibraryDownloader(config, stats)
            missing_books = downloader.read_missing_books()
            stats.total_books += len(missing_books)
            downloader.run()
            stats.processed_files += 1
        except Exception as e:
            print(f"处理 {result_file} 时出错: {e}")
            continue
        finally:
            # 保存进度
            stats.save_progress(progress_file)

        print(f"完成处理: {result_file}")
        time.sleep(5)

    # 打印最终统计信息
    print("\n下载任务完成，统计如下：")
    print(f"处理文件数: {stats.processed_files}/{stats.total_files}")
    print(f"下载成功: {stats.downloaded_books} 本")
    print(f"下载失败: {stats.failed_books} 本")
    print(f"总计图书: {stats.total_books} 本")
    print(f"开始时间: {stats.start_time}")
    print(f"结束时间: {datetime.now().isoformat()}")