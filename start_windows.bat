@echo off
chcp 65001 >nul
echo ========================================
echo   AI Writer 启动脚本 (Windows)
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist "venv" (
    echo [提示] 未检测到虚拟环境，正在创建...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [成功] 虚拟环境已创建
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查依赖是否安装
pip show nicegui >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装依赖...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
)

REM 检查配置文件
if not exist "config.json" (
    if exist "config.example.json" (
        echo [提示] 未找到 config.json，正在从 config.example.json 复制...
        copy config.example.json config.json >nul
        echo [成功] 已创建 config.json，请修改其中的 API Key
    ) else (
        echo [警告] 未找到 config.json 和 config.example.json
    )
)

echo.
echo [启动] 正在启动 AI Writer...
echo.

python main.py

pause