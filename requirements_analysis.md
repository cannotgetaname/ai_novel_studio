# AI 网文工作站 依赖分析与精简方案

## 原始依赖 (requirements.txt)
包含132个包，总计约3MB+，但实际项目中仅使用了少数几个核心包。

## 实际使用分析
通过扫描项目源码，发现实际导入和使用的包如下：

### 核心运行时依赖
1. `nicegui` - UI框架 (必须)
2. `openai` - AI模型接口 (必须)
3. `chromadb` - 向量数据库 (必须)
4. `networkx` - 图分析 (必须)
5. `python-dateutil` - 时间处理 (必须)

### 内置库 (无需安装)
- `json`, `os`, `uuid`, `datetime`, `asyncio`, `hashlib`, `shutil`, `glob`, `traceback`, `copy`, `colorsys`, `time`, `sys`

### 总结
项目实际仅需5个第三方包，相比原来的132个大幅减少。移除了大量未使用的包如：
- Flask/FastAPI系列 (项目使用NiceGUI自带的服务器)
- Pandas/Numpy (项目未做数据分析)
- 大量工具包和辅助库