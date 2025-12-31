# 📚 AI Novel Studio (AI 网文工作站)

![Version](https://img.shields.io/badge/Version-V15.1-blue) ![Python](https://img.shields.io/badge/Python-3.10%2B-green) ![DeepSeek](https://img.shields.io/badge/AI-DeepSeek_V3%2FR1-purple) ![License](https://img.shields.io/badge/License-MIT-orange)

**AI Novel Studio** 是一个专为**百万字长篇网文**创作设计的本地化 AI 辅助系统。

它拒绝做简单的“聊天机器人”，而是基于 **RAG（检索增强生成）**、**分形递归总结** 和 **状态自动审计** 三大核心技术，解决长篇创作中“逻辑崩坏”、“设定遗忘”和“剧情注水”的痛点。

> **当前版本特性**：模块化架构 | 分卷管理支持 | DeepSeek R1 深度推理 | 全书剧情递归总结

---

## ✨ 核心亮点

### 1. 📖 结构化分卷管理 (New)
告别扁平的章节列表，支持专业的**“分卷-章节”**树状结构。
- **层级管理**：支持创建、重命名、删除分卷（Volume）。
- **定点插入**：可在指定分卷下新建章节，支持折叠/展开视图。
- **拖拽式体验**：(UI 层面) 左侧侧边栏采用折叠面板设计，清晰管理庞大目录。

### 2. 🧠 递归式剧情总结 (Map-Reduce)
让 AI 拥有“上帝视角”，不再写出前后矛盾的剧情。
- **单章摘要**：每次保存章节时，后台自动生成 150 字精炼摘要。
- **全书总纲**：基于所有单章摘要，递归生成/更新**“全书剧情脉络”**。
- **记忆注入**：在写第 500 章时，AI 依然能通过总纲记得第 1 章的核心伏笔。

### 3. 🌍 动态世界审计 (State Audit)
利用 **DeepSeek-R1 (Reasoner)** 的强大逻辑能力，自动维护世界观一致性。
- **自动结算**：写完一章后，AI 会“审计”正文，自动提取：
    - 🩸 **人物状态**（如：重伤、升级、黑化）
    - 🎒 **物品流转**（如：获得神器、丢失信物）
    - 🕸️ **关系变更**（如：结仇、拜师）
- **数据库同步**：一键将变更同步到底层 JSON 数据库，无需手动修改设定集。

### 4. 🚀 智能写作引擎
- **Smart RAG**：在生成正文前，自动检索向量库（ChromaDB）中的历史记忆，并进行“智能清洗”，排除干扰信息。
- **多模型路由**：
    - **写作 (Writer)**：高温度，使用 DeepSeek-V3，文笔更具创造力。
    - **架构 (Architect)**：使用 DeepSeek-R1，逻辑严密，擅长伏笔设计。
    - **审稿 (Reviewer)**：低温度，毒舌风格，精准指出逻辑漏洞。

### 5. 📊 可视化与交互
- **人物关系图谱**：力导向图展示角色社交网络。
- **自动化时间轴**：AI 自动分析正文中的时间流逝（如“三天后”），生成可视化时间线。
- **局部重绘**：选中正文某一段，让 AI 针对性润色或改写。

---

## 🛠️ 技术架构

本项目采用前后端分离（但在同一进程中运行）的模块化设计：

* **前端 UI**: [NiceGUI](https://nicegui.io/) (基于 Vue + FastAPI，全异步极速交互)
* **后端逻辑**: Python (Asyncio)
* **向量数据库**: ChromaDB (本地存储，隐私安全)
* **大模型接口**: OpenAI 兼容协议 (默认适配 DeepSeek)
* **数据存储**: 纯 JSON 文本存储 (Chapters/Settings/Volumes)，方便迁移和版本控制。

---

## 🚀 快速开始

### 1. 环境准备
推荐使用 Python 3.10 或更高版本。
我用的3.12.2

```
# 1. 克隆项目
git clone https://github.com/cannotgetaname/ai_novel_studio.git
cd ai-novel-studio

# 2. 创建虚拟环境 (推荐)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. 安装依赖
pip install nicegui chromadb openai```

2. 配置文件
在项目根目录创建 config.json 文件（可复制 config.example.json），并填入你的 API Key。

```

{
    "api_key": "sk-your-deepseek-api-key",
    "base_url": "[https://api.deepseek.com](https://api.deepseek.com)",
    "project_dir": "MyNovel_Data",
    "models": {
        "writer": "deepseek-chat",
        "architect": "deepseek-reasoner",
        "auditor": "deepseek-reasoner"
    },
    "prompts": {
        "writer_system": "你是一个网文大神..."
    }
}
3. 运行系统


python main.py
终端显示 NiceGUI ready 后，浏览器会自动打开 http://localhost:8080。

📖 使用指南
侧边栏 (目录管理)：

点击 “新建分卷” 创建你的第一卷。

在分卷下点击 “+” 号添加章节。

点击 “📖 全书梗概” 查看 AI 自动生成的剧情总纲。

写作 Tab：

输入标题和大纲，点击 “🚀 生成”。

写完后点击 “🌍 结算”，让 AI 帮你更新人物状态。

点击 “💾 保存”，后台会自动更新剧情摘要。

设定 Tab：

管理人物、物品、地点。支持列表模式和图谱模式切换。

架构师 Tab：

输入“后续剧情走向”，让 AI 基于全书伏笔为你规划未来 10 章的大纲。

🤝 贡献与协议
欢迎提交 Issue 或 Pull Request！ 本项目遵循 MIT 开源协议。

Made with ❤️ by AI Novel Studio Team