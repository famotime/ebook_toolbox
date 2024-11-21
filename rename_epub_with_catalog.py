"""
epub文件名目录信息添加工具

本脚本用于处理epub电子书文件名，主要功能：
1. 读取epub文件的一级目录信息
2. 将目录信息添加到文件名中（格式：原文件名 [目录信息].epub）
3. 仅处理文件名包含"全集"、"套装"、"作品集"的文件
4. 自动删除文件名中的"(Z-Library)"字符
5. 如果新文件名超过250字符，会：
   - 截断目录信息
   - 创建同名txt文件保存完整目录信息
6. 生成处理日志，记录所有操作

使用方法：
1. 在 TARGET_DIRS 中设置要处理的目录路径
2. 运行脚本即可自动处理指定目录中的epub文件

注意事项：
- 已经包含目录信息（[...]格式）的文件会被跳过
- 所有操作都会记录在目标目录下的 rename_log.log 文件中
- 支持Windows和Unix路径格式
"""

from pathlib import Path
import ebooklib
from ebooklib import epub
import re
from datetime import datetime


def get_toc_titles(epub_path):
    """获取epub文件的一级目录标题"""
    book = epub.read_epub(epub_path)
    toc = book.toc

    # 只获取一级目录
    level1_titles = []
    for item in toc:
        if isinstance(item, tuple):
            title = item[0].title
            level1_titles.append(title)

    return level1_titles

def clean_filename(text, max_length=100):
    """清理文件名中的非法字符，并在需要时截断"""
    # 移除或替换Windows文件名中的非法字符
    text = re.sub(r'[<>:"/\\|?*]', '_', text)
    if len(text) > max_length:
        return text[:max_length], text
    return text, None

def process_filename(filename):
    """处理原始文件名，删除 (Z-Library) 字符"""
    return filename.replace('(Z-Library)', '').strip()

def should_process_file(filename):
    """检查文件是否需要处理"""
    keywords = ['全集', '套装', '作品集', '合集', '系列', '丛书', '全套']
    return any(keyword in filename for keyword in keywords)

def main():
    for target_dir in TARGET_DIRS:
        # 展开用户路径并创建日志文件
        target_dir = target_dir.expanduser().resolve()
        log_file = target_dir / 'rename_log.log'
        log_entries = []

        # 检查目录是否存在
        if not target_dir.is_dir():
            print(f"错误：目录 '{target_dir}' 不存在")
            continue

        print(f"\n处理目录: {target_dir}")

        # 获取指定目录下的所有epub文件
        epub_files = target_dir.glob('*.epub')

        for epub_path in epub_files:
            try:
                # 检查文件名是否包含指定关键词
                if not should_process_file(epub_path.name):
                    log_entries.append(f"跳过不符合条件的文件: {epub_path.name}")
                    print(f"跳过不符合条件的文件: {epub_path.name}")
                    continue

                # 检查文件名是否已包含方括号中的目录信息
                if re.search(r'\[.*\]\.epub$', epub_path.name):
                    log_entries.append(f"跳过已处理的文件: {epub_path.name}")
                    print(f"跳过已处理的文件: {epub_path.name}")
                    continue

                # 处理原始文件名，删除 (Z-Library)
                original_name = epub_path.name
                clean_stem = process_filename(epub_path.stem)

                # 获取目录标题
                titles = get_toc_titles(str(epub_path))

                if titles:
                    # 将目录标题组合成字符串
                    toc_str = '_'.join(titles)

                    # 计算可用于目录信息的最大长度
                    max_toc_length = 250 - (len(clean_stem) + 1 + 2 + len(epub_path.suffix))

                    # 清理并可能截断目录字符串
                    cleaned_toc, full_toc = clean_filename(toc_str, max_toc_length)

                    # 构建新文件名
                    new_name = f"{clean_stem} [{cleaned_toc}]{epub_path.suffix}"
                    new_path = epub_path.parent / new_name

                    # 如果有完整目录信息需要保存
                    if full_toc:
                        txt_path = epub_path.parent / f"{clean_stem} [{cleaned_toc}].txt"
                        txt_path.write_text(
                            f"原文件名: {original_name}\n"
                            f"完整目录信息:\n"
                            f"{'='*50}\n"
                            f"{full_toc}\n"
                            f"{'='*50}",
                            encoding='utf-8'
                        )
                        log_entries.append(f"已创建目录信息文件: {txt_path.name}")
                        print(f"已创建目录信息文件: {txt_path.name}")

                    # 重命名文件
                    epub_path.rename(new_path)
                    log_entries.append(f"已重命名: {original_name} -> {new_name}")
                    print(f"已重命名: {original_name} -> {new_name}")

            except Exception as e:
                error_msg = f"处理 {epub_path.name} 时出错: {str(e)}"
                log_entries.append(error_msg)
                print(error_msg)

        # 写入日志文件
        log_content = (
            f"处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"处理目录: {target_dir}\n"
            f"{'='*50}\n"
            f"{chr(10).join(log_entries)}\n"
            f"{'='*50}\n\n"
        )

        # 追加模式写入日志
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_content)

        print(f"\n日志已保存到: {log_file}")

if __name__ == '__main__':
    # 在这里指定要处理的目录路径
    TARGET_DIRS = [
        Path(r'J:\zlibrary'),
    ]

    main()
