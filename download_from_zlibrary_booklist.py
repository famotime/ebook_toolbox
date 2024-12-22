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
import pyperclip
from urllib.parse import urlparse, urljoin
import logging
from datetime import datetime

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

def setup_logging(save_dir: Path) -> logging.Logger:
    """配置日志记录器"""
    # 获取logger
    logger = logging.getLogger('zlibrary_downloader')

    # 如果logger已经有处理器，说明已经配置过，接返回
    if logger.handlers:
        return logger

    # 创建logs目录
    log_dir = save_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    # 生成日志文件名
    log_file = log_dir / f'zlibrary_download_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'

    # 配置日志格式
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 配置logger
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

class BooklistDownloader:
    """Z-Library书单下载器"""

    def __init__(self, booklist_url: str, save_dir: Path = None, local_library_path: Path = None,
                 local_files_index: Dict = None, use_local_index: bool = True):
        self.booklist_url = booklist_url
        self.save_dir = save_dir or Path("downloads")
        self.local_library_path = local_library_path
        self.use_local_index = use_local_index
        self.local_files_index = local_files_index if use_local_index else {}
        self.config = ZLibraryConfig.load_account_info()
        self.downloaded_books = set()
        self.max_workers = 10  # 设置最大并行数
        self.total_books = 0

        # 初始化API客户端
        if not self.config.remix_userid or not self.config.remix_userkey:
            raise ValueError("缺少必要的认证信息：remix_userid 和 remix_userkey")

        self.client = Zlibrary(
            remix_userid=self.config.remix_userid,
            remix_userkey=self.config.remix_userkey
        )

        # 获取并显示用户信息
        user_profile = self.client.getProfile()["user"]
        self.logger = setup_logging(self.save_dir)
        self.logger.info("\n登录信息:")
        self.logger.info(f"用户名: {user_profile.get('name', 'N/A')}")
        self.logger.info(f"邮箱: {user_profile.get('email', 'N/A')}")
        self.logger.info(f"今日已下载: {user_profile.get('downloads_today', 0)} 本")
        self.logger.info(f"下载上限: {user_profile.get('downloads_limit', 10)} 本")
        self.logger.info(f"剩余下载配额: {self.client.getDownloadsLeft()} 本\n")

        # 创建下载目录
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # 设置请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    def _load_downloaded_books(self) -> set:
        """加载已下载的书籍列表"""
        downloaded = set()
        if self.save_dir.exists():
            for ext in ['.epub', '.pdf', '.txt', '.mobi', '.azw3']:
                for file_path in self.save_dir.glob(f'*{ext}'):
                    if file_path.is_file():
                        downloaded.add(file_path.stem)
        return downloaded

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
                # 加载书单页面
                driver.get(self.booklist_url)
                # 等待页面加载完成
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "z-bookcard"))
                )

                try:
                    booklist_title = tree.xpath('/html/head/title/text()')
                    self.logger.info(f"正在加载书单页面: {booklist_title}")
                except Exception as e:
                    self.logger.info(f"正在加载书单页面……")

                # 循环点击"Show more"按钮
                retry_count = 0
                max_retries = 50  # 最大点击次数
                while retry_count < max_retries:
                    try:
                        # 等待"Show more"按钮出现
                        show_more = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "page-load-more"))
                        )

                        if not show_more.is_displayed():
                            self.logger.info("已加载所有内容")
                            break

                        driver.execute_script("arguments[0].click();", show_more)  # 使用JavaScript点击
                        retry_count += 1
                        self.logger.info(f"{retry_count}/{max_retries}  加载更多书籍...")
                        time.sleep(3)  # 等待加载

                    except TimeoutException:
                        self.logger.info("没有更多内容需要加载")
                        break
                    except Exception as e:
                        self.logger.error(f"点击'Show more'按钮时出错: {e}")
                        retry_count += 1
                        time.sleep(2)
                    if retry_count >= max_retries:
                        self.logger.info(f"达到最大点击次数限制({max_retries}次),继续处理已加载的内容……")

                page_content = driver.page_source
                tree = html.fromstring(page_content)

                # 获取书单标题并使用处理后的安全文件名
                booklist_title = tree.xpath('/html/head/title/text()')
                if booklist_title:
                    safe_title = self._safe_filename(booklist_title[0].strip())
                    self.save_dir = self.save_dir / safe_title
                    self.save_dir.mkdir(parents=True, exist_ok=True)
                    self.downloaded_books = self._load_downloaded_books()
                else:
                    self.logger.warning("未能获取到书单标题，使用默认目录名")
                    safe_title = "未命名书单"
                    self.save_dir = self.save_dir / safe_title
                    self.save_dir.mkdir(parents=True, exist_ok=True)
                    self.downloaded_books = self._load_downloaded_books()

                # 获取所有书籍
                books = []
                book_elements = tree.xpath('//z-bookcard')

                if not book_elements:
                    self.logger.warning("未找到任何书籍元素，可能是页面结构发生变化")
                    return []

                for element in book_elements:
                    try:
                        # 提取书籍信息，添加错误处理
                        title = element.xpath('.//div[@slot="title"]/text()')
                        author = element.xpath('.//div[@slot="author"]/text()')

                        if not title or not author:
                            self.logger.warning(f"跳过一本书籍：标题或作者信息不完整")
                            continue

                        download_path = element.get('download', '')
                        download_url = f"https://1lib.sk{download_path}" if download_path else ""

                        book = {
                            'title': title[0].strip(),
                            'author': author[0].strip(),
                            'book_id': element.get('id', ''),
                            'language': element.get('language', ''),
                            'year': element.get('year', ''),
                            'format': element.get('extension', ''),
                            'download_url': download_url
                        }

                        if book['title'] and book['book_id']:  # 确保至少有标题和ID
                            books.append(book)
                        else:
                            self.logger.warning(f"跳过一本书籍：缺少必要信息")

                    except Exception as e:
                        self.logger.warning(f"解析单本书籍信息时出错: {e}")
                        continue

                if not books:
                    self.logger.warning("未能成功解析任何书籍信息")
                else:
                    self.logger.info(f"成功解析 {len(books)} 本书籍信息")

                return books

            finally:
                driver.quit()

        except Exception as e:
            self.logger.error(f"解析书单页面失败: {str(e)}")
            self.logger.debug("错误详情:", exc_info=True)  # 添加详细的错误信息
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
                self.logger.info(f"[{len(self.downloaded_books)}/{self.total_books}] 已下载: 《{book['title']}》，跳过")
                return True

            # 构造文件名
            safe_filename = self._safe_filename(f"{book['title']}")
            file_extension = book['format'].lower()

            # 仅在启用本地索引时进行本地文件搜索
            if self.use_local_index and self.local_files_index:
                # self.logger.info(f"正在从本地文件库搜索匹配文件《{safe_filename}》……")
                local_key = (book['title'], f".{file_extension}") if (book['title'], f".{file_extension}") in self.local_files_index else (safe_filename, f".{file_extension}")
                if local_key in self.local_files_index:
                    # self.logger.info(f"已经在本地文件库中找到匹配文件《{safe_filename}》")
                    source_path = self.local_files_index[local_key]
                    target_path = self.save_dir / f"{local_key[0]}.{local_key[1]}"

                    if not target_path.exists():
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        copy2(source_path, target_path)
                        self.downloaded_books.add(book['title'])
                        self.logger.info(f"\n[{len(self.downloaded_books)}/{self.total_books}] 在本地文件库中找到匹配文件，成功复制: \n{source_path} -> {target_path}\n")
                        return True
                    else:
                        self.logger.info(f"目标位置已存在同名文件: {target_path}，跳过……")
                        return True
            elif not self.use_local_index:
                self.logger.info("已禁用本地文件库搜索，直接进行网络下载...")

            # 如果本地没有找到，继续原有的下载逻辑
            self.logger.info(f"本地文件库中未找到匹配文件《{safe_filename}》，继续从网络下载……")

            # 检查必要的字段
            if not book.get('book_id') or not book.get('title'):
                self.logger.error(f"错误：缺少必要的书籍信息")
                return False

            # 构造文件名
            file_path = self.save_dir / f"{safe_filename}.{file_extension}"

            # 检查文件是否已存在
            if file_path.exists():
                self.logger.info(f"文件已存在: {file_path}，跳过")
                return True

            self.logger.info(f"正在搜索书籍信息: 《{book['title']}》(ID: {book['book_id']})")

            # 通过search API获取完整书籍信息
            book_detail = None

            # 第一次搜索：使用完整书名（包含格式后缀）
            try:
                search_results = self.client.search(book['title'], extensions=[book['format']])

                if search_results and 'books' in search_results:
                    # 优先使用book_id精确匹配
                    for result in search_results['books']:
                        if str(result.get('id')) == str(book['book_id']):
                            book_detail = result
                            break
            except Exception as e:
                self.logger.warning(f"使用完整匹配搜索时出错: {str(e)}")

            # 如果第一次搜索未找到，尝试第二次搜索：仅使用书名
            if not book_detail:
                try:
                    search_results = self.client.search(book['title'])
                    if search_results and 'books' in search_results:
                        # 使用标题匹配
                        for result in search_results['books']:
                            if str(result.get('title')) == str(book['title']):
                                book_detail = result
                                break
                except Exception as e:
                    self.logger.error(f"搜索书籍时出错: {str(e)}")
                    return False

            if not book_detail:
                self.logger.error(f"未找到匹配的书籍信息：《{book['title']}》")
                return False

            self.logger.info(f"正在下载: 《{book_detail['title']}》 ({book_detail['extension']})")

            # 使用API下载图书
            filename, content = self.client.downloadBook(book_detail)
            if not content:
                self.logger.error(f"下载失败: 《{book_detail['title']}》")
                return False

            # 保存文件
            file_path = self.save_dir / f"{safe_filename}.{book_detail['extension']}"
            with file_path.open('wb') as f:
                f.write(content)

            self.downloaded_books.add(book['title'])
            self.logger.info(f"\n\n[{len(self.downloaded_books)}/{self.total_books}] 下载成功: {file_path}\n")

            return True

        except requests.exceptions.RequestException as e:
            self.logger.error(f"网络请求错误: {str(e)}")
            return False
        except KeyboardInterrupt:
            self.logger.info("\n用户中断下载")
            raise
        except Exception as e:
            self.logger.error(f"下载《{book['title']}》时出错: {str(e)}")
            return False

    def _safe_filename(self, filename: str) -> str:
        """生成安全的文件名"""
        # 替换不安全的字符
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        # 限制文件名长度
        if len(filename.encode('utf-8')) > 240:  # 留出一些空间给路径
            filename = filename[:200] + '...' + filename[-10:]
        return filename

    def run(self):
        """运行下载流程"""
        try:
            # 检查下载配额
            downloads_left = self.client.getDownloadsLeft()
            self.logger.info(f"\n当前剩余下载配额: {downloads_left}")
            if downloads_left <= 0:
                self.logger.info("下载配额已用完，终止操作\n")
                return

            # 解析书单
            self.logger.info(f"正在解析书单: {self.booklist_url}")
            books = self.parse_booklist()
            if not books:
                self.logger.info("未找到任何图书信息\n")
                return

            self.total_books = len(books)
            self.logger.info(f"找到 {self.total_books} 本图书")

            # 使用线程池进行并行下载
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 提交所有下载任务
                future_to_book = {
                    executor.submit(self.download_book, book): book
                    for book in books
                    if book['title'] not in self.downloaded_books
                }

                # 处理完成的任务
                try:
                    for future in as_completed(future_to_book):
                        book = future_to_book[future]
                        try:
                            future.result()
                        except Exception as e:
                            self.logger.error(f"下载《{book['title']}》时发生错误: {e}")
                            continue  # 继续处理下一本书

                        # 检查剩余配额
                        downloads_left = self.client.getDownloadsLeft()
                        if downloads_left <= 0:
                            self.logger.info(f"\n下载配额已用完，停止后续下载\n")
                            break
                except Exception as e:
                    self.logger.error(f"处理下载任务时出错: {e}")

            self.logger.info("\n下载完成!")
            self.logger.info(f"总计: {self.total_books} 本")
            self.logger.info(f"成功: {len(self.downloaded_books)} 本")
            self.logger.info(f"失败: {self.total_books - len(self.downloaded_books)} 本")
            self.logger.info(f"下载目录: {self.save_dir}")
            self.logger.info(f"剩余下载配额: {self.client.getDownloadsLeft()}\n")

        except Exception as e:
            self.logger.error(f"运行下载流程时出错: {e}")

def process_booklists_from_clipboard(save_dir: Path, base_url: str = "https://1lib.sk",
                                   local_library_path: Path = None, use_local_index: bool = True):
    """从剪贴板获取书单链接并处理下载"""
    # 添加logger初始化
    logger = setup_logging(save_dir)

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
        logger.error("剪贴板中未找到有效zlibrary书单链接")
        logger.info("请复制书单链接到剪贴板后重试")
        logger.info("支持的格式：")
        logger.info("1. 完整URL：https://1lib.sk/booklist/...")
        logger.info("2. 相对路径：/booklist/...")
        logger.info("3. 纯路径：booklist/...")
        exit(1)

    logger.info(f"找到 {len(urls)} 个书单链接:")
    for i, url in enumerate(urls, 1):
        logger.info(f"{i}. {url}")
    logger.info("")

    # 仅在启用本地索引时构建索引
    local_files_index = {}
    if use_local_index and local_library_path and local_library_path.exists():
        local_files_index = build_local_files_index(local_library_path)
    elif not use_local_index:
        logger.info("已禁用本地文件库索引功能")

    # 逐个处理书单
    for i, booklist_url in enumerate(urls, 1):
        logger.info("-" * 50)
        logger.info(f"处理第 {i}/{len(urls)} 个书单:")
        logger.info(f"URL: {booklist_url}")
        try:
            # 创建下载器时传入已建立的索引
            downloader = BooklistDownloader(
                booklist_url,
                save_dir,
                local_library_path,
                local_files_index=local_files_index,
                use_local_index=use_local_index
            )
            # 检查下载配额
            downloads_left = downloader.client.getDownloadsLeft()
            if downloads_left <= 0:
                logger.info("下载配额已用完，终止操作")
                break
            downloader.run()
        except KeyboardInterrupt:
            logger.info("\n用户中断下载")
            break
        except Exception as e:
            logger.error(f"处理书单时出错: {e}")
            continue

        # 书单间添加延时
        if i < len(urls):
            logger.info("\n等待5秒后处理下一个书单...")
            time.sleep(5)

    logger.info("\n所有书单处理完成!")

def build_local_files_index(local_library_path: Path) -> Dict:
    """建立本地文件索引"""
    logger = logging.getLogger('zlibrary_downloader')
    local_files_index = {}
    file_list_path = local_library_path / '_file_list.txt'

    # 如果索引文件存在且不为空，直接读取
    if file_list_path.exists() and file_list_path.stat().st_size > 0:
        logger.info(f"正在从索引文件读取本地文件库: {file_list_path}，请耐心等待……")
        with file_list_path.open('r', encoding='utf-8') as f:
            for line in f:
                try:
                    path_str, size, mtime = line.strip().split('|')
                    path = Path(path_str)
                    # if path.exists():  # 确认文件仍然存在
                    key = (path.stem, path.suffix.lower())
                    local_files_index[key] = path
                except:
                    continue
        logger.info(f"已读取本地文件索引，共计 {len(local_files_index)} 个电子书文件")
        return local_files_index

    # 如果索引文件不存在或为空，则重新生成
    logger.info(f"正在索引本地文件库: {local_library_path}，请耐心等待……")
    files = []
    # 需要排除的系统文件夹
    exclude_dirs = {'$RECYCLE.BIN', 'System Volume Information', 'Recovery'}
    for ext in ['.epub', '.pdf', '.txt', '.mobi', '.azw3']:  # 支持的文件类型
        try:
            for p in local_library_path.rglob(f'*{ext}'):
                try:
                    # 检查路径中是否包含需要排除的系统文件夹
                    if any(x in p.parts for x in exclude_dirs):
                        continue
                    if p.is_file():
                        stat = p.stat()
                        # 跳过小于10KB的文件
                        if stat.st_size < 10 * 1024:  # 10KB = 10 * 1024 bytes
                            continue
                        files.append(f"{p}|{stat.st_size}|{stat.st_mtime}")
                        key = (p.stem, p.suffix.lower())
                        local_files_index[key] = p
                except (PermissionError, OSError):
                    continue
        except Exception as e:
            logger.error(f"搜索{ext}文件时出错: {e}")
            continue

    # 保存索引文件
    try:
        with file_list_path.open('w', encoding='utf-8') as f:
            f.write('\n'.join(files))
        logger.info("完成本地文件索引，共计找到", len(files), "个电子书文件")
        logger.info(f"索引文件已保存到: {file_list_path}")
    except Exception as e:
        logger.error(f"保存索引文件失败: {e}")

    return local_files_index

if __name__ == "__main__":
    save_dir = Path(r"J:\zlibrary_booklists")
    local_library_path = Path(r"J:")  # 设置本地文件库路径
    BASE_URL = "https://1lib.sk"
    USE_LOCAL_INDEX = True  # 控制是否使用本地索引

    # 从剪贴板读取书单链接
    process_booklists_from_clipboard(
        save_dir,
        BASE_URL,
        local_library_path,
        use_local_index=USE_LOCAL_INDEX
    )