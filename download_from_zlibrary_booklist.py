"""
根据 zlibrary Booklist 批量下载电子书
1. 从配置文件读取帐号信息，并登录Zlibrary；
2. 读取剪贴板中的 Zlibrary Booklist 网址，访问对应的书单页面，解析并逐个下载电子书；
3. 将下载的电子书保存到以书单命名的文件夹中；
"""

from pathlib import Path
import json
import time
from lxml import html
import requests
from dataclasses import dataclass
from Zlibrary import Zlibrary
from typing import List, Dict, Optional
from shutil import copy2
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

@dataclass
class ZLibraryConfig:
    """Z-Library配置类"""
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

class BooklistDownloader:
    """Z-Library书单下载器"""

    def __init__(self, booklist_url: str, save_dir: Path = None, local_library_path: Path = None):
        self.booklist_url = booklist_url
        self.save_dir = save_dir or Path("downloads")
        self.local_library_path = local_library_path
        self.local_files_index = {}  # 本地文件索引
        self.config = ZLibraryConfig.load_account_info()
        self.downloaded_books = set()
        self.lock = threading.Lock()  # 添加线程锁
        self.max_workers = 5  # 设置最大并行数

        # 初始化API客户端
        if not self.config.remix_userid or not self.config.remix_userkey:
            raise ValueError("缺少必要的认证信息：remix_userid 和 remix_userkey")

        self.client = Zlibrary(
            remix_userid=self.config.remix_userid,
            remix_userkey=self.config.remix_userkey
        )

        # 获取并显示用户信息
        user_profile = self.client.getProfile()["user"]
        print("\n登录信息:")
        print(f"用户名: {user_profile.get('name', 'N/A')}")
        print(f"邮箱: {user_profile.get('email', 'N/A')}")
        print(f"今日已下载: {user_profile.get('downloads_today', 0)} 本")
        print(f"下载上限: {user_profile.get('downloads_limit', 10)} 本")
        print(f"剩余下载配额: {self.client.getDownloadsLeft()} 本\n")

        # 创建下载目录
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 设置请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        # 如果提供了本地库路径，则建立索引
        if self.local_library_path and self.local_library_path.exists():
            self._build_local_files_index()

    def _build_local_files_index(self):
        """建立本地文件索引"""
        file_list_path = self.local_library_path / '_file_list.txt'

        # 如果索引文件存在且不为空，直接读取
        if file_list_path.exists() and file_list_path.stat().st_size > 0:
            print(f"正在从索引文件读取本地文件库: {file_list_path}，请耐心等待……")
            with file_list_path.open('r', encoding='utf-8') as f:
                for line in f:
                    try:
                        path_str, size, mtime = line.strip().split('|')
                        path = Path(path_str)
                        if path.exists():  # 确认文件仍然存在
                            key = (path.stem, path.suffix.lower())
                            self.local_files_index[key] = path
                    except:
                        continue
            print(f"已读取本地文件索引，共计 {len(self.local_files_index)} 个电子书文件")
            return

        # 如果索引文件不存在或为空，则重新生成
        print(f"正在索引本地文件库: {self.local_library_path}，请耐心等待……")
        files = []
        for ext in ['.epub', '.pdf', '.txt', '.mobi', '.azw3']:  # 支持的文件类型
            try:
                for p in self.local_library_path.rglob(f'*{ext}'):
                    try:
                        if p.is_file():
                            stat = p.stat()
                            files.append(f"{p}|{stat.st_size}|{stat.st_mtime}")
                            key = (p.stem, p.suffix.lower())
                            self.local_files_index[key] = p
                    except (PermissionError, OSError):
                        continue
            except Exception as e:
                print(f"搜索{ext}文件时出错: {e}")
                continue

        # 保存索引文件
        try:
            with file_list_path.open('w', encoding='utf-8') as f:
                f.write('\n'.join(files))
            print("完成本地文件索引，共计找到", len(files), "个电子书文件")
            print(f"索引文件已保存到: {file_list_path}")
        except Exception as e:
            print(f"保存索引文件失败: {e}")

        print(f"本地文件索引完成，共找到 {len(self.local_files_index)} 个文件")

    def _load_downloaded_books(self) -> set:
        """通过扫描目标文件夹获取已下载书籍的清单"""
        downloaded_books = set()
        if self.save_dir.exists():
            # 获取所有文件，不包括目录
            for file_path in self.save_dir.glob('*.*'):
                if file_path.is_file():
                    # 从文件名中提取书名（去掉作者和扩展名部分）
                    filename = file_path.stem
                    book_title = filename.split('-')[0].strip()    # 假设文件名格式为 "书名-作者"
                    downloaded_books.add(book_title)
        return downloaded_books

    def parse_booklist(self) -> List[Dict[str, str]]:
        """解析书单页面，获取书籍信息列表"""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException, NoSuchElementException

            # 配置Chrome选项
            options = webdriver.ChromeOptions()
            options.add_argument('--headless')     # 可临时禁用无头模式来调试
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--ignore-ssl-errors')
            driver = webdriver.Chrome(options=options)

            try:
                # 先登录
                # print("正在登录...")
                # driver.get("https://1lib.sk/")

                # # 设置cookies来实现登录
                # cookies = {
                #     'remix_userid': self.config.remix_userid,
                #     'remix_userkey': self.config.remix_userkey
                # }
                # for name, value in cookies.items():
                #     driver.add_cookie({
                #         'name': name,
                #         'value': value,
                #         'domain': '1lib.sk'  # 确保域名正确
                #     })

                # 加载书单页面
                print("正在加载书单页面...")
                driver.get(self.booklist_url)

                # 等待页面加载完成
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "z-bookcard"))
                )

                # 循环点击"Show more"按钮
                retry_count = 0
                max_retries = 20  # 修改为最多点击20次
                while retry_count < max_retries:
                    try:
                        # 等待"Show more"按钮出现
                        show_more = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "page-load-more"))
                        )

                        if not show_more.is_displayed():
                            print("已加载所有内容")
                            break

                        driver.execute_script("arguments[0].click();", show_more)  # 使用JavaScript点击
                        retry_count += 1  # 增加计数器
                        print(f"{retry_count}/{max_retries}  加载更多书籍...")
                        time.sleep(3)  # 等待加载

                    except TimeoutException:
                        print("没有更多内容需要加载")
                        break
                    except Exception as e:
                        print(f"点击'Show more'按钮时出错: {e}")
                        retry_count += 1
                        time.sleep(2)
                    if retry_count >= max_retries:
                        print(f"达到最大点击次数限制({max_retries}次),继续处理已加载的内容……")

                # 获取完整的页面内容
                page_content = driver.page_source
                tree = html.fromstring(page_content)

                # 获取书单标题并安全处理
                booklist_title = tree.xpath('/html/head/title/text()')
                if booklist_title:
                    # 使用安全的文件名处理方法
                    safe_title = self._safe_filename(booklist_title[0].strip())
                    self.save_dir = self.save_dir / safe_title
                    self.save_dir.mkdir(parents=True, exist_ok=True)
                    # 在设置正确的save_dir后加载已下载书籍列表
                    self.downloaded_books = self._load_downloaded_books()

                # 获取所有书籍
                books = []
                book_elements = tree.xpath('//z-bookcard')

                for element in book_elements:
                    # 提取书籍信息
                    download_path = element.get('download', '')
                    download_url = f"https://1lib.sk{download_path}" if download_path else ""

                    book = {
                        'title': element.xpath('.//div[@slot="title"]/text()')[0].strip(),
                        'author': element.xpath('.//div[@slot="author"]/text()')[0].strip(),
                        'book_id': element.get('id'),
                        'language': element.get('language'),
                        'year': element.get('year'),
                        'format': element.get('extension'),
                        'download_url': download_url
                    }

                    books.append(book)

                return books

            finally:
                driver.quit()

        except Exception as e:
            print(f"解析书单页面失败: {e}")
            return []

    def _get_text(self, element, xpath: str) -> str:
        """安全地获取xpath匹配的文本内容"""
        try:
            result = element.xpath(xpath)
            return result[0].strip() if result else ""
        except Exception:
            return ""

    def download_book(self, book: Dict[str, str]) -> bool:
        """下载单本书籍"""
        try:
            # 检查是否已下载
            if book['title'] in self.downloaded_books:
                print(f"已下载: 《{book['title']}》，跳过")
                return True

            # 构造文件名
            safe_filename = self._safe_filename(f"{book['title']}")
            file_extension = book['format'].lower()

            # 检查本地文件库
            print(f"正在从本地文件库搜索匹配文件《{safe_filename}》……")
            local_key = (safe_filename, f".{file_extension}")
            if local_key in self.local_files_index:
                source_path = self.local_files_index[local_key]
                target_path = self.save_dir / f"{safe_filename}.{file_extension}"

                if not target_path.exists():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    copy2(source_path, target_path)
                    print(f"在本地文件库中找到匹配文件，成功复制: {target_path}\n")
                    self.downloaded_books.add(book['title'])
                    return True
                else:
                    print(f"目标位置已存在文件: {target_path}")
                    return True

            # 如果本地没有找到，继续原有的下载逻辑
            print(f"本地文件库中未找到匹配文件《{safe_filename}》，继续从网络下载……\n")

            # 检查必要的字段
            if not book.get('book_id') or not book.get('title'):
                print(f"错误：缺少必要的书籍信息")
                return False

            # 构造文件名
            safe_filename = self._safe_filename(f"{book['title']}.{book['format'].lower()}")
            file_path = self.save_dir / safe_filename

            # 检查文件是否已存在
            if file_path.exists():
                print(f"文件已存在: {file_path}，跳过")
                return True

            print(f"\n正在搜索书籍信息: 《{book['title']}》(ID: {book['book_id']})")

            # 通过search API获取完整书籍信息
            search_results = self.client.search(book['title'], extensions=[book['format']])

            # 检查search_results的结构
            if not search_results or 'books' not in search_results:
                print(f"搜索失败：未找到相关书籍")
                return False

            # 在搜索结果中查找匹配的book_id
            book_detail = None
            for result in search_results['books']:
                if str(result.get('id')) == str(book['book_id']) or str(result.get('title')) == str(book['title']):
                    book_detail = result
                    break

            if not book_detail:
                print(f"未找到匹配的书籍信息")
                return False

            print(f"正在下载: 《{book_detail['title']}》 ({book_detail['extension']})")

            # 使用API下载图书
            filename, content = self.client.downloadBook(book_detail)
            if not content:
                print(f"下载失败: 《{book_detail['title']}》")
                return False

            # 保存文件
            with file_path.open('wb') as f:
                f.write(content)

            print(f"下载成功: {file_path}\n")

            return True

        except requests.exceptions.RequestException as e:
            print(f"网络请求错误: {str(e)}")
            return False
        except KeyboardInterrupt:
            print("\n用户中断下载")
            raise
        except Exception as e:
            print(f"下载图书时出错: {str(e)}")
            print(f"错误类型: {type(e).__name__}")
            return False

    def _safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        # 替换不安全的字符
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        # 限制文件名长度
        if len(filename.encode('utf-8')) > 240:  # 留出一些空间给路径
            filename = filename[:80] + '...' + filename[-10:]
        return filename

    def run(self):
        """运行下载流程"""
        # 检查下载配额
        downloads_left = self.client.getDownloadsLeft()
        print(f"\n当前剩余下载配额: {downloads_left}")
        if downloads_left <= 0:
            print("下载配额已用完，终止操作")
            return

        # 解析书单
        print(f"正在解析书单: {self.booklist_url}")
        books = self.parse_booklist()
        if not books:
            print("未找到任何图书信息")
            return

        print(f"找到 {len(books)} 本图书")

        # 统计信息
        total = len(books)
        success = 0
        failed = 0

        # 使用线程池进行并行下载
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有下载任务
            future_to_book = {
                executor.submit(self.download_book, book): book
                for book in books
                if book['title'] not in self.downloaded_books
            }

            # 处理完成的任务
            for future in as_completed(future_to_book):
                book = future_to_book[future]
                try:
                    if future.result():
                        with self.lock:
                            success += 1
                    else:
                        with self.lock:
                            failed += 1
                except Exception as e:
                    print(f"下载《{book['title']}》时发生错误: {e}")
                    with self.lock:
                        failed += 1

                # 检查剩余配额
                downloads_left = self.client.getDownloadsLeft()
                if downloads_left <= 0:
                    print(f"\n下载配额已用完，停止后续下载")
                    break

        # 输出统计信息
        print("\n下载完成!")
        print(f"总计: {total} 本")
        print(f"成功: {success} 本")
        print(f"失败: {failed} 本")
        print(f"下载目录: {self.save_dir}")
        print(f"剩余下载配额: {self.client.getDownloadsLeft()}")

def process_booklists_from_clipboard(save_dir: Path, base_url: str = "https://1lib.sk", local_library_path: Path = None):
    """从剪贴板获取书单链接并处理下载"""
    clipboard_content = pyperclip.paste()

    # 处理每一行内容
    raw_urls = [line.strip() for line in clipboard_content.split('\n') if line.strip()]
    urls = []

    for raw_url in raw_urls:
        # 如果是完整URL
        if raw_url.startswith(('http://', 'https://')):
            if urlparse(raw_url).netloc.endswith('lib.sk'):
                urls.append(raw_url)
        # 如果是相对路径（以/开头）
        elif raw_url.startswith('/'):
            urls.append(urljoin(base_url, raw_url))
        # 如果不包含/，则跳过
        elif '/' not in raw_url:
            continue
        # 如果是纯路径（不以/开头）
        else:
            urls.append(urljoin(base_url, '/' + raw_url))

    if not urls:
        print("剪贴板中未找到有效的zlibrary书单链接")
        print("请复制书单链接到剪贴板后重试")
        print("支持的格式：")
        print("1. 完整URL：https://1lib.sk/booklist/...")
        print("2. 相对路径：/booklist/...")
        print("3. 纯路径：booklist/...")
        exit(1)

    print(f"找到 {len(urls)} 个书单链接:")
    for i, url in enumerate(urls, 1):
        print(f"{i}. {url}")

    # 逐个处理书单
    for i, booklist_url in enumerate(urls, 1):
        print(f"\n处理第 {i}/{len(urls)} 个书单:")
        print(f"URL: {booklist_url}")
        try:
            downloader = BooklistDownloader(booklist_url, save_dir, local_library_path)
            # 检查下载配额
            downloads_left = downloader.client.getDownloadsLeft()
            if downloads_left <= 0:
                print("下载配额已用完，终止操作")
                break
            downloader.run()
        except KeyboardInterrupt:
            print("\n用户中断下载")
            break
        except Exception as e:
            print(f"处理书单时出错: {e}")
            continue

        # 书单间添加延时
        if i < len(urls):
            print("\n等待10秒后处理下一个书单...")
            time.sleep(10)

    print("\n所有书单处理完成!")

if __name__ == "__main__":
    import pyperclip
    from urllib.parse import urlparse, urljoin

    save_dir = Path(r"J:\zlibrary_booklists")
    local_library_path = Path(r"J:")  # 设置本地文件库路径
    BASE_URL = "https://1lib.sk"

    # 从剪贴板读取书单链接
    process_booklists_from_clipboard(save_dir, BASE_URL, local_library_path)