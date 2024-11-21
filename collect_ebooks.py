"""
在本地硬盘上查找一个清单文件中的所有电子书，并复制到一个新的目录中。

功能说明：
1. 清单文件包含使用《》包裹的书名
2. 搜索规则：
   - 文件名必须以搜索词开头（忽略标点符号和大小写）
   - 支持中文、英文和数字
   - 文件类型优先级：epub > pdf > txt
3. 处理流程：
   - 首次运行时生成搜索目录下的文件列表（_file_list.txt）
   - 跳过已经存在于输出目录中的文件
   - 生成处理结果文件（清单文件名_结果.txt）
   - 复制找到的文件到输出目录
4. 输出报告：
   - 总文件数统计
   - 已存在文件数
   - 新找到文件数
   - 成功复制数
   - 未找到文件清单
   - 复制失败文件列表

注意事项：
- 跳过系统目录和特殊文件夹的扫描
- 不验证文件是否真实存在
- 使用文件缓存提升搜索性能
"""

from pathlib import Path
import shutil
import re
import time
import pyperclip

def generate_file_list(search_dir):
    """
    生成目录下所有文件的路径列表文件
    Args:
        search_dir: 搜索目录路径
    Returns:
        文件列表文件的路径
    """
    search_path = Path(search_dir)
    file_list_path = search_path / '_file_list.txt'

    print(f"正在生成文件列表：{file_list_path}")

    # 收集所有epub、pdf和txt文件
    files = []
    for ext in ['.epub', '.pdf', '.txt']:
        try:
            for p in search_path.rglob(f'*{ext}'):
                try:
                    # 跳过系统目录和无法访问的文件
                    # 要跳过的系统目录和文件名列表
                    SKIP_DIRS = {
                        'System Volume Information',
                        '$Recycle.Bin',
                        '$RECYCLE.BIN',
                        'Config.Msi',
                        'Recovery',
                        'Documents and Settings',
                        'PerfLogs',
                        'Program Files',
                        'Program Files (x86)',
                        'Windows'
                    }
                    if p.is_file() and not any(x.startswith('$') or x in SKIP_DIRS for x in p.parts):
                        # 添加文件大小和修改时间信息
                        stat = p.stat()
                        files.append(f"{p}|{stat.st_size}|{stat.st_mtime}")
                except (PermissionError, OSError):
                    continue
        except Exception as e:
            print(f"搜索{ext}文件时出错: {e}")
            continue

    # 将文件列表写入文件
    with file_list_path.open('w', encoding='utf-8') as f:
        f.write('\n'.join(files))

    print(f"文件列表生成完成，共 {len(files)} 个文件")
    return file_list_path

def clean_filename(filename):
    """
    清理文件名中的标点符号和空格，只保留中文、英文和数字
    """
    # 使用正则表达式保留中文字符、英文字母和数字
    cleaned = re.sub(r'[^\u4e00-\u9fff\w]', '', filename)
    return cleaned.lower()  # 转换为小写

def search_file(filename, search_dir):
    """
    在文件列表中搜索文件
    Args:
        filename: 要搜索的文件名
        search_dir: 搜索目录路径
    """
    search_path = Path(search_dir)
    file_list_path = search_path / '_file_list.txt'
    name = clean_filename(filename)
    if not name:
        name = filename.lower()

    print(f"正在搜索：{filename}（清理后的搜索词：{name}）")

    # 如果文件列表不存在或为空，则生成
    if not file_list_path.exists() or file_list_path.stat().st_size == 0:
        file_list_path = generate_file_list(search_dir)

    # 修改缓存结构以包含文件信息
    if not hasattr(search_file, '_file_cache'):
        search_file._file_cache = {'.epub': [], '.pdf': [], '.txt': []}
        with file_list_path.open('r', encoding='utf-8') as f:
            for line in f:
                path_str, size, mtime = line.strip().split('|')
                path = Path(path_str)
                ext = path.suffix.lower()
                if ext in search_file._file_cache:
                    search_file._file_cache[ext].append((
                        str(path),
                        clean_filename(path.stem),
                        int(size),
                        float(mtime)
                    ))

    # 按优先级搜索匹配的文件
    matches = []
    for ext in ['.epub', '.pdf', '.txt']:
        for file_path, clean_stem, size, mtime in search_file._file_cache[ext]:
            if clean_stem.startswith(name):
                matches.append((file_path, ext, size, mtime))

        # 如果在当前优先级找到匹配，就不继续搜索次优先级的文件
        if matches:
            # 在相同后缀名下，优先选择更大的文件，如果大小相同则选择更新的文件
            return max(matches, key=lambda x: (x[2], x[3]))[0]

    print(f"未找到：{filename}")
    return "未找到"

def check_file_list_update(search_dir):
    """
    检查文件列表是否需要更新
    Args:
        search_dir: 搜索目录路径
    Returns:
        bool: 是否需要更新
    """
    search_path = Path(search_dir)
    file_list_path = search_path / '_file_list.txt'

    # 如果文件列表不存在或为空，需要生成
    if not file_list_path.exists() or file_list_path.stat().st_size == 0:
        print(f"文件列表{file_list_path}不存在或为空，需要生成。")
        return True

    # 如果文件列表超过24小时未更新，建议更新
    # file_age = time.time() - file_list_path.stat().st_mtime
    # if file_age > 24 * 3600:  # 24小时
    #     user_input = input("文件列表已超过24小时未更新，是否重新生成？(y/n): ")
    #     return user_input.lower() == 'y'

    return False

def extract_book_names(content: str) -> list[str]:
    """
    从整个文本内容中提取所有使用《》包裹的书名，并去重

    Args:
        content: 输入的文本内容
    Returns:
        list[str]: 提取到的去重后的书名列表
    """
    if not content or '《' not in content:
        return []

    pattern = r'《([^》]+)》'
    matches = re.findall(pattern, content)

    # 使用集合去重后转回列表
    return list(dict.fromkeys(matches))

def clean_dirname(name: str) -> str:
    """
    清理目录名中的非法字符
    Args:
        name: 原始目录名
    Returns:
        str: 清理后的目录名
    """
    # Windows下文件名不能包含这些字符: \ / : * ? " < > |
    invalid_chars = r'\/:*?"<>|'
    # 替换非法字符为空格
    for char in invalid_chars:
        name = name.replace(char, ' ')
    # 清理多余的空格
    name = ' '.join(name.split())
    return name.strip()

def get_books_from_clipboard():
    """
    从剪贴板获取内容并提取书名
    Returns:
        tuple: (目录名, 书名列表)
    """
    try:
        content = pyperclip.paste()
        if not content:
            raise ValueError("剪贴板内容为空")

        # 获取第一行作为目录名并清理
        lines = content.splitlines()
        dir_name = clean_dirname(lines[0].strip()) if lines else "新建书单"

        # 提取书名
        book_names = extract_book_names(content)
        if not book_names:
            raise ValueError("未找到使用《》标记的书名")

        return dir_name, book_names
    except Exception as e:
        print(f"从剪贴板获取内容失败: {e}")
        return None, []

def process_book_list(list_file, search_dir, from_clipboard=False):
    """
    处理书籍清单
    Args:
        list_file: 清单文件路径（从剪贴板读取时作为输出目录的父目录）
        search_dir: 搜索目录路径
        from_clipboard: 是否从剪贴板读取内容
    """
    search_path = Path(search_dir)
    if not search_path.exists():
        raise FileNotFoundError(f"搜索目录不存在: {search_dir}")

    # 根据来源获取书名列表和输出目录
    if from_clipboard:
        parent_dir = Path(list_file)
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)

        dir_name, book_names = get_books_from_clipboard()
        if not dir_name or not book_names:
            return

        output_dir = parent_dir / dir_name
    else:
        list_path = Path(list_file)
        if not list_path.exists():
            raise FileNotFoundError(f"清单文件不存在: {list_file}")

        # 一次性读取整个文件内容
        with list_path.open('r', encoding='utf-8') as f:
            content = f.read()

        book_names = extract_book_names(content)
        output_dir = list_path.parent / list_path.stem

    # 创建输出目录
    output_dir.mkdir(exist_ok=True)

    # 结果文件和日志文件都保存在新建的书单目录下
    result_file = output_dir / "处理结果.txt"
    log_file = output_dir / "处理日志.txt"

    # 获取输出目录中已存在的文件
    existing_files = {clean_filename(f.stem): f.stem for f in output_dir.glob('*.*')}

    # 添加统计变量
    stats = {
        'total': len(book_names),  # 总文件数
        'found': 0,          # 找到的文件数
        'copied': 0,         # 成功复制的文件数
        'existing': 0,       # 已存在的文件数
        'not_found': [],     # 未找到的文件列表
        'copy_failed': []    # 复制失败的文件列表
    }

    # 处理每本书
    results = []
    for book_name in book_names:
        clean_name = clean_filename(book_name)

        if clean_name in existing_files:
            stats['existing'] += 1
            result = f"《{book_name}》: 跳过（输出目录已存在：{existing_files[clean_name]}）"
            results.append(result)
            continue

        file_path = search_file(book_name, search_path)
        if file_path == "未找到":
            stats['not_found'].append(book_name)
        else:
            stats['found'] += 1
            try:
                shutil.copy2(file_path, output_dir)
                stats['copied'] += 1
            except Exception as e:
                stats['copy_failed'].append((book_name, str(e)))

        result = f"《{book_name}》: {file_path}"
        results.append(result)

    # 将结果写入结果文件
    with result_file.open('w', encoding='utf-8') as f:
        f.write("处理总结：\n")
        f.write(f"总共需要处理的文件数：{stats['total']}\n")
        f.write(f"已存在的文件数：{stats['existing']}\n")
        f.write(f"新找到的文件数：{stats['found']}\n")
        f.write(f"成功复制的文件数：{stats['copied']}\n")
        f.write(f"未找到的文件数：{len(stats['not_found'])}\n\n")

        if stats['not_found']:
            f.write("未找到的文件清单：\n")
            for book in stats['not_found']:
                f.write(f"- {book}\n")
            f.write("\n")

        if stats['copy_failed']:
            f.write("复制失败的文件：\n")
            for book, error in stats['copy_failed']:
                f.write(f"- {book}: {error}\n")

    # 将详细结果写入日志文件
    with log_file.open('w', encoding='utf-8') as f:
        f.write('\n'.join(results))

    print(f"\n处理日志已保存到：{log_file}")
    print(f"处理结果已保存到：{result_file}")


if __name__ == "__main__":
    # 清单文件路径
    # list_file = r"C:\Users\Administrator\Desktop\超人书单.md"

    # 搜索目录路径
    search_dir = r"J:"

    try:
        # 检查是否需要更新文件列表
        if check_file_list_update(search_dir):
            generate_file_list(search_dir)

        # 从文件读取
        # process_book_list(list_file, search_dir, from_clipboard=False)

        # 或从剪贴板读取
        process_book_list(r"J:\书单", search_dir, from_clipboard=True)

        print("处理完成！")
    except Exception as e:
        print(f"处理失败: {e}")
