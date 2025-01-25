"""
批量精简电子书文件名中的冗余信息：
1. 遍历指定目录及其所有子目录
2. 查找所有电子书文件（支持的格式：epub、mobi、azw3、pdf、txt）
3. 移除文件名中的"(Z-Library)"及其后续文字
4. 同时更新同目录下"处理结果.txt"文件中的相关记录
"""
from pathlib import Path
import re

def clean_book_filenames(directory=None, index_file=None):
    """批量清理电子书文件名中的冗余信息

    支持两种工作模式：
    1. 目录扫描模式：遍历指定目录及其子目录下的所有电子书文件
    2. 索引文件模式：根据索引文件中记录的文件路径进行处理

    Args:
        directory (Path|str|None): 要处理的目录路径。如果为None，则仅使用索引文件模式
        index_file (Path|str|None): 索引文件路径。如果为None，则仅使用目录扫描模式

    """
    if not directory and not index_file:
        raise ValueError("必须提供目录路径或索引文件路径其中之一")

    stats = {
        'total_files': 0,
        'renamed_files': 0,
        'deleted_files': 0,
        'failed_files': 0,
        'skipped_files': 0,
        'not_found_files': 0
    }

    ebook_extensions = ('.epub', '.mobi', '.azw3', '.pdf', '.txt')

    # 索引文件模式
    if index_file:
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                index_records = {}
                for line in f:
                    parts = line.strip().split('|')
                    if len(parts) >= 1:
                        file_path = Path(parts[0])
                        if file_path.exists():
                            if file_path.suffix.lower() in ebook_extensions:
                                stats['total_files'] += 1
                                process_single_file(file_path, stats, index_records)
                        else:
                            stats['not_found_files'] += 1
                            print(f'索引文件中的文件未找到: {file_path}')

                # 更新索引文件
                if index_records:
                    update_index_file(index_file, index_records)
        except Exception as e:
            print(f'处理索引文件时出错: {str(e)}')

    # 目录扫描模式
    if directory:
        dir_path = Path(directory)
        for file_path in dir_path.rglob('*'):
            if file_path.suffix.lower() in ebook_extensions:
                stats['total_files'] += 1
                process_single_file(file_path, stats)

    return stats

def process_single_file(file_path, stats, index_records=None):
    """处理单个文件的重命名逻辑"""
    original_name = file_path.stem

    # 移除文件名中的 Z-Library 标记，如“_Z-Library”、“(Z-Library)”、“Z-Library”等
    new_name = re.sub(r'_?\s*\(Z-Library\).*$', '', original_name)
    # 移除文件名中的数字结尾，如“_123456”、“(123456)”等
    new_name = re.sub(r'_?\(?\d{5,20}\)?$', '', new_name)

    if new_name != original_name:
        new_path = file_path.with_name(new_name + file_path.suffix)
        try:
            # 如果目标文件已存在，则删除原文件
            if new_path.exists():
                file_path.unlink()  # 删除原文件
                stats['deleted_files'] += 1
                print(f'文件已存在，已删除重复文件: {file_path.name}')
            else:
                # 重命名文件
                file_path.rename(new_path)
                stats['renamed_files'] += 1
                print(f'已重命名: {file_path.name} -> {new_path.name}')

                # 更新索引记录
                if index_records is not None and file_path in index_records:
                    old_record = index_records[file_path]
                    new_record = old_record.replace(str(file_path), str(new_path))
                    index_records[file_path] = new_record

        except Exception as e:
            stats['failed_files'] += 1
            print(f'处理失败 {file_path.name}: {str(e)}')
    else:
        stats['skipped_files'] += 1

def update_index_file(index_file, index_records):
    """更新索引文件"""
    try:
        with open(index_file, 'w', encoding='utf-8') as f:
            for record in index_records.values():
                f.write(record + '\n')
        print('索引文件已更新')
    except Exception as e:
        print(f'更新索引文件失败: {str(e)}')


if __name__ == '__main__':
    # 仅使用索引文件模式
    # index_file = Path(r"J:\_file_list.txt")
    # stats = clean_book_filenames(index_file=index_file)

    # 或仅使用目录扫描模式
    directory = Path(r"J:\电子书\2024年")
    stats = clean_book_filenames(directory=directory)

    # 或同时使用两种模式
    # stats = clean_book_filenames(directory=directory, index_file=index_file)

    # 打印统计信息
    print('\n处理结果统计如下：')
    print(f'扫描的电子书文件总数：{stats["total_files"]}')
    print(f'成功重命名文件数：{stats["renamed_files"]}')
    print(f'删除重复文件数：{stats["deleted_files"]}')
    print(f'无需重命名文件数：{stats["skipped_files"]}')
    print(f'重命名失败文件数：{stats["failed_files"]}')
    print(f'索引文件中未找到的文件数：{stats["not_found_files"]}')
