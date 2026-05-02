"""
电子书批量处理脚本：
1. 先在本地搜索电子书并整理到指定目录
2. 对于本地未找到的书籍，从Z-Library下载
"""

from pathlib import Path
import time
from collect_local_ebooks import (
    process_book_list_directory, check_file_list_update, generate_file_list,
    retry_missing_local_books, extract_book_names, process_book_list, clean_dirname,
)
from download_ebooks_from_zlibrary import main as download_from_zlibrary
from local_ebooks_workflow import SINGLE_BOOK_DIRNAME


def process_ebooks(list_dir: str | Path, search_dir: str | Path, output_dir: str | Path,
                   skip_index_update: bool = False, clipboard_content: str | None = None):
    """
    处理电子书收集和下载

    Args:
        list_dir: 书单文件所在目录
        search_dir: 本地电子书搜索目录
        output_dir: 输出目录
        skip_index_update: 是否跳过索引更新
        clipboard_content: 剪贴板书单内容，非空时从该内容提取书名而非读取目录
    """
    # 转换为Path对象
    list_dir = Path(list_dir)
    search_dir = Path(search_dir)
    output_dir = Path(output_dir)

    print("="*50)
    print("第一步：搜索本地电子书")
    print("="*50)

    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / SINGLE_BOOK_DIRNAME).mkdir(exist_ok=True)

    # 检查是否需要更新文件索引
    if not skip_index_update:
        if check_file_list_update(search_dir):
            generate_file_list(search_dir)
    else:
        print("已跳过索引更新（使用历史索引）")

    # 处理本地电子书
    if clipboard_content:
        print("从剪贴板内容中提取书名...")
        book_names = extract_book_names(clipboard_content)
        if book_names:
            first_line = clipboard_content.splitlines()[0].strip() if clipboard_content.splitlines() else "剪贴板书单"
            dir_name = clean_dirname(first_line)
            print(f"从剪贴板提取到 {len(book_names)} 本书，目录名：{dir_name}")
            process_book_list(output_dir / "书单", search_dir, from_clipboard=True,
                              output_dir=output_dir, clipboard_content=clipboard_content)
        else:
            print("剪贴板中未找到《》标记的书名，跳过本地搜索")

        # 剪贴板模式到此结束，不执行后续的目录补偿和Z-Library下载
        print("\n处理完成！")
        print(f"剪贴板书单已处理到：{output_dir}")
        return

    # 目录模式：处理本地书单文件
    process_book_list_directory(list_dir, search_dir, output_dir=output_dir)

    print("\n"+"="*50)
    print("补偿步骤：重试本地搜索和Z-Library补漏")
    print("="*50)

    # 再次扫描并补偿之前因各种原因未找到的本地书籍
    retry_missing_local_books(output_dir, search_dir)

    # 清理Z-Library的断点记录缓存，保证之前记录为未找到的书会在这里重新进行搜索下载
    progress_file = output_dir / "download_progress.json"
    if progress_file.exists():
        try:
            progress_file.unlink()
        except Exception as e:
            pass

    print("\n"+"="*50)
    print("第二步：从Z-Library下载未找到的电子书")
    print("="*50)

    # 从Z-Library下载未找到的电子书
    download_from_zlibrary(output_dir)

    print("\n处理完成！")
    print(f"所有电子书已整理到：{output_dir}")


if __name__ == "__main__":
    # 配置路径
    LIST_DIR = Path(r"D:\Python_Work\Wiznotes_tools\wiznotes\豆瓣2024榜单\split_level_2")  # 书单文件目录
    SEARCH_DIR = Path(r"J:")  # 本地电子书库路径
    OUTPUT_DIR = Path(r"J:\2024年豆瓣读书榜单")  # 输出目录

    try:
        process_ebooks(
            list_dir=LIST_DIR,
            search_dir=SEARCH_DIR,
            output_dir=OUTPUT_DIR
        )
    except KeyboardInterrupt:
        print("\n用户中断处理")
    except Exception as e:
        print(f"\n处理过程中出错: {e}")
