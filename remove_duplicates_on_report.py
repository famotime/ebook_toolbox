"""
根据find_duplicated_files.py生成的重复文件报告，批量删除重复文件到windows系统回收站
"""
import os
import shutil
import send2trash
from duplicate_finder_workflow import parse_checked_paths_from_report

def remove_duplicates_on_report(report_file_path):
    with open(report_file_path, 'r', encoding='utf-8') as file:
        checked_paths = parse_checked_paths_from_report(file.read())

    for file_path in checked_paths:
        if os.path.exists(file_path):
            send2trash.send2trash(file_path)
            print(f"已移动文件到系统回收站: {file_path}")
        else:
            print(f"文件不存在: {file_path}")

if __name__ == "__main__":
    report_file_path = r"D:\Python_Work\ebook_toolbox\output\duplicates_个人图片及视频_20250125_175404.md"
    remove_duplicates_on_report(report_file_path)
