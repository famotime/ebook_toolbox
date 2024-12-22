"""
电子书批量处理脚本：
1. 先在本地搜索电子书并整理到指定目录
2. 对于本地未找到的书籍，从Z-Library下载
"""

from pathlib import Path
import time
import sys
from collect_local_ebooks import process_book_list_directory, check_file_list_update, generate_file_list
from download_ebooks_from_zlibrary import main as download_from_zlibrary


def process_ebooks(list_dir: str | Path, search_dir: str | Path, output_dir: str | Path):
    """
    处理电子书收集和下载

    Args:
        list_dir: 书单文件所在目录
        search_dir: 本地电子书搜索目录
        output_dir: 输出目录
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
    (output_dir / "单本好书").mkdir(exist_ok=True)

    # 设置全局变量 BOOKS_OUTPUT_DIR
    # 这里使用 sys.modules 来修改 collect_local_ebooks 模块中的全局变量
    sys.modules['collect_local_ebooks'].BOOKS_OUTPUT_DIR = output_dir

    # 检查是否需要更新文件索引
    if check_file_list_update(search_dir):
        generate_file_list(search_dir)

    # 处理本地电子书
    process_book_list_directory(list_dir, search_dir)

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
