# 🖊️ AI Novel Studio (DeepSeek Edition)

> 一个基于 **DeepSeek-V3/R1** 构建的本地化、沉浸式长篇小说辅助写作 IDE。
> 融合 **分形写作法 (Fractal Writing)**、**RAG 记忆检索** 与 **知识图谱**，助你从一个灵感到百万字长篇。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![NiceGUI](https://img.shields.io/badge/UI-NiceGUI-purple)
![DeepSeek](https://img.shields.io/badge/AI-DeepSeek-blue)
![ChromaDB](https://img.shields.io/badge/RAG-ChromaDB-green)

---

## ✨ 核心亮点

### 1. 🏗️ 架构师模式 (Architect Pro)
采用 **分形写作理念**，支持从“一句话灵感”无限裂变：
- **灵感 -> 分卷 -> 章节 -> 场景流 (Beat Sheet)**。
- 集成 **DeepSeek-R1 (推理模型)**，深度推演剧情逻辑，生成高质量细纲。
- 交互式树状图管理，支持一键采纳 AI 建议到正式目录。

### 2. 📚 多项目书架管理
- 完整的 **项目隔离**：支持创建、重命名、删除多本小说。
- **独立记忆库**：每本书拥有独立的 ChromaDB 向量集合（基于 MD5 隔离），防止剧情串台。
- 自动备份与快照机制，保障数据安全。

### 3. 🧠 混合检索增强 (Hybrid RAG)
彻底解决 AI "吃书" 问题：
- **向量检索 (Vector RAG)**：自动检索前文伏笔、过往剧情。
- **图谱检索 (Graph RAG)**：基于 NetworkX 构建人物关系网，AI 写作时自动感知人物羁绊与地缘关系。

### 4. 📝 沉浸式写作台
- **双栏设计**：左侧目录/大纲，中间沉浸写作，右侧 AI 助手。
- **实时辅助**：
  - **AI 续写**：根据光标位置自动续写下文。
  - **世界观审计**：自动分析正文，提取人物状态变更（受伤、升级）并反向更新设定集。
  - **时间轴分析**：自动计算剧情内的时间流逝。

---

## 🛠️ 安装指南

### 前置要求
- Python 3.10 或更高版本
- 一个有效的 [DeepSeek API Key](https://platform.deepseek.com/)

### 1. 克隆项目
```bash
git clone https://github.com/cannotgetaname/ai_novel_studio.git
cd ai-novel-studio
```
### 2. 创建虚拟环境 (推荐)
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```
### 3. 安装依赖
```bash
pip install -r requirements.txt
```
*注意*: 首次运行时，ChromaDB 可能会下载 embedding 模型，请确保网络通畅(可能需要科学上网)。

### 4. 配置信息
复制config.example.json为config.json并填入自己的api-key


### 5. 启动应用
```bash

python main.py
```

---
## 🚀 快速上手
1. **配置 API**:
   
   * 启动后进入 "**设定 (Settings)**" -> "系统配置"。

   * 填入你的 DeepSeek API Key 并保存。

   * 建议：将 Architect 模型路由设置为 deepseek-reasoner 以获得最佳推演效果
   * 也可以将config.example.json重命名为config.json并填入key
2. **创建新书**：
   
   * 点击左上角的 "**书架**" 按钮。
   * 点击 "**新建小说**"，输入书名（支持中文）。
3. **从灵感到大纲**:
   
* 切换到 "架构 (Architect)" 标签页。

* 在根节点输入核心脑洞，点击 "AI 裂变" 生成分卷。

* 选中分卷，继续裂变生成章节。

* 满意后点击 "采纳"，大纲将自动同步到左侧写作目录。
  

4. **开始写作**：
   
   * 切换回 "**写作 (Writing)**" 标签页，点击目录中的章节开始创作！

---
## 📂 项目结构
```plaintext
ai_novel_studio/
├── config.example.json     #配置文件示例
├── config.json             #配置文件
├── main.py                 # 程序入口，UI 主框架
├── backend.py              # 核心后端 (文件IO, RAG, LLM调用)
├── requirements.txt        # 依赖列表
├── projects/               # [数据] 所有小说存储目录
│   └── MyBook/             # 单本小说结构
│       ├── chapters/       # 章节文本
│       ├── structure.json  # 目录结构
│       ├── outline_tree.json # 架构师蓝图数据
│       └── ...             # 设定集 (characters.json 等)
├── chroma_db_storage/      # [数据] 向量数据库存储
└── novel_modules/          # UI 功能模块
    ├── architect.py        # 架构师/大纲生成 UI
    ├── bookshelf.py        # 书架管理 UI
    ├── writing.py          # 编辑器与写作 UI
    ├── settings.py         # 设定集与图谱 UI
    ├── timeline.py         # 时间轴 UI
    └── state.py            # 全局状态管理 (单例模式)
```
## 🧩 技术栈
- Frontend: NiceGUI (基于 Vue/Quasar 的 Python UI 框架)
- Backend: Python 3.12+
- LLM: OpenAI SDK (兼容 DeepSeek API)
- Database:
  - JSON (结构化数据)
  - [ChromaDB](https://www.trychroma.com/) (向量检索)
  - [NetworkX](https://networkx.org/en/) (知识图谱构建)

## 🤝 贡献与反馈
这是一个个人开发的辅助写作工具，如果你有好的想法或发现了 Bug，欢迎提交 Issue 或 Pull Request！

**To-Do List**:
-  增加 epub/txt 导出功能
-  支持本地 LLM (Ollama) 接入
-  角色模拟对话 (Chat with Character)
  ---
