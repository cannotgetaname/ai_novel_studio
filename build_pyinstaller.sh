#!/bin/bash
# PyInstaller 打包脚本 - 最终版本
# 已验证可正常运行

echo "========================================"
echo "  AI Writer PyInstaller 打包脚本"
echo "========================================"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

source venv/bin/activate

# 清理旧构建
rm -rf build dist *.spec 2>/dev/null

echo "[信息] 开始打包..."

# 使用 PyInstaller 打包
# --collect-all chromadb/nicegui: 收集所有子模块和资源
# --copy-metadata: 复制元数据
pyinstaller main.py \
    --name ai_writer \
    --noconfirm \
    --clean \
    --collect-all chromadb \
    --collect-all nicegui \
    --collect-data sentence_transformers \
    --copy-metadata chromadb \
    --copy-metadata nicegui \
    --hidden-import=posthog \
    --hidden-import=overrides \
    --hidden-import=onnxruntime \
    --hidden-import=tokenizers \
    --add-data "novel_modules:novel_modules" \
    --add-data "config.example.json:." \
    --exclude-module pytest \
    --exclude-module hypothesis \
    --exclude-module tkinter \
    --exclude-module matplotlib \
    --exclude-module IPython \
    --console \
    2>&1 | tail -20

# 检查结果
if [ -d "dist/ai_writer" ]; then
    cd dist/ai_writer

    # 创建启动脚本
    cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
if [ ! -f config.json ]; then
    cp config.example.json config.json
    echo "========================================"
    echo "已创建 config.json"
    echo "请修改 API Key 后重新运行此脚本"
    echo "========================================"
    exit 0
fi
echo "启动 AI Writer..."
echo "请在浏览器访问 http://localhost:8081"
./ai_writer
EOF
    chmod +x start.sh

    mkdir -p projects data/global

    SIZE=$(du -sm . | cut -f1)
    echo
    echo "[成功] 打包完成！"
    echo "[输出] dist/ai_writer/"
    echo "[体积] 约 ${SIZE} MB"
    echo
    echo "[部署说明]"
    echo "1. 将 dist/ai_writer/ 目录打包发送给用户"
    echo "2. 用户解压后运行 ./start.sh"
    echo "3. 首次运行会创建 config.json，需修改 API Key"
    echo "4. 再次运行 ./start.sh"
    echo "5. 浏览器访问 http://localhost:8081"
else
    echo "[错误] 打包失败"
    exit 1
fi