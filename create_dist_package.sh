#!/bin/bash
# 创建分发用的压缩包

echo "创建分发压缩包..."

cd /home/zcz/program/ai_writer/dist

# 清理不必要的文件（测试数据等）
rm -rf ai_writer/chroma_db_storage ai_writer/config.json ai_writer/data/MyFirstNovel 2>/dev/null

# 创建 zip 包
zip -r ai_writer_linux_x64.zip ai_writer/

SIZE=$(du -sh ai_writer_linux_x64.zip | cut -f1)
echo "压缩包: ai_writer_linux_x64.zip (${SIZE})"
echo "位置: /home/zcz/program/ai_writer/dist/"