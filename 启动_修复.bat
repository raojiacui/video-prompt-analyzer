@echo off
chcp 65001 >nul
set QT_QPA_PLATFORM_PLUGIN_PATH=C:\Users\雨下雨停\AppData\Local\Programs\Python\Python314\Lib\site-packages\PyQt5\Qt5\plugins
cd /d "%~dp0"
py main.py
pause
