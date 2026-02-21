@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ================================
echo Video Prompt Analyzer
echo 视频镜头分析 ^& 提示词反推工具
echo ================================
echo.

REM 检查虚拟环境
if not exist "venv" (
    echo [1/2] 创建虚拟环境...
    py -m venv venv
    echo 虚拟环境创建完成
    echo.
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查依赖
echo [2/2] 检查依赖...
py -m pip install -q -r requirements.txt

echo.
echo ================================
echo 启动应用...
echo ================================
echo.

py main.py

pause
