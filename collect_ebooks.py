"""
在本地硬盘上查找书单中的电子书，并复制到一个新目录中。

功能说明：
1. 支持两种输入方式：
   - 从剪贴板读取（监控模式）
   - 从文件读取（直接处理模式）
2. 清单格式要求：
   - 必须包含使用《》包裹的书名
   - 使用剪贴板时，第一行作为输出目录名
3. 书名处理规则：
   - 自动清理HTML标签（如 <span>、<br> 等）
   - 自动清理HTML实体字符（如 &nbsp;）
   - 自动清理特殊字符（如 *[]【】{}『』「」等）
   - 自动清理多余空格
4. 搜索规则：
   - 文件名必须以搜索词开头（忽略标点符号和大小写）
   - 支持中文、英文和数字
   - 文件类型优先级：epub > pdf > txt
   - 同类型文件优先选择更大的文件，大小相同则选择更新的文件
5. 输出目录结构：
   - 在统一的父目录下创建子文件夹
   - 每个书单对应一个独立的子文件夹
   - 子文件夹包含处理结果和日志文件
6. 处理流程：
   - 首次运行时生成搜索目录下的文件列表（_file_list.txt）
   - 跳过已经存在于输出目录中的文件
   - 生成两个结果文件：
     * 处理结果.txt：简要统计和文件列表
     * 处理日志.txt：详细的处理记录和完整路径
7. 输出报告：
   - 总文件数统计
   - 已存在文件数
   - 新找到文件数
   - 成功复制数
   - 未找到文件清单
   - 复制失败文件列表

注意事项：
- 自动跳过系统目录和特殊文件夹的扫描
- 使用文件缓存提升搜索性能
- 监控模式下，粘贴不包含《》的内容可退出程序
- 支持的书单文件格式：txt、md、html
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
            # 在相同后缀名下优先选择更大的文件，如果大小相同则选择更新的文件
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
    # 文件名示例: _file_list_20241201.txt
    file_list_path = search_path / f'_file_list.txt'

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
    会清理书名中的HTML标签、HTML实体字符、特殊字符和多余空格

    Args:
        content: 输入的文本内容
    Returns:
        list[str]: 提取到的去重后的书名列表
    """
    if not content or '《' not in content:
        return []

    # 先提取所有《》中的内容
    pattern = r'《([^》]+)》'
    matches = re.findall(pattern, content)

    # 清理HTML标签的正则表达式
    html_pattern = r'<[^>]+>'

    # 清理HTML实体字符的正则表达式
    html_entity_pattern = r'&[a-zA-Z]+;'

    # 要清理的特殊字符（可以根据需要添加更多）
    special_chars = r'[*\[\]【】\{\}『』「」\\\|\.\+#@\$%\^&\s]'

    # 清理每个书名中的HTML标签、特殊字符和多余空格
    cleaned_names = []
    for name in matches:
        # 1. 移除HTML标签
        cleaned = re.sub(html_pattern, '', name)
        # 2. 移除HTML实体字符（如&nbsp;）
        cleaned = re.sub(html_entity_pattern, ' ', cleaned)
        # 3. 移除特殊字符
        cleaned = re.sub(special_chars, ' ', cleaned)
        # 4. 清理多余空格并去除首尾空格
        cleaned = ' '.join(cleaned.split())
        if cleaned:  # 确保清理后的书名不为空
            cleaned_names.append(cleaned)

    # 使用字典去重并保持顺序
    return list(dict.fromkeys(cleaned_names))

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
        # 修改输出目录为统一的父目录下的子目录
        output_dir = Path(BOOKS_OUTPUT_DIR) / list_path.stem

    # 创建输出目录
    output_dir.mkdir(exist_ok=True)

    # 结果文件和日志文件都保存在新建的书单目录下
    result_file = output_dir / "处理结果.txt"
    log_file = output_dir / "处理日志.txt"

    # 读取已有的处理结果
    previously_copied = set()
    if result_file.exists():
        with result_file.open('r', encoding='utf-8') as f:
            content = f.read()
            # 提取"已找到并复制的文件"部分的书名
            if "已找到并复制的文件：" in content:
                copied_section = content.split("已找到并复制的文件：")[1].split("\n\n")[0]
                for line in copied_section.strip().split("\n"):
                    if line.startswith("- 《"):
                        book = line[3:-1]  # 去掉"- 《"和"》"
                        previously_copied.add(book)

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
    log_results = []  # 新增：用于记录详细日志
    for book_name in book_names:
        # 如果书已经在之前的处理结果中，跳过处理
        if book_name in previously_copied:
            stats['existing'] += 1
            result = f"《{book_name}》: 跳过（之前已处理）"
            results.append(result)
            log_results.append(result)
            continue

        clean_name = clean_filename(book_name)

        if clean_name in existing_files:
            stats['existing'] += 1
            result = f"《{book_name}》: 跳过（输出目录已存在：{existing_files[clean_name]}）"
            results.append(result)
            log_results.append(result)  # 跳过的文件记录相同
            continue

        file_path = search_file(book_name, search_path)
        if file_path == "未找到":
            stats['not_found'].append(book_name)
            log_results.append(f"《{book_name}》: 未找到")
        else:
            stats['found'] += 1
            try:
                shutil.copy2(file_path, output_dir)
                stats['copied'] += 1
                # 结果文件只记录文件名
                results.append(f"- 《{book_name}》")
                # 日志文件记录完整路径
                log_results.append(f"《{book_name}》: 已复制 {file_path} -> {output_dir}")
            except Exception as e:
                stats['copy_failed'].append((book_name, str(e)))
                error_msg = f"《{book_name}》: 复制失败 - 源文件：{file_path}, 错误：{str(e)}"
                log_results.append(error_msg)

    # 读取已有的处理结果内容
    existing_content = ""
    existing_copied_files = ""
    if result_file.exists():
        with result_file.open('r', encoding='utf-8') as f:
            existing_content = f.read()
            if "已找到并复制的文件：" in existing_content:
                parts = existing_content.split("已找到并复制的文件：")
                if len(parts) > 1:
                    existing_copied_files = parts[1].split("\n\n")[0].strip()

    # 将结果写入结果文件
    with result_file.open('w', encoding='utf-8') as f:
        f.write("处理总结：\n")
        f.write(f"总共需要处理的文件数：{stats['total']}\n")
        f.write(f"已存在的文件数：{stats['existing']}\n")
        f.write(f"新找到的文件数：{stats['found']}\n")
        f.write(f"成功复制的文件数：{stats['copied']}\n")
        f.write(f"未找到的文件数：{len(stats['not_found'])}\n\n")

        f.write("已找到并复制的文件：\n")
        # 首先写入原有的已复制文件列表
        if existing_copied_files:
            f.write(existing_copied_files + "\n")
        # 然后写入新复制的文件
        for result in results:
            if "未找到" not in result and "跳过" not in result:
                f.write(f"{result}\n")
        f.write("\n")

        if stats['not_found']:
            f.write("未找到的文件清单：\n")
            for book in stats['not_found']:
                f.write(f"- 《{book}》\n")
            f.write("\n")

    # 将详细结果写入日志文件（包含完整路径）
    with log_file.open('w', encoding='utf-8') as f:
        f.write(f"处理时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"搜索目录：{search_dir}\n")
        f.write(f"输出目录：{output_dir}\n")
        f.write("="*50 + "\n\n")
        f.write('\n'.join(log_results))

    print(f"\n处理日志已保存到：{log_file}")
    print(f"处理结果已保存到：{result_file}")

def monitor_clipboard(search_dir):
    """
    监控系统剪贴板，发现新的书单就处理
    Args:
        search_dir: 搜索目录路径
    """
    last_content = ""
    print("开始监控剪贴板，粘贴包含《》内容开始处理，粘贴不包含《》的内容结束程序...")

    while True:
        try:
            current_content = pyperclip.paste()
            # 如果剪贴板内容发生变化
            if current_content != last_content:
                last_content = current_content

                # 检查是否包含书名标记
                if "《" in current_content and "》" in current_content:
                    print("\n检测到新的书单，开始处理...")
                    process_book_list(Path(search_dir) / "书单", search_dir, from_clipboard=True)
                    print("\n继续监控剪贴板...")
                else:
                    print("\n检测到不包含书名的内容，退出程序")
                    break

            time.sleep(1)  # 降低CPU占用

        except KeyboardInterrupt:
            print("\n用户中断，退出程序")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            continue

def process_book_list_directory(list_dir, search_dir):
    """
    处理指定目录下的所有书单文件
    Args:
        list_dir: 书单文件所在目录
        search_dir: 搜索目录路径
    """
    list_path = Path(list_dir)
    if not list_path.exists():
        raise FileNotFoundError(f"书单目录不存在: {list_dir}")

    # 支持的文件类型
    supported_extensions = {'.txt', '.md', '.html', '.htm'}

    # 获取所有支持的文件
    book_list_files = []
    for ext in supported_extensions:
        book_list_files.extend(list_path.glob(f'*{ext}'))

    if not book_list_files:
        print(f"在 {list_dir} 中未找到任何书单文件")
        return

    print(f"找到 {len(book_list_files)} 个书单文件")

    # 处理每个书单文件
    for file_path in book_list_files:
        print(f"\n处理书单文件: {file_path.name}")
        process_book_list(file_path, search_dir, from_clipboard=False)


if __name__ == "__main__":
    search_dir = r"J:"    # 本地电子书库路径
    list_dir = r"D:\Python_Work\Wiznotes_tools\wiznotes\兴趣爱好\读书观影\书单"    # 书单文件所在目录
    BOOKS_OUTPUT_DIR = Path(r"J:\书单")  # 统一的书单输出目录

    try:
        # 确保输出目录存在
        BOOKS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 检查是否需要更新文件索引列表
        if check_file_list_update(search_dir):
            generate_file_list(search_dir)

        print("请选择运行模式：")
        print("1. 剪贴板监控模式")
        print("2. 批量处理书单文件")
        mode = input("请输入模式编号(1/2): ").strip()

        if mode == "1":
            # 启动剪贴板监控，使用统一的输出目录
            monitor_clipboard(search_dir)
        elif mode == "2":
            # 处理书单文件
            process_book_list_directory(list_dir, search_dir)
        else:
            print("无效的模式选择！")

    except Exception as e:
        print(f"处理失败: {e}")
