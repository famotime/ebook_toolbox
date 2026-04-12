import os
import sys
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from env_config import load_zlibrary_env, ENV_FILE

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dist = Path(__file__).parent / "frontend" / "dist"

class EnvConfigModel(BaseModel):
    zlibrary_email: str
    zlibrary_password: str
    zlibrary_remix_userid: str
    zlibrary_remix_userkey: str

@app.get("/api/settings")
def get_settings():
    config = load_zlibrary_env()
    return config

@app.post("/api/settings")
def save_settings(config: EnvConfigModel):
    lines = []
    if ENV_FILE.exists():
        with ENV_FILE.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    
    def update_or_append(lines_arr, key, val):
        found = False
        for i, line in enumerate(lines_arr):
            if line.strip().startswith(f"{key}="):
                lines_arr[i] = f"{key}={val}\n"
                found = True
                break
        if not found:
            lines_arr.append(f"{key}={val}\n")
    
    update_or_append(lines, "ZLIBRARY_EMAIL", config.zlibrary_email)
    update_or_append(lines, "ZLIBRARY_PASSWORD", config.zlibrary_password)
    update_or_append(lines, "ZLIBRARY_REMIX_USERID", config.zlibrary_remix_userid)
    update_or_append(lines, "ZLIBRARY_REMIX_USERKEY", config.zlibrary_remix_userkey)

    with ENV_FILE.open("w", encoding="utf-8") as f:
        f.writelines(lines)
    
    return {"status": "ok"}

@app.get("/api/scripts")
def get_scripts():
    return [
        {
            "id": "collect_local_ebooks",
            "name": "本地电子书搜索与整理",
            "description": "在指定硬盘中搜索书单中的电子书，并统一归档整理。",
            "params": [
                {"key": "list_dir", "label": "书单文件目录", "default": "", "tooltip": "包含书单TXT或MD的目录路径。脚本会自动读取该目录下的所有文本并提取其中带有《》的书名。必填。"},
                {"key": "search_dir", "label": "本地搜索盘符/目录", "default": "J:\\", "tooltip": "脚本将在此目录及其子孙目录中搜索找到的书名的电子书。耗时受目录总文件数影响。"},
                {"key": "output_dir", "label": "收集输出目录", "default": "J:\\书单", "tooltip": "找到的电子书统一存放位置，会自动为每个书单建子文件夹。"},
            ]
        },
        {
            "id": "collect_ebooks_with_booklists",
            "name": "书单批量下载 (含Z-Lib)",
            "description": "先在本地搜索匹配书单电子书，缺失的部分尝试通过Z-Library网络接口补充下载。",
            "params": [
                {"key": "list_dir", "label": "书单文件目录", "default": "", "tooltip": "包含待搜集书单文件的目录，必须确保内容已被《》包围。必填。"},
                {"key": "search_dir", "label": "本地搜索基目录", "default": "J:\\", "tooltip": "本地搜索的扫描起点目录。"},
                {"key": "output_dir", "label": "输出目录", "default": "J:\\2024年豆瓣读书榜单", "tooltip": "最终电子书的保存和合并输出位置。"},
            ]
        }
    ]

@app.websocket("/api/ws/run/{script_id}")
async def run_script_websocket(websocket: WebSocket, script_id: str):
    await websocket.accept()
    # receive params
    data = await websocket.receive_json()
    params = data.get("params", {})
    
    list_dir = params.get("list_dir", "").replace("\\", "\\\\")
    search_dir = params.get("search_dir", "J:\\").replace("\\", "\\\\")
    output_dir = params.get("output_dir", "J:\\书单").replace("\\", "\\\\")
    
    if not list_dir:
        await websocket.send_text("错误：请填写书单文件目录(list_dir)后再执行！\n")
        await websocket.close()
        return

    temp_script = Path(__file__).parent / f"temp_run_{script_id}.py"
    
    if script_id == "collect_local_ebooks":
        script_code = f"""
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from pathlib import Path
from collect_local_ebooks import process_book_list_directory, check_file_list_update, generate_file_list

list_dir = r"{list_dir}"
search_dir = r"{search_dir}"
output_dir = Path(r"{output_dir}")

print("开始执行: 本地电子书搜集...")
try:
    if check_file_list_update(search_dir):
        generate_file_list(search_dir)
    process_book_list_directory(list_dir, search_dir, output_dir=output_dir)
except Exception as e:
    print(f"发生异常: {{e}}")
"""
    elif script_id == "collect_ebooks_with_booklists":
        script_code = f"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from collect_ebooks_with_booklists import process_ebooks

list_dir = r"{list_dir}"
search_dir = r"{search_dir}"
output_dir = r"{output_dir}"

print("开始执行: 批量查缺补漏与下载流程...")
try:
    process_ebooks(list_dir, search_dir, output_dir)
except Exception as e:
    print(f"发生异常: {{e}}")
"""
    else:
        await websocket.send_text("未知的脚本运行请求")
        await websocket.close()
        return

    with temp_script.open("w", encoding="utf-8") as f:
        f.write(script_code)

    process = await asyncio.create_subprocess_exec(
        sys.executable, str(temp_script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(Path(__file__).parent)
    )

    try:
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            await websocket.send_text(line.decode("utf-8", errors="replace"))
            
        await process.wait()
        await websocket.send_text(f"\n[进程结束，退出码：{process.returncode}]")
    except Exception as e:
        await websocket.send_text(f"错误: {str(e)}")
    finally:
        if temp_script.exists():
            try:
                temp_script.unlink()
            except:
                pass
        await websocket.close()

if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
