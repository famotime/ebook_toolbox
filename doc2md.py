"""
读取指定目录下的所有doc/docx文件内容，并拼接成一个markdown文件
"""
from pathlib import Path
import docx2txt
import win32com.client
import time
import re

def convert_doc_to_docx(doc_path):
    """将 doc 文件转换为 docx 文件"""
    word = win32com.client.Dispatch('Word.Application')
    doc = word.Documents.Open(str(doc_path))
    docx_path = doc_path.with_suffix('.docx')
    doc.SaveAs(str(docx_path), 16)  # 16 表示 docx 格式
    doc.Close()
    word.Quit()
    return docx_path

def natural_sort_key(path):
    """实现自然排序的键函数
    例如：确保 "2.doc" 排在 "10.doc" 前面
    """
    # 将文件名分割成文本和数字部分
    parts = re.split('([0-9]+)', path.stem)
    # 将数字部分转换为整数进行比较
    return [int(part) if part.isdigit() else part.lower() for part in parts]

def doc_to_markdown(input_dir, output_file):
    """
    将指定目录下的所有 doc/docx 文件转换为单个 markdown 文件

    Args:
        input_dir: 输入目录路径
        output_file: 输出的 markdown 文件路径
    """
    input_path = Path(input_dir)
    output_path = Path(output_file)

    # 收集并排序所有文档
    doc_files = sorted(input_path.glob('*.doc'), key=natural_sort_key)
    docx_files = sorted(input_path.glob('*.docx'), key=natural_sort_key)

    # 合并内容
    content = []

    # 处理 doc 文件
    for doc_file in doc_files:
        print(f"处理文件: {doc_file}")
        docx_file = convert_doc_to_docx(doc_file)
        text = docx2txt.process(str(docx_file))
        content.append(f"## {doc_file.stem}\n\n{text}\n\n")

    # 处理 docx 文件
    for docx_file in docx_files:
        print(f"处理文件: {docx_file}")
        text = docx2txt.process(str(docx_file))
        content.append(f"## {docx_file.stem}\n\n{text}\n\n")

    # 写入输出文件
    output_path.write_text('\n'.join(content), encoding='utf-8')
    print(f"转换完成，输出文件：{output_path}")

if __name__ == '__main__':
    # 使用示例
    input_directory = Path(r"G:\Download\创作")  # 输入目录
    output_markdown = input_directory / "output.md"  # 输出文件
    doc_to_markdown(input_directory, output_markdown)
