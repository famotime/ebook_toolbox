"""
将markdown文件中的图片下载到本地，并修改图片路径
"""
from pathlib import Path
import re
import requests
import hashlib
from urllib.parse import unquote

def download_image(url: str, save_dir: Path) -> Path:
    """
    下载图片并返回保存路径
    """
    # 确保保存目录存在
    save_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名（使用URL的MD5值作为文件名）
    file_name = hashlib.md5(url.encode()).hexdigest()
    # 保留原始文件扩展名
    ext = Path(unquote(url)).suffix or '.jpg'
    save_path = save_dir / f"{file_name}{ext}"

    # 如果文件已存在，直接返回路径
    if save_path.exists():
        return save_path

    # 下载图片
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        save_path.write_bytes(response.content)
        return save_path
    except Exception as e:
        print(f"下载图片失败: {url}\n错误信息: {e}")
        return None

def process_markdown(md_file: Path, image_dir: Path = None) -> None:
    """
    处理Markdown文件中的图片
    """
    if image_dir is None:
        image_dir = md_file.parent / 'images'

    content = md_file.read_text(encoding='utf-8')

    # 匹配Markdown中的图片链接
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'

    def replace_image(match):
        alt_text, url = match.groups()
        # 跳过已经是本地路径的图片
        if url.startswith(('/', '.')) or ':\\' in url:
            return match.group(0)

        # 下载图片
        save_path = download_image(url, image_dir)
        if save_path:
            # 构建相对路径
            relative_path = save_path.relative_to(md_file.parent)
            return f'![{alt_text}]({relative_path})'
        return match.group(0)

    # 替换所有图片链接
    new_content = re.sub(pattern, replace_image, content)

    # 保存修改后的文件
    md_file.write_text(new_content, encoding='utf-8')


if __name__ == '__main__':
    md_file = Path(r'J:\相对论究竟是什么【文字版】_(万维钢).md')
    process_markdown(md_file)