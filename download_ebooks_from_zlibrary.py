"""
从ZLibrary下载电子书：
1. 从"处理结果.txt"中读取未找到的文件清单；
2. 从ZLibrary搜索并下载；
3. 将下载的文件移动到指定目录；
4. 更新"处理结果.txt"。
"""

from pathlib import Path
from dataclasses import dataclass
import time
from Zlibrary import Zlibrary
import json

@dataclass
class ZLibraryConfig:
    target_dir: Path = Path("ebooks")
    result_file: Path = Path("处理结果.txt")
    # Zlibrary登录凭据，默认为空，将从配置文件读取
    email: str = ""
    password: str = ""
    # 或者使用 remix token (推荐)
    remix_userid: str = ""
    remix_userkey: str = ""

    @classmethod
    def load_account_info(cls, config_path: Path = None):
        """从配置文件加载账号信息"""
        if config_path is None:
            config_path = Path(__file__).parent.parent / "account" / "web_accounts.json"

        try:
            with config_path.open('r', encoding='utf-8') as f:
                accounts = json.load(f)
                zlibrary_account = accounts.get("zlibrary", {})
                return cls(
                    email=zlibrary_account.get("email", ""),
                    password=zlibrary_account.get("password", ""),
                    remix_userid=zlibrary_account.get("remix_userid", ""),
                    remix_userkey=zlibrary_account.get("remix_userkey", "")
                )
        except Exception as e:
            print(f"读取账号配置文件失败: {e}")
            return cls()

class ZLibraryDownloader:
    def __init__(self, config: ZLibraryConfig = None):
        self.config = config or ZLibraryConfig()

        # 确保目标目录存在
        self.config.target_dir.mkdir(exist_ok=True)

        # 初始化API客户端
        if self.config.remix_userid and self.config.remix_userkey:
            self.client = Zlibrary(
                remix_userid=self.config.remix_userid,
                remix_userkey=self.config.remix_userkey
            )
        else:
            self.client = Zlibrary(
                email=self.config.email,
                password=self.config.password
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
                print(f"未找到图书: {book_name}")
                return None

            # 获取第一个搜索结果
            book = results["books"][0]
            print(f"找到图书: {book['title']} by {book.get('author', '未知作者')}")

            # 检查剩余下载次数
            downloads_left = self.client.getDownloadsLeft()
            if downloads_left <= 0:
                print("今日下载次数已用完")
                return None

            # 下载图书
            filename, content = self.client.downloadBook(book)
            if not content:
                print(f"下载失败: {book_name}")
                return None

            # 直接保存到目标目录
            file_path = self.config.target_dir / filename
            with file_path.open('wb') as f:
                f.write(content)
            return file_path

        except Exception as e:
            print(f"处理图书时出错: {e}")
            return None

    def update_result_file(self, book_name: str, success: bool):
        """更新处理结果文件"""
        with self.config.result_file.open('r', encoding='utf-8') as f:
            lines = f.readlines()

        with self.config.result_file.open('w', encoding='utf-8') as f:
            for line in lines:
                if not line.strip().endswith(book_name):
                    f.write(line)
            if success:
                f.write(f"已下载: {book_name}\n")
            else:
                f.write(f"下载失败: {book_name}\n")

    def run(self):
        """运行下载流程"""
        missing_books = self.read_missing_books()
        print(f"找到 {len(missing_books)} 本待下载的图书")

        for book_name in missing_books:
            print(f"\n正在处理: {book_name}")

            # 搜索并下载
            file_path = self.search_and_download_book(book_name)
            if not file_path:
                self.update_result_file(book_name, success=False)
                continue

            print(f"成功下载到: {file_path}")
            self.update_result_file(book_name, success=True)

            # 添加延时避免请求过于频繁
            time.sleep(2)

if __name__ == "__main__":
    result_file = Path("J:\书单\死磕这5本散文集！文笔真的可以脱胎换骨！\处理结果.txt")

    # 从配置文件加载账号信息
    config = ZLibraryConfig.load_account_info()
    # 更新其他配置
    config.result_file = result_file
    config.target_dir = result_file.parent

    downloader = ZLibraryDownloader(config)
    downloader.run()