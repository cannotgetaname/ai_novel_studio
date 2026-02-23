# 🖊️ AI 网文工作站 - 从灵感直达百万字

> 一款现代化的AI辅助写作IDE，融合**混合检索增强(RAG)**、**知识图谱**与**分形写作法**，助你从一个灵感到完成百万字长篇。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![NiceGUI](https://img.shields.io/badge/UI-NiceGUI-purple)
![AI](https://img.shields.io/badge/AI-Compatible-blue)
![ChromaDB](https://img.shields.io/badge/RAG-ChromaDB-green)

---

## ✨ 核心特性

### 🏗️ 分形架构师
- **分形写作理念**：从"一句话灵感"无限裂变为完整长篇
- **AI驱动推演**：自动生成分卷、章节大纲，确保逻辑连贯
- **可视化管理**：树状图展示作品结构，直观掌控全局

### 📚 多项目管理
- **书架系统**：轻松创建、切换和管理多个写作项目
- **数据隔离**：每本书独立的记忆库，防止剧情混乱
- **自动备份**：定时备份机制，保护创作成果

### 🧠 混合智能增强
- **向量检索(RAG)**：自动检索前文伏笔，保持剧情一致性
- **知识图谱**：人物关系、地点连接、物品归属智能追踪
- **世界观审计**：实时更新角色状态、物品归属等设定

### 📝 沉浸式创作
- **双栏布局**：目录大纲+写作面板+AI助手三重体验
- **智能辅助**：AI续写、局部重绘、智能审稿等功能
- **实时同步**：自动保存与记忆库更新，专注创作本身

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- 有效的AI服务API Key (支持OpenAI、DeepSeek等兼容接口)

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/cannotgetaname/ai_novel_studio.git
cd ai_novel_studio
```

2. **创建虚拟环境** (推荐)
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
*注：首次运行时ChromaDB会下载embedding模型，请确保网络畅通*

4. **配置API**
```bash
cp config.example.json config.json
# 编辑config.json，填入你的API密钥
```

5. **启动应用**
```bash
python main.py
```
访问 http://localhost:8080 即可开始创作

---

## 💡 使用指南

### 1. 项目配置
- 进入"设定" → "系统配置"页面
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

### 4. 开始创作
- 点击左侧章节列表开始写作
- 利用"🚀 生成"按钮让AI协助续写
- 使用"🌍 结算"功能更新世界观设定
- "🔍 审稿"功能提供智能写作建议

---

## 🔧 功能详解

### 写作功能
- **AI续写**：基于上下文智能续写内容
- **局部重绘**：选中文本让AI优化特定段落
- **智能审稿**：检查逻辑一致性、文笔质量
- **自动保存**：实时同步到向量数据库

### 设定管理
- **人物卡**：详细的角色设定和关系管理
- **世界观**：完整的世界背景设定
- **物品系统**：法宝、装备等物品设定
- **地点管理**：地理环境和势力分布

### 知识管理
- **时间轴**：追踪剧情时间线
- **关系图谱**：可视化人物关系网
- **历史快照**：章节版本管理
- **全文检索**：快速定位关键信息

---

## 🏗️ 技术架构

- **前端框架**: NiceGUI (基于Vue.js的Python Web框架)
- **AI接口**: OpenAI SDK (兼容各种API服务)
- **向量数据库**: ChromaDB (高效相似度检索)
- **知识图谱**: NetworkX (复杂关系建模)
- **数据存储**: JSON (轻量级持久化)

### 核心模块
```
ai_novel_studio/
├── main.py                 # 应用入口
├── backend.py              # 核心业务逻辑
├── run_app.py              # 运行脚本
├── novel_modules/          # 功能模块
│   ├── architect.py        # 架构师模块
│   ├── bookshelf.py        # 书架管理
│   ├── writing.py          # 写作界面
│   ├── settings.py         # 设定管理
│   ├── timeline.py         # 时间轴
│   └── state.py            # 状态管理
├── projects/               # 项目数据
├── chroma_db_storage/      # 向量数据库
└── config.json             # 配置文件
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