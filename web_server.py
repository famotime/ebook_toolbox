import uvicorn
from web_api import app
import builtins
import webbrowser
from threading import Timer

def open_browser():
    webbrowser.open_new("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("启动 Ebook Toolbox Web 服务，请访问 http://127.0.0.1:8000")
    Timer(1.5, open_browser).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)
