"""
读取指定目录下的所有doc/docx文件内容，并拼接成一个markdown文件
"""
import argparse
from pathlib import Path
import re


DEFAULT_INPUT_DIRECTORY = Path(r"G:\Download\创作")

def convert_doc_to_docx(doc_path):
    """将 doc 文件转换为 docx 文件"""
    import win32com.client

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
    import docx2txt

    input_path = Path(input_dir)
    output_path = Path(output_file)
    if not input_path.exists():
        raise FileNotFoundError(f"输入目录不存在: {input_path}")

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


def resolve_output_markdown(input_dir: Path, output_file: Path | None) -> Path:
    return output_file or (Path(input_dir) / "output.md")


def build_parser():
    parser = argparse.ArgumentParser(description="将目录中的 doc/docx 合并为 Markdown")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIRECTORY, help="输入目录")
    parser.add_argument("--output-file", type=Path, default=None, help="输出 Markdown 文件")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    output_file = resolve_output_markdown(args.input_dir, args.output_file)
    doc_to_markdown(args.input_dir, output_file)


if __name__ == '__main__':
    main()
