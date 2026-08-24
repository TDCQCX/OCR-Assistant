@echo off
rem 构建 Windows 可执行程序(按版本输出到 dist\)
cd /d "%~dp0"
set VERSION=1.0.0
.\.venv\Scripts\python.exe scripts\make_icon.py
if not exist assets mkdir assets
.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --windowed --onefile ^
  --name "OCR助手-v%VERSION%" ^
  --icon "assets\app.ico" ^
  --version-file "version_info.txt" ^
  --collect-all rapidocr_onnxruntime ^
  --hidden-import PIL._tkinter_finder ^
  main.py
echo.
echo 构建完成: dist\OCR助手-v%VERSION%.exe
pause
