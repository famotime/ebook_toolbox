# ebook_toolbox 电子书处理工具箱

## 完整工具列表

1. `collect_ebooks.py`: 电子书搜索与整理工具
2. `rename_epub_with_catalog.py`: EPUB合集文件名处理工具
3. `clean_booknames.py`: 书名格式清理工具
4. `download_ebooks_from_zlibrary.py`: Z-Library电子书下载工具
5. `Zlibrary.py`: Z-Library API封装库



## 主要功能

### 1. 电子书搜索与整理 (collect_ebooks.py)

根据书单内容在本地硬盘上查找指定的电子书文件，并将它们复制到整理到对应书单目录中。

主要功能：
- 支持从剪贴板或文本文件读取书名清单（使用《》标记的书名）

- 按文件类型优先级搜索：epub > pdf > txt

  


### 2. EPUB合集文件名补充目录信息 (rename_epub_with_catalog.py)

这个脚本用于处理EPUB电子书合集的文件名，自动添加目录信息。

主要功能：
- 读取EPUB文件的一级目录信息
- 将目录信息添加到文件名中（格式：原文件名 [目录信息].epub）
- 自动处理文件名中包含"全集"、"套装"、"作品集"等关键词的文件
- 自动删除文件名中的"(Z-Library)"字符
- 处理过长文件名，自动截断并保存完整信息
- 生成详细的处理日志

### 3. 书名清理工具 (clean_booknames.py)

这个脚本用于清理和标准化书名格式。

主要功能：
- 清理书名中的多余字符和标点
- 统一书名的《》标记格式
- 删除常见的广告后缀
- 批量处理文本文件中的书名

### 4. Z-Library电子书下载工具 (download_ebooks_from_zlibrary.py)

这个脚本提供了从Z-Library自动下载电子书的功能。

主要功能：
- 支持批量下载指定书名的电子书
- 自动处理登录和搜索过程
- 支持多种下载格式选择
- 自动重试和错误处理
- 生成下载报告和日志

### 5. Z-Library API封装 (Zlibrary.py)

这是一个封装了Z-Library网站API的工具类。

主要功能：
- 提供登录认证接口
- 封装搜索和下载功能
- 处理请求限制和错误
- 管理会话和cookies
- 提供便捷的API调用方法

## 使用方法

### 电子书搜索与整理工具 (collect_ebooks.py)

1. 从剪贴板读取书单：
   - 复制包含书名的文本（书名需要用《》标记）
   - 第一行文本将作为输出目录名
   - 运行脚本，自动处理剪贴板内容

2. 从文件读取书单：
   - 创建文本文件，包含需要查找的书名（使用《》标记）
   - 修改脚本中的 `list_file` 路径
   - 运行脚本处理文件内容

3. 配置搜索目录：
   - 修改脚本中的 `search_dir` 变量
   - 首次运行会生成文件缓存列表
   - 24小时后会提示更新缓存

4. 输出文件说明：
   - 处理结果.txt：包含统计信息和详细结果
   - 处理日志.txt：记录每本书的处理状态
   - 找到的电子书文件会被复制到输出目录

注意事项：
- 搜索时会忽略文件名中的标点符号和大小写
- 文件名匹配规则：必须以搜索词开头
- 同一本书存在多个版本时，优先选择更大的文件
- 自动跳过 Windows 系统目录和特殊文件夹

### EPUB合集文件名补充目录信息工具 (rename_epub_with_catalog.py)

1. 基本配置：
   ```python
   TARGET_DIRS = [
       Path(r'J:\zlibrary'),  # 添加需要处理的目录路径
       # Path(r'D:\ebooks'),  # 可以添加多个目录
   ]
   ```

2. 处理规则：
   - 仅处理文件名包含以下关键词的文件：
     - 全集
     - 套装
     - 作品集
     - 合集
     - 系列
     - 丛书
     - 全套
   - 自动跳过已经包含目录信息（[...]格式）的文件
   - 自动删除文件名中的"(Z-Library)"字符

3. 文件命名格式：
   - 原文件名：`作者名+书名.epub`
   - 处理后：`作者名+书名 [目录1_目录2_目录3].epub`
   - 如果目录信息过长（超过250字符）：
     - 文件名会被自动截断
     - 创建同名txt文件保存完整目录信息

4. 输出文件：
   - rename_log.log：记录所有处理操作
   - 目录信息文件（可选）：保存被截断的完整目录信息

5. 使用示例：
   ```bash
   # 原文件名
   鲁迅全集(Z-Library).epub
   
   # 处理后的文件名
   鲁迅全集 [朝花夕拾_野草_故事新编_华盖集].epub
   
   # 如果目录过长，会生成
   鲁迅全集 [朝花夕拾_野草...].epub
   鲁迅全集 [朝花夕拾_野草...].txt  # 包含完整目录信息
   ```

6. 注意事项：
   - 确保有足够的权限访问和修改目标目录
   - 建议先备份重要文件再进行处理
   - 处理过程中请勿修改文件名
   - 需要安装 ebooklib 库：`pip install ebooklib`

### 书名清理工具使用

```python
from clean_booknames import clean_names
# 清理单个书名
cleaned = clean_names("<<三体>>（全集）【精校版】.txt")  # 返回：《三体》

# 清理文件中的书名
clean_names("input.txt", "output.txt")
```

### Z-Library下载工具使用

1. 配置账号信息：
```python
ZLIBRARY_EMAIL = "your_email@example.com"
ZLIBRARY_PASSWORD = "your_password"
```

2. 准备书单文件：
```text
《三体》
《百年孤独》
《人类简史》
```

3. 运行下载：
```python
from download_ebooks_from_zlibrary import download_books
download_books("booklist.txt", "downloads")
```



## 依赖库

- ebooklib
- pyperclip
- requests

