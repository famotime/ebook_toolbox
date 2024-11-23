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
        print(f"图片已存在，跳过下载: {save_path}")
        return save_path

    # 下载图片
    try:
        print(f"正在下载图片: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        save_path.write_bytes(response.content)
        print(f"下载成功，保存至: {save_path}")
        return save_path
    except Exception as e:
        print(f"下载图片失败: {url}\n错误信息: {e}")
        return None

def process_markdown(md_file: Path, image_dir: Path = None) -> None:
    """
    处理Markdown文件中的图片
    """
    print(f"\n开始处理Markdown文件: {md_file}")

    if image_dir is None:
        image_dir = md_file.parent / 'images'
    print(f"图片将保存至: {image_dir}")

    content = md_file.read_text(encoding='utf-8')

    # 匹配Markdown中的图片链接
    pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
    matches = re.findall(pattern, content)
    total_images = len(matches)
    print(f"找到 {total_images} 个图片链接")

    processed_count = 0
    skipped_count = 0
    failed_count = 0

    def replace_image(match):
        nonlocal processed_count, skipped_count, failed_count
        alt_text, url = match.groups()
        # 跳过已经是本地路径的图片
        if url.startswith(('/', '.')) or ':\\' in url:
            skipped_count += 1
            print(f"跳过本地图片: {url}")
            return match.group(0)

        # 下载图片
        save_path = download_image(url, image_dir)
        if save_path:
            processed_count += 1
            # 构建相对路径
            relative_path = save_path.relative_to(md_file.parent)
            return f'![{alt_text}]({relative_path})'
        failed_count += 1
        return match.group(0)

    # 替换所有图片链接
    new_content = re.sub(pattern, replace_image, content)

    # 保存修改后的文件
    md_file.write_text(new_content, encoding='utf-8')

    print(f"\n处理完成:")
    print(f"- 成功下载: {processed_count} 个")
    print(f"- 跳过本地图片: {skipped_count} 个")
    print(f"- 下载失败: {failed_count} 个")


if __name__ == '__main__':
    md_file = Path(r'J:\相对论究竟是什么【文字版】_(万维钢).md')
    process_markdown(md_file)