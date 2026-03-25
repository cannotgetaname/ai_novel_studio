# 🖊️ AI 网文工作站 - 从灵感直达百万字

> 一款现代化的AI辅助写作IDE，融合**混合检索增强(RAG)**、**知识图谱**与**分形写作法**，助你从一个灵感到完成百万字长篇。

![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![NiceGUI](https://img.shields.io/badge/UI-NiceGUI-purple)
![AI](https://img.shields.io/badge/AI-Compatible-blue)
![ChromaDB](https://img.shields.io/badge/RAG-ChromaDB-green)

---

## ✨ 核心特性

### 🏗️ 分形架构师
- **分形写作理念**：从"一句话灵感"无限裂变为完整长篇
- **AI驱动推演**：自动生成分卷、章节大纲，确保逻辑连贯
- **可视化管理**：树状图展示作品结构，直观掌控全局

### 🧰 智能工具箱
- **8大工具类别**：起名大全、角色生成器、书名生成器、冲突生成器、简介生成器、场景生成器、金手指生成器、剧情转折
- **20+创作工具**：涵盖网文创作全流程
- **一键保存**：生成结果可直接保存到人物库、物品库、地点库

### 📖 拆书分析
- **多格式支持**：支持 TXT、DOCX 文件上传
- **智能解析**：自动识别章节结构
- **五维分析**：综合分析、结构分析、人物分析、语言分析、情节分析

### 🧠 混合智能增强
- **向量检索(RAG)**：自动检索前文伏笔，保持剧情一致性
- **知识图谱**：人物关系、地点连接、物品归属智能追踪
- **世界观审计**：实时更新角色状态、物品归属等设定

### 🌍 世界观管理
- **结构化字段**：基本信息、核心设定、关键元素、背景故事四大板块
- **预设模板**：玄幻修仙、科幻赛博、都市异能、古风武侠
- **一致性检查**：AI 自动检测世界观设定中的矛盾

### 💰 费用管理
- **Token 计费**：精确统计 AI 调用成本
- **多模型定价**：支持 DeepSeek、GPT-4、Claude 等主流模型
- **趋势分析**：查看每日、每周、每月费用统计

### 🎯 写作目标
- **目标设定**：支持日目标、周目标、月目标
- **进度追踪**：实时显示写作进度
- **连续天数**：激励持续创作

---

## 🚀 快速开始

### 环境要求

| 项目 | 要求 |
|------|------|
| Python | 3.9+ (推荐 3.12) |
| 操作系统 | Windows / Linux / macOS |
| 网络 | 能访问 AI API 服务 |

### 一键启动

#### Windows 用户

双击运行 `start_windows.bat`，脚本会自动：
- 检测并创建虚拟环境
- 安装所需依赖
- 创建配置文件（如不存在）
- 启动应用

#### Linux/macOS 用户

```bash
# 添加执行权限（首次需要）
chmod +x start_linux.sh

# 运行启动脚本
./start_linux.sh
```

### 手动安装

<details>
<summary>点击展开详细步骤</summary>

1. **克隆项目**
```bash
git clone https://github.com/cannotgetaname/ai_novel_studio.git
cd ai_novel_studio
```

2. **创建虚拟环境**
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

3. **安装依赖**
```bash
pip install -r requirements.txt
```

> 💡 国内用户可使用镜像加速：
> ```bash
> pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
> ```

4. **配置 API**

复制配置模板并修改：
```bash
cp config.example.json config.json
```

编辑 `config.json`，填入你的 API 密钥：
```json
{
    "api_key": "你的API密钥",
    "base_url": "https://api.deepseek.com"
}
```

5. **启动应用**
```bash
python main.py
```

访问 http://localhost:8081 开始创作

</details>

### 环境诊断

如遇到问题，运行诊断脚本：

```bash
python check_environment.py
```

脚本会自动检测：
- ✅ Python 版本
- ✅ 依赖安装状态
- ✅ 文件完整性
- ✅ 配置正确性
- ✅ 网络连接
- ✅ ChromaDB 功能

---

## 🔧 配置说明

### 支持的 API 服务

本项目使用 OpenAI 兼容接口，支持以下服务：

| 服务商 | base_url | 备注 |
|--------|----------|------|
| DeepSeek | `https://api.deepseek.com` | 默认，性价比高 |
| OpenAI | `https://api.openai.com/v1` | 官方接口 |
| 智谱 AI | `https://open.bigmodel.cn/api/paas/v4` | 国产大模型 |
| 月之暗面 | `https://api.moonshot.cn/v1` | Kimi 模型 |
| Ollama | `http://localhost:11434/v1` | 本地部署 |

### 模型配置

在 `config.json` 中可为不同任务指定不同模型：

```json
{
    "models": {
        "writer": "deepseek-chat",      // 写作
        "architect": "deepseek-reasoner", // 架构规划
        "reviewer": "deepseek-chat",    // 审稿
        "auditor": "deepseek-reasoner"  // 状态审计
    }
}
```

---

## 💡 使用指南

### 1. 项目配置
- 进入"系统设置" → "API与模型"页面
- 填入API密钥和模型配置
- 保存设置并测试连接

### 2. 创建新书
- 点击左侧书架管理区域的"📚 切换/管理书籍"
- 选择"新建小说"，输入书名
- 系统将自动创建项目结构

### 3. 构建大纲
- 切换到"架构"标签页
- 在世界观设定中输入核心概念
- 使用AI架构师功能生成分卷和章节大纲
- 采纳满意的大纲到正式目录

### 4. 使用智能工具箱
- 切换到"智能工具箱"标签页
- 选择工具类别（如起名大全、角色生成器）
- 点击具体工具，设置参数后生成
- 生成结果可保存到素材库

### 5. 拆书学习
- 切换到"拆书分析"标签页
- 上传 TXT 或 DOCX 格式的参考作品
- 选择分析维度，开始分析
- 查看多维度分析结果，学习写作技法

### 6. 开始创作
- 点击左侧章节列表开始写作
- 利用"🚀 生成"按钮让AI协助续写
- 使用"🌍 结算"功能更新世界观设定
- "🔍 审稿"功能提供智能写作建议

---

## 🐳 Docker 部署

```bash
# 构建镜像
docker build -t ai-writer .

# 运行容器
docker run -d -p 8081:8081 -v ./data:/app/data ai-writer
```

---

## ❓ 常见问题

<details>
<summary>Python 版本不兼容</summary>

确保 Python 版本 >= 3.9：
```bash
python --version
```

如版本过低，请从 [python.org](https://www.python.org/downloads/) 下载新版本。
</details>

<details>
<summary>依赖安装失败</summary>

尝试以下方案：
```bash
# 升级 pip
python -m pip install --upgrade pip

# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```
</details>

<details>
<summary>ChromaDB SQLite 错误</summary>

Linux/macOS:
```bash
# Ubuntu/Debian
sudo apt-get install sqlite3 libsqlite3-dev

# macOS
brew install sqlite
```
</details>

<details>
<summary>网络连接失败</summary>

1. 检查网络是否能访问 API 服务
2. 如使用代理，确保代理配置正确
3. 运行 `python check_environment.py` 测试网络连通性
</details>

<details>
<summary>Windows 中文乱码</summary>

在 CMD 中执行：
```cmd
chcp 65001
```

或使用 PowerShell / Windows Terminal。
</details>

---

## 🏗️ 技术架构

- **前端框架**: NiceGUI (基于Vue.js的Python Web框架)
- **AI接口**: OpenAI SDK (兼容各种API服务)
- **向量数据库**: ChromaDB (高效相似度检索)
- **知识图谱**: NetworkX (复杂关系建模)
- **数据存储**: JSON (轻量级持久化)

### 核心模块
```
ai_writer/
├── main.py                 # 应用入口
├── backend.py              # 核心业务逻辑
├── config.json             # 配置文件
├── config.example.json     # 配置模板
├── requirements.txt        # 依赖列表
├── start_windows.bat       # Windows 启动脚本
├── start_linux.sh          # Linux/macOS 启动脚本
├── check_environment.py    # 环境诊断工具
├── novel_modules/          # 功能模块
│   ├── architect.py        # 架构师模块
│   ├── bookshelf.py        # 书架管理
│   ├── writing.py          # 写作界面
│   ├── settings.py         # 设定管理
│   ├── timeline.py         # 时间轴
│   ├── state.py            # 状态管理
│   ├── toolbox.py          # 智能工具箱
│   ├── book_analysis.py    # 拆书分析
│   ├── billing.py          # 费用管理
│   └── goals.py            # 写作目标
├── data/                   # 全局数据 (运行后生成)
│   └── global/             # 跨项目数据
├── projects/               # 项目数据 (运行后生成)
└── chroma_db/              # 向量数据库 (运行后生成)
```

---

## 🤝 贡献与支持

这是一个开源的个人写作辅助工具，欢迎任何形式的贡献：

- 报告Bug或提出功能建议
- 提交代码改进
- 完善文档
- 分享使用经验

### 待办事项
- [ ] 增强EPUB/TXT导出功能
- [ ] 集成本地LLM支持(Ollama)
- [ ] 开发角色对话模拟功能
- [ ] 添加团队协作功能

---

## 📄 许可证

本项目仅供学习和个人使用。

---

## 🙏 致谢

感谢所有为AI创作工具做出贡献的开发者，以及在创作路上不懈努力的写作者们。