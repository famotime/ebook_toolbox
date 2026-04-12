with open("download_ebooks_from_zlibrary.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    'self.stats.failed_books += 1  # 下载次数用完计入失败\n                return None',
    'self.stats.failed_books += 1  # 下载次数用完计入失败\n                raise Exception("QUOTA_EXCEEDED")'
)

text = text.replace(
    '        except Exception as e:\n            print(f"处理图书时出错: {e}")\n            self.stats.failed_books += 1  # 异常情况计入失败\n            self.update_result_file(book_name, success=False)\n            return None',
    '        except Exception as e:\n            if str(e) == "QUOTA_EXCEEDED":\n                raise\n            print(f"处理图书时出错: {e}")\n            self.stats.failed_books += 1  # 异常情况计入失败\n            self.update_result_file(book_name, success=False)\n            return None'
)

text = text.replace(
    '                stats.processed_files += 1\n                final_downloads_left = downloader.downloads_left\n                stats.processed_file_list.append(str(result_file))\n            except Exception as e:\n                print(f"处理 {result_file} 时出错: {e}")\n                continue\n            finally:\n                stats.save_progress(progress_file)',
    '                stats.processed_files += 1\n                final_downloads_left = downloader.client.getDownloadsLeft()\n                stats.processed_file_list.append(str(result_file))\n            except Exception as e:\n                print(f"处理 {result_file} 时出错: {e}")\n                if "QUOTA_EXCEEDED" in str(e):\n                    print("检测到下载限额已满，主动终止当前及后续队列，保存断点供明天续传。")\n                    break\n                continue\n            finally:\n                stats.save_progress(progress_file)'
)

with open("download_ebooks_from_zlibrary.py", "w", encoding="utf-8") as f:
    f.write(text)
