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

#### 克隆项目
```bash
git clone [https://github.com/cannotgetaname/ai_novel_studio.git](https://github.com/cannotgetaname/ai_novel_studio.git)
cd ai-novel-studio
```
#### 创建虚拟环境 (推荐)
```bash

python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```
#### 安装依赖
```bash

pip install nicegui chromadb openai
```
### 2. 配置文件
在项目根目录创建 config.json 文件（可复制 config.example.json），并填入你的 API Key。

```json

{
    "api_key": "YOUR_API_KEY",
    "base_url": "[https://api.deepseek.com](https://api.deepseek.com)",
    "project_dir": "MyNovel_Data",
    "chroma_db_path": "chroma_db",
    "chunk_size": 500,
    "overlap": 100,
    "models": {
        "writer": "deepseek-chat",
        "architect": "deepseek-reasoner",
        "editor": "deepseek-chat",
        "reviewer": "deepseek-chat",
        "timekeeper": "deepseek-chat",
        "auditor": "deepseek-reasoner",
        "summary": "deepseek-chat"
    },
    "temperatures": {
        "writer": 1.5,
        "architect": 1.0,
        "editor": 0.7,
        "reviewer": 0.5,
        "timekeeper": 0.1,
        "auditor": 0.6,
        "summary": 0.5
    },
    "prompts": {
        "writer_system": "你是一个顶级网文作家，擅长热血、快节奏、爽点密集的风格。写作要求：\n1. 【黄金法则】多用“展示”而非“讲述”（Show, don't tell）。\n2. 【对话驱动】通过对话推动剧情和塑造性格，拒绝大段枯燥的心理描写。\n3. 【感官描写】调动视觉、听觉、触觉，增加代入感。\n4. 【节奏把控】详略得当，战斗场面要干脆利落，日常互动要有趣味。\n请根据提供的大纲、世界观和上下文，撰写引人入胜的正文。",
        
        "architect_system": "你是一个精通起承转合的剧情架构师。你的任务是基于前文和伏笔，规划后续章节。要求：\n1. 【逻辑严密】后续剧情必须符合人物性格逻辑，不能机械降神。\n2. 【冲突制造】每一章都必须有一个核心冲突或悬念钩子。\n3. 【伏笔回收】尝试利用历史记忆中的伏笔。\n请严格只返回一个标准的 JSON 列表，不要包含 Markdown 标记或其他废话。",
        
        "knowledge_filter_system": "你是一个专业的资料整理助手。你的任务是从检索到的碎片信息中，剔除无关噪音，筛选出对当前章节写作真正有帮助的背景信息（如人物之前的恩怨、物品的特殊设定、地点的具体样貌）。如果片段与当前剧情无关，请忽略。",
        
        "reviewer_system": "你是一个以毒舌著称的严厉网文主编。请从以下维度审查正文：\n1. 【人设一致性】人物言行是否符合其性格和身份？\n2. 【剧情逻辑】是否有前后矛盾或不合理的转折？\n3. 【爽点节奏】是否过于拖沓？是否有期待感？\n请输出一份 Markdown 格式的报告，不仅要指出问题，还要给出具体的修改建议。",
        
        "timekeeper_system": "你是一个精确的时间记录员。你的任务是分析正文，推算时间流逝。输出必须是严格的 JSON 格式：{\"label\": \"当前时间点(如：修仙历10年春)\", \"duration\": \"本章经过的时间(如：3天)\", \"events\": [\"事件1\", \"事件2\"]}。请只输出 JSON。",
        
        "auditor_system": "你是一个世界观数据库管理员。你的任务是分析小说正文，提取状态变更。你需要敏锐地捕捉隐性信息（例如：'他断了一臂' -> 状态: 重伤/残疾）。\n\n请严格按以下 JSON 结构输出（不要使用 Markdown 代码块）：\n{\n  \"char_updates\": [{\"name\": \"名字\", \"field\": \"属性名\", \"new_value\": \"新值\"}],\n  \"item_updates\": [{\"name\": \"物品名\", \"field\": \"属性名\", \"new_value\": \"新值\"}],\n  \"new_chars\": [{\"name\": \"名字\", \"gender\": \"性别\", \"role\": \"角色类型\", \"status\": \"状态\", \"bio\": \"简介\"}],\n  \"new_items\": [{\"name\": \"物品名\", \"type\": \"类型\", \"owner\": \"持有者\", \"desc\": \"描述\"}],\n  \"new_locs\": [{\"name\": \"地名\", \"faction\": \"所属势力\", \"desc\": \"描述\"}],\n  \"relation_updates\": [{\"source\": \"主角\", \"target\": \"配角\", \"type\": \"关系类型\"}]\n}",
        
        "summary_chapter_system": "你是一个专业的网文编辑，擅长提炼剧情精华。请将给定的小说章节压缩成 150 字以内的摘要。要求：\n1. 保留核心冲突和结果。\n2. 记录关键道具或人物的获得/损失。\n3. 记录重要的伏笔。\n不要写流水账，要写干货。",
        
        "summary_book_system": "你是一个资深主编，拥有宏观的上帝视角。请根据各章节的摘要，梳理出整本书目前的剧情脉络（Story Arc）。要求：\n1. 串联主要故事线，忽略支线细枝末节。\n2. 明确主角目前的处境、目标和成长阶段。\n3. 篇幅控制在 500 字左右，适合快速回顾。"
    }
}
```
## 3. 运行
```bash

python main.py
```
终端显示 NiceGUI ready 后，浏览器会自动打开 http://localhost:8080。

## 📖 使用指南
### 侧边栏 (目录管理)：
点击 “新建分卷” 创建你的第一卷。

在分卷下点击 “+” 号添加章节。

支持修改分卷名和章节名

点击 “📖 全书梗概” 查看 AI 自动生成的剧情总纲。
下方有全局查找替换、灵感百宝箱

### 写作 Tab：
输入标题和大纲，点击 “🚀 生成”。

写完后点击 “🌍 结算”，让 AI 帮你更新人物状态。

点击 “💾 保存”，后台会自动更新剧情摘要。

可查看历史闪照和备份

可局部重绘

支持ai审稿

### 设定 Tab：
管理世界观、人物、物品、地点。支持列表模式和图谱模式切换。

系统配置支持修改api-key,LLM路由、提示词、备份等


### 架构师 Tab：
输入“后续剧情走向”，让 AI 基于全书伏笔为你规划未来 10 章的大纲。

### 时间轴 Tab：
根据正文提取时间轴

## 🤝 贡献与协议
欢迎提交 Issue 或 Pull Request！ 本项目遵循 MIT 开源协议。

Made with ❤️ by cannotgetaname