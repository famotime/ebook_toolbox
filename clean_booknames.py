"""
批量处理电子书文件名的清理工具：
1. 遍历指定目录及其所有子目录
2. 查找所有电子书文件（支持的格式：epub、mobi、azw3、pdf、txt）
3. 移除文件名中的"(Z-Library)"及其后续文字
4. 同时更新同目录下"处理结果.txt"文件中的相关记录
5. 统计并显示处理结果（总文件数、重命名成功数、无需重命名数、失败数）
"""
from pathlib import Path
import re

def clean_book_filenames(directory):
    # 添加统计计数器
    stats = {
        'total_files': 0,        # 扫描的总文件数
        'renamed_files': 0,      # 成功重命名的文件数
        'failed_files': 0,       # 重命名失败的文件数
        'skipped_files': 0       # 不需要重命名的文件数
    }

    # 支持的电子书文件扩展名
    ebook_extensions = ('.epub', '.mobi', '.azw3', '.pdf', '.txt')

    # 获取目录路径对象
    dir_path = Path(directory)

    # 遍历所有文件，包括子目录
    for file_path in dir_path.rglob('*'):
        if file_path.suffix.lower() in ebook_extensions:
            stats['total_files'] += 1
            original_name = file_path.stem

            new_name = re.sub(r'_?\s*\(Z-Library\).*$', '', original_name)

            if new_name != original_name:
                new_path = file_path.with_name(new_name + file_path.suffix)
                try:
                    # 重命名文件
                    file_path.rename(new_path)
                    stats['renamed_files'] += 1
                    print(f'已重命名: {file_path.name} -> {new_path.name}')

                    # 检查并更新同目录下的“处理结果.txt”文件
                    result_file = file_path.parent / "处理结果.txt"
                    if result_file.exists():
                        try:
                            # 读取文件内容
                            content = result_file.read_text(encoding='utf-8')
                            # 替换文件名
                            new_content = content.replace(file_path.name, new_path.name)
                            # 写回文件
                            result_file.write_text(new_content, encoding='utf-8')
                            print(f'已更新“处理结果.txt”中的文件名记录')
                        except Exception as e:
                            print(f'更新“处理结果.txt”失败: {str(e)}')

                except Exception as e:
                    stats['failed_files'] += 1
                    print(f'重命名失败 {file_path.name}: {str(e)}')
            else:
                stats['skipped_files'] += 1

    return stats

if __name__ == '__main__':
    # 获取当前目录
    current_dir = Path(r"J:\书单")

    # 执行清理并获取统计结果
    stats = clean_book_filenames(current_dir)

    # 打印统计信息
    print('\n处理结果统计如下：')
    print(f'扫描的电子书文件总数：{stats["total_files"]}')
    print(f'成功重命名文件数：{stats["renamed_files"]}')
    print(f'无需重命名文件数：{stats["skipped_files"]}')
    print(f'重命名失败文件数：{stats["failed_files"]}')
