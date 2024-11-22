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
                print(f"未找到: 《{book_name}》")
                return None

            # 获取搜索结果中文件名包含书名的图书
            found_book = None
            for book in results["books"]:
                if book_name.lower() in book['title'].lower():
                    found_book = book
                    break

            if not found_book:
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
                print(f"下载失败: 《{book_name}》")
                self.update_result_file(book_name, success=False)
                return None

            # 直接保存到目标目录
            file_path = self.config.target_dir / filename
            with file_path.open('wb') as f:
                f.write(content)

            # 更新结果文件，传入实际的文件名
            self.update_result_file(book_name, success=True, filename=filename)
            return file_path

        except Exception as e:
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
    # 指定要搜索的根目录
    root_dir = Path("J:/书单")

    # 从配置文件加载账号信息
    config = ZLibraryConfig.load_account_info()

    # 查找所有处理结果文件
    result_files = find_result_files(root_dir)
    print(f"找到 {len(result_files)} 个处理结果文件")

    # 逐个处理每个结果文件
    for result_file in result_files:
        print(f"\n开始处理目录: {result_file.parent}")

        # 更新配置
        config.result_file = result_file
        config.target_dir = result_file.parent

        try:
            # 创建下载器并运行
            downloader = ZLibraryDownloader(config)
            downloader.run()
        except Exception as e:
            print(f"处理 {result_file} 时出错: {e}")
            continue

        print(f"完成处理: {result_file}")
        # 在处理不同目录之间添加较长的延时
        time.sleep(5)