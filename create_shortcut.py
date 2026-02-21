import os
import subprocess

desktop = os.path.join(os.path.expanduser("~"), "Desktop")
project_dir = r"C:\Users\雨下雨停\Desktop\VideoPromptAnalyzer"

# 创建一个启动脚本到桌面
script_content = f"""@echo off
cd /d "{project_dir}"
call 启动.bat
"""

shortcut_bat = os.path.join(desktop, "视频分析工具.bat")
with open(shortcut_bat, "w", encoding="gbk") as f:
    f.write(script_content)

print(f"快捷方式已创建到桌面: {shortcut_bat}")
