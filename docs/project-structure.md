# 项目结构

## 概览

`ebook_toolbox` 当前按“入口脚本 + 共享工作流模块 + 测试 + 临时资产”组织，主线能力集中在本地书单整理、Z-Library 下载、重复文件查找和若干独立小工具。

## 入口脚本

| 文件 | 作用 |
| --- | --- |
| `collect_local_ebooks.py` | 本地书单整理主入口，支持批量书单与剪贴板监控 |
| `collect_ebooks_with_booklists.py` | 组合入口，先搜本地再补 Z-Library 下载 |
| `download_ebooks_from_zlibrary.py` | 针对 `处理结果.txt` 中未找到图书的批量下载入口 |
| `download_from_zlibrary_booklist.py` | 解析 Z-Library 书单页面并批量下载 |
| `find_duplicated_files.py` | 重复文件索引、查找与 Markdown 报告导出入口 |
| `remove_duplicates_on_report.py` | 根据重复文件 Markdown 报告把选中项移入回收站 |
| `clean_booknames.py` | 清理电子书文件名中的 Z-Library/数字尾缀等冗余信息 |
| `pull_md_images_to_local.py` | 下载 Markdown 中的远程图片并改写为本地路径 |
| `doc2md.py` | 合并目录中的 `.doc/.docx` 为单个 Markdown 文件 |
| `rename_epub_with_catalog.py` | 为 EPUB 合集文件名补充目录信息 |

## 共享模块

| 文件 | 作用 |
| --- | --- |
| `env_config.py` | 读取项目根目录 `.env` 中的 Z-Library 配置 |
| `library_index.py` | 统一 SQLite 文件索引、书名标准化、内容 quick/full hash 计算与查询 |
| `zlibrary_runtime.py` | 统一 Z-Library 认证加载、客户端创建、待处理结果文件发现 |
| `zlibrary_booklist_workflow.py` | 书单 HTML 解析、标准化本地索引命中判断、下载目标路径拼装 |
| `local_ebooks_workflow.py` | 本地书单输出目录决策、已复制条目解析、批量跳过分类 |
| `duplicate_finder_workflow.py` | 重复文件保留规则、Markdown 报告渲染与解析 |
| `Zlibrary.py` | 项目内使用的 Z-Library API 封装 |

## 测试

| 文件 | 覆盖范围 |
| --- | --- |
| `tests/test_env_config.py` | `.env` 账号字段读取 |
| `tests/test_local_ebooks_workflow.py` | 本地书单解析、输出目录决策、SQLite 索引搜索、同内容文件跳过 |
| `tests/test_zlibrary_booklist_workflow.py` | Z-Library 书单 HTML 解析、标准化本地索引匹配、已下载跳过 |
| `tests/test_zlibrary_runtime.py` | 共享认证加载、客户端创建、待处理结果文件筛选 |
| `tests/test_duplicate_finder_workflow.py` | 重复文件选择策略、报告渲染与改名同内容文件识别 |
| `tests/test_small_tool_entrypoints.py` | 小工具 CLI 入口参数与默认路径解析 |

## 非核心目录

| 路径 | 说明 |
| --- | --- |
| `image/` | README 配图资源 |
| `output/` | 历史重复文件报告与索引输出，属于运行产物 |
| `temp/` | 临时脚本、抓取页面、分析素材，不属于核心运行链路 |
| `account/` | 旧目录，当前凭据已迁移到项目根目录 `.env` |

## 当前建议

1. 继续把索引、哈希、标准化等横切逻辑收敛到 `library_index.py`，避免入口脚本再各自维护一套规则。
2. 新增行为优先补到 `tests/`，再改对应入口脚本。
3. 将 `temp/` 与 `output/` 视为辅助资产目录，不要把它们当成核心模块的一部分。
