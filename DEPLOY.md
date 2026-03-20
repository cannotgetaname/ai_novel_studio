# AI Writer 部署指南

## 快速开始

### Windows 用户

1. 双击运行 `start_windows.bat`
2. 首次运行会自动创建虚拟环境并安装依赖
3. 修改 `config.json` 中的 API Key

### Linux/macOS 用户

```bash
# 添加执行权限
chmod +x start_linux.sh

# 运行启动脚本
./start_linux.sh
```

## 手动部署步骤

### 1. 环境要求

- Python 3.9+ (推荐 3.10 或 3.11)
- pip 包管理器

### 2. 创建虚拟环境

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置

复制配置文件并修改：

```bash
cp config.example.json config.json
```

编辑 `config.json`，填入你的 API Key：

```json
{
    "api_key": "你的API密钥",
    "base_url": "https://api.deepseek.com"
}
```

### 5. 启动

```bash
python main.py
```

访问 http://localhost:8081

## 环境检测

运行环境检测脚本诊断问题：

```bash
python check_environment.py
```

## 常见问题

### 1. Python 版本问题

**症状**: 提示语法错误或模块找不到

**解决**: 
```bash
python --version  # 确认版本 >= 3.9
```

### 2. 依赖安装失败

**症状**: pip install 报错

**解决方案**:

```bash
# 升级 pip
python -m pip install --upgrade pip

# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. ChromaDB 问题

**症状**: SQLite 版本错误

**解决**:
```bash
# 安装系统级 SQLite
# Ubuntu/Debian:
sudo apt-get install sqlite3 libsqlite3-dev

# macOS:
brew install sqlite
```

### 4. 网络连接问题

**症状**: Connection error

**检查**:
1. 确认网络可以访问 API 服务
2. 检查代理设置
3. 运行 `python check_environment.py` 测试网络

### 5. Windows 编码问题

**症状**: 中文乱码

**解决**:
- 确保文件保存为 UTF-8 编码
- Windows 终端设置: `chcp 65001`

### 6. 权限问题

**症状**: 无法创建目录或写入文件

**解决**:
```bash
# Linux/macOS
chmod -R 755 .

# Windows: 以管理员身份运行
```

## 支持的 API 服务商

本项目使用 OpenAI 兼容接口，支持：

- DeepSeek (默认)
- OpenAI
- 智谱 AI
- 月之暗面
- 其他兼容 OpenAI API 的服务

修改 `config.json` 中的 `base_url` 即可切换。

## Docker 部署 (可选)

```bash
# 构建镜像
docker build -t ai-writer .

# 运行容器
docker run -d -p 8081:8081 -v ./data:/app/data ai-writer
```

## 目录结构

```
ai_writer/
├── main.py              # 主入口
├── backend.py           # 后端逻辑
├── config.json          # 配置文件 (需创建)
├── config.example.json  # 配置示例
├── requirements.txt     # 依赖列表
├── start_windows.bat    # Windows 启动脚本
├── start_linux.sh       # Linux/macOS 启动脚本
├── check_environment.py # 环境检测
├── novel_modules/       # 功能模块
│   ├── state.py
│   ├── writing.py
│   ├── settings.py
│   └── ...
└── projects/            # 小说数据 (运行后生成)
```

## 更新日志

查看 git log 或运行 `git log --oneline`
