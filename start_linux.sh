#!/bin/bash
echo "========================================"
echo "  AI Writer 启动脚本 (Linux/macOS)"
echo "========================================"
echo

# 检测系统类型
OS_TYPE=$(uname -s)
echo "[信息] 操作系统: $OS_TYPE"

# 检查 Python 是否安装
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "[错误] 未检测到 Python，请先安装 Python 3.9+"
    exit 1
fi

echo "[信息] Python 版本: $($PYTHON_CMD --version)"

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[提示] 未检测到虚拟环境，正在创建..."
    $PYTHON_CMD -m venv venv
    if [ $? -ne 0 ]; then
        echo "[错误] 创建虚拟环境失败"
        exit 1
    fi
    echo "[成功] 虚拟环境已创建"
fi

# 激活虚拟环境
source venv/bin/activate

# 检查依赖是否安装
if ! pip show nicegui &> /dev/null; then
    echo "[提示] 正在安装依赖..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "[错误] 依赖安装失败"
        exit 1
    fi
fi

# 检查配置文件
if [ ! -f "config.json" ]; then
    if [ -f "config.example.json" ]; then
        echo "[提示] 未找到 config.json，正在从 config.example.json 复制..."
        cp config.example.json config.json
        echo "[成功] 已创建 config.json，请修改其中的 API Key"
    else
        echo "[警告] 未找到 config.json 和 config.example.json"
    fi
fi

echo
echo "[启动] 正在启动 AI Writer..."
echo

$PYTHON_CMD main.py