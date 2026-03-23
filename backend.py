import json
import os
import asyncio
import time
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
import shutil # <--- 新增
import glob   # <--- 新增
from datetime import datetime # <--- 必须加这一行！
import re  # 用于字数统计的正则表达式

import networkx as nx

import hashlib


def count_words(text):
    """
    精确统计字数，区分中英文
    返回: {
        'chinese': 中文字数,
        'english': 英文单词数,
        'total_chars': 总字符数,
        'pure_chars': 纯文字符数(不含空格),
        'total_words': 总字数(中文字+英文词)
    }
    """
    if not text:
        return {
            'chinese': 0,
            'english': 0,
            'total_chars': 0,
            'pure_chars': 0,
            'total_words': 0
        }

    # 统计中文字符数
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))

    # 统计英文单词数
    english_words = len(re.findall(r'[a-zA-Z]+', text))

    # 统计数字
    numbers = len(re.findall(r'\d+', text))

    # 总字符数（含空格、标点）
    total_chars = len(text)

    # 纯文字符数（不含空格）
    pure_chars = len(re.sub(r'\s', '', text))

    # 总字数 = 中文字 + 英文词 + 数字组
    # 这是网文常用的统计方式
    total_words = chinese_chars + english_words + numbers

    return {
        'chinese': chinese_chars,
        'english': english_words,
        'numbers': numbers,
        'total_chars': total_chars,
        'pure_chars': pure_chars,
        'total_words': total_words
    }

class WorldGraph:
    def __init__(self, manager):
        self.manager = manager
        self.G = nx.DiGraph() # 有向图

    # 【核心】从现有的 app_state 动态构建图谱
    # 每次写作前调用一次，保证数据最新
    def rebuild(self):
        self.G.clear()
        
        # 1. 加载人物数据 (现有格式)
        # char: {'name': '叶凡', 'relations': [{'target': '黑皇', 'type': '损友'}]}
        chars = self.manager.load_characters()
        for c in chars:
            # 添加人物节点
            self.G.add_node(c['name'], type='character', desc=c.get('bio', '')[:50])
            
            # 添加人物关系边
            for rel in c.get('relations', []):
                # 确保目标节点也存在（防止死链）
                if rel['target']:
                    self.G.add_edge(c['name'], rel['target'], relation=rel['type'], weight=2)

        # 2. 加载地点数据 (现有格式)
        # loc: {'name': '紫山', 'neighbors': ['矿区'], 'parent': '北域'}
        locs = self.manager.load_locations()
        for l in locs:
            # 添加地点节点
            self.G.add_node(l['name'], type='location', desc=l.get('desc', '')[:50])
            
            # 添加拓扑连接 (双向边)
            for n in l.get('neighbors', []):
                self.G.add_edge(l['name'], n, relation="连通", weight=1)
            
            # 添加行政归属 (父子边)
            if l.get('parent'):
                self.G.add_edge(l['name'], l['parent'], relation="属于", weight=0.5)

        # 3. 加载物品数据 (现有格式) -> 关联到持有者
        # item: {'name': '万物母气鼎', 'owner': '叶凡'}
        items = self.manager.load_items()
        for i in items:
            self.G.add_node(i['name'], type='item', desc=i.get('desc', '')[:50])
            if i.get('owner'):
                self.G.add_edge(i['owner'], i['name'], relation="持有", weight=3)

    # --- GraphRAG 功能：获取某人的"关系网文本" ---
    def get_context_text(self, center_node, hops=1):
        if center_node not in self.G: return ""
        
        # 提取 1-2 跳的子图
        # 比如：叶凡 ->(持有)-> 鼎； 叶凡 ->(仇人)-> 姬皓月
        nodes = {center_node}
        for _ in range(hops):
            new_nodes = set()
            for n in nodes:
                new_nodes.update(self.G.neighbors(n))      # 我连别人
                new_nodes.update(self.G.predecessors(n))   # 别人连我
            nodes.update(new_nodes)
        
        subgraph = self.G.subgraph(nodes)
        
        # 转成自然语言文本，喂给 AI
        lines = []
        for u, v, d in subgraph.edges(data=True):
            rel = d.get('relation', '关联')
            lines.append(f"- {u} {rel} {v}")
            
        return "\n".join(lines)

    # --- 寻路功能：查找两者关系 ---
    def find_relation_path(self, start, end):
        try:
            path = nx.shortest_path(self.G, start, end)
            return " -> ".join(path)
        except (nx.NetworkXError, nx.NodeNotFound, nx.NetworkXNoPath):
            return ""
    # 【新增】导出 ECharts 可视化数据
    def get_echarts_data(self):
        nodes = []
        links = []
        categories = [{"name": "character"}, {"name": "location"}, {"name": "item"}]
        
        # 颜色配置 (Hardcoded for stability)
        color_map = {
            "character": "#5470c6", # 蓝
            "location": "#91cc75",  # 绿
            "item": "#fac858"       # 黄
        }

        for n, attr in self.G.nodes(data=True):
            ntype = attr.get('type', 'unknown')
            # 根据类型决定大小
            symbol_size = 30
            if ntype == 'location': symbol_size = 40
            elif ntype == 'item': symbol_size = 20
            
            nodes.append({
                "name": n,
                "category": ntype, # 对应 categories 下标或名称
                "symbolSize": symbol_size,
                "draggable": True,
                "value": attr.get('desc', '')[:20],
                "itemStyle": {"color": color_map.get(ntype, '#ccc')},
                "label": {"show": True, "position": "right"}
            })
        
        for u, v, attr in self.G.edges(data=True):
            links.append({
                "source": u,
                "target": v,
                "value": attr.get('relation', ''),
                "label": {"show": True, "formatter": "{c}"}, # 显示关系名
                "lineStyle": {"curveness": 0.2, "color": "source"}
            })
            
        return {"nodes": nodes, "links": links, "categories": categories}

# ================= 配置加载 =================
def load_config():
    # 优先读取 config.json，不存在则读取 config.example.json，再没有则返回空
    if os.path.exists("config.json"):
        with open("config.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    elif os.path.exists("config.example.json"):
        with open("config.example.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

CFG = load_config()

# ================= 默认提示词配置 =================
DEFAULT_PROMPTS = {
    "writer_system": "你是一个顶级网文作家，擅长热血、快节奏、爽点密集的风格。写作要求：\n1. 【黄金法则】多用\"展示\"而非\"讲述\"（Show, don't tell）。\n2. 【对话驱动】通过对话推动剧情和塑造性格，拒绝大段枯燥的心理描写。\n3. 【感官描写】调动视觉、听觉、触觉，增加代入感。\n4. 【节奏把控】详略得当，战斗场面要干脆利落，日常互动要有趣味。\n5. 【字数要求】每章正文必须在 2000-4000 字之间，这是硬性要求，不可偷工减料。\n请根据提供的大纲、世界观和上下文，撰写引人入胜的正文。",
    "architect_system": "你是一个精通起承转合的剧情架构师。你的任务是基于前文和伏笔，规划后续章节。要求：\n1. 【逻辑严密】后续剧情必须符合人物性格逻辑，不能机械降神。\n2. 【冲突制造】每一章都必须有一个核心冲突或悬念钩子。\n3. 【伏笔回收】尝试利用历史记忆中的伏笔。\n请严格只返回一个标准的 JSON 列表，不要包含 Markdown 标记或其他废话。",
    "json_only_architect_system": "你是一个只输出JSON的架构师。",
    "knowledge_filter_system": "你是一个专业的资料整理助手。你的任务是从检索到的碎片信息中，剔除无关噪音，筛选出对当前章节写作真正有帮助的背景信息（如人物之前的恩怨、物品的特殊设定、地点的具体样貌）。如果片段与当前剧情无关，请忽略。",
    "reviewer_system": "你是一个以毒舌著称的严厉网文主编。请从以下维度审查正文：\n1. 【人设一致性】人物言行是否符合其性格和身份？\n2. 【剧情逻辑】是否有前后矛盾或不合理的转折？\n3. 【爽点节奏】是否过于拖沓？是否有期待感？\n请输出一份 Markdown 格式的报告，不仅要指出问题，还要给出具体的修改建议。",
    "timekeeper_system": "你是一个精确的时间记录员。你的任务是分析正文，推算时间流逝。输出必须是严格的 JSON 格式：{\"label\": \"当前时间点(如：修仙历10年春)\", \"duration\": \"本章经过的时间(如：3天)\", \"events\": [\"事件1\", \"事件2\"]}。请只输出 JSON。",
    "auditor_system": "你是一个世界观数据库管理员。你的任务是分析小说正文，提取状态变更。你需要敏锐地捕捉隐性信息（例如：'他断了一臂' -> 状态: 重伤/残疾）。\n\n请严格按以下 JSON 结构输出（不要使用 Markdown 代码块）：\n{\"char_updates\": [...], \"item_updates\": [...], \"new_chars\": [...], \"new_items\": [...], \"new_locs\": [...], \"relation_updates\": [...]}",
    "summary_chapter_system": "你是一个专业的网文编辑，擅长提炼剧情精华。请将给定的小说章节压缩成 150 字以内的摘要。要求：\n1. 保留核心冲突和结果。\n2. 记录关键道具或人物的获得/损失。\n3. 记录重要的伏笔。\n不要写流水账，要写干货。",
    "summary_book_system": "你是一个资深主编，拥有宏观的上帝视角。请根据各章节的摘要，梳理出整本书目前的剧情脉络（Story Arc）。要求：\n1. 串联主要故事线，忽略支线细枝末节。\n2. 明确主角目前的处境、目标和成长阶段。\n3. 篇幅控制在 500 字左右，适合快速回顾。",
    "inspiration_assistant_system": "你是一个网文灵感助手。请只返回请求的内容，不要废话。"
}

def get_prompt(key):
    """安全获取提示词，优先从配置读取，否则返回默认值"""
    return CFG.get('prompts', {}).get(key, DEFAULT_PROMPTS.get(key, ""))

def get_default_prompts():
    """返回默认提示词配置"""
    return DEFAULT_PROMPTS.copy()

# ================= 默认裂变策略配置 =================
DEFAULT_VOLUME_FISSION_STRATEGIES = {
    "time_based": {
        "name": "时间裂变",
        "description": "按时间顺序拆分为多个阶段",
        "detailed_prompt": """请严格按照故事时间线规划，每个分卷代表主角人生的一个明确阶段。
要求：
1. 标注每个阶段的起止时间点（如：少年期 1-15岁）
2. 每个阶段必须有明显的成长标志或关键事件
3. 确保时间流动合理，避免跳跃过快
4. 考虑主角实力与年龄的对应关系""",
        "is_default": True
    },
    "space_based": {
        "name": "空间裂变",
        "description": "按空间位置拆分为多个场景",
        "detailed_prompt": """请按空间/地域划分，每个分卷发生在不同的主要地点。
要求：
1. 明确每个地点的特色与危险等级
2. 每个地点要有独特的势力、资源或机缘
3. 地点转换要有合理的过渡（如传送、旅行）
4. 考虑地图结构与主角成长路径的匹配""",
        "is_default": True
    },
    "character_based": {
        "name": "人物裂变",
        "description": "从剧情中提取人物支线",
        "detailed_prompt": """请围绕不同的人物支线来规划分卷。
要求：
1. 每个分卷聚焦一个主要人物的成长弧光
2. 人物关系要有明确的变化节点
3. 配角要有独立的故事线，不能只是主角的附庸
4. 考虑多线叙事的交汇与分离""",
        "is_default": True
    },
    "conflict_based": {
        "name": "冲突裂变",
        "description": "将主要冲突拆分为多个回合",
        "detailed_prompt": """请将主要冲突拆分为多个回合/阶段。
要求：
1. 每个分卷围绕一个核心冲突
2. 冲突要有明确的起因、发展、高潮、结果
3. 每个冲突都要推动主角成长
4. 大冲突可以包含多个小冲突""",
        "is_default": True
    },
    "standard": {
        "name": "标准裂变",
        "description": "通用剧情拆分",
        "detailed_prompt": """请按照通用的故事结构进行拆分。
要求：
1. 每个分卷有明确的主题和目标
2. 确保剧情连贯性和逻辑性
3. 合理分配剧情密度和节奏""",
        "is_default": True
    }
}

DEFAULT_CHAPTER_FISSION_STRATEGIES = {
    "time_based": {
        "name": "时间裂变",
        "description": "按时间顺序规划章节",
        "detailed_prompt": """请严格按时间顺序规划章节，每章代表一个明确的时间点或时间段。
要求：
1. 标注每章的时间节点
2. 确保时间流动合理连贯
3. 关键时间点要有标志性的情节
4. 注意季节、日夜等时间细节""",
        "is_default": True
    },
    "space_based": {
        "name": "空间裂变",
        "description": "按空间场景规划章节",
        "detailed_prompt": """请按空间/场景划分章节，每章发生在不同的具体地点。
要求：
1. 每章有明确的主要场景
2. 场景转换要有合理的过渡
3. 利用场景特点设计剧情
4. 注意场景的氛围营造""",
        "is_default": True
    },
    "character_based": {
        "name": "人物裂变",
        "description": "围绕人物视角规划章节",
        "detailed_prompt": """请围绕不同的人物视角或人物成长阶段来规划章节。
要求：
1. 每章聚焦特定人物或关系
2. 展示人物的性格与成长
3. 人物视角切换要自然
4. 多视角叙事要有交汇点""",
        "is_default": True
    },
    "conflict_based": {
        "name": "冲突裂变",
        "description": "围绕冲突展开规划章节",
        "detailed_prompt": """请围绕冲突的展开来规划章节，每章代表冲突的一个回合或转折点。
要求：
1. 每章有明确的冲突或悬念
2. 冲突要有层次递进
3. 设置伏笔和转折
4. 章节结尾要有钩子""",
        "is_default": True
    },
    "standard": {
        "name": "标准裂变",
        "description": "自然剧情流规划章节",
        "detailed_prompt": """请根据剧情自然流动划分章节，确保每章有明确的冲突和解决。
要求：
1. 每章有完整的起承转合
2. 章节之间过渡自然
3. 节奏张弛有度
4. 控制章节长度均衡""",
        "is_default": True
    }
}

DEFAULT_SCENE_FISSION_STRATEGIES = {
    "dialogue_based": {
        "name": "对话驱动型",
        "description": "以对话为核心驱动剧情发展",
        "detailed_prompt": """每个场景围绕关键对话展开。
要求：
1. 场景开篇即进入对话或对话准备
2. 对话必须有明确目的（信息交换、冲突升级、关系变化）
3. 通过对话揭示人物性格和推动情节
4. 避免无效闲聊，每句台词都要有功能""",
        "is_default": True
    },
    "action_based": {
        "name": "动作驱动型",
        "description": "以动作为核心驱动剧情发展",
        "detailed_prompt": """每个场景包含明确的动作序列。
要求：
1. 动作场景要有清晰的节奏（铺垫、爆发、收尾）
2. 每个动作都要推动剧情或展示能力
3. 注意动作的视觉化和感官描写
4. 控制战斗时长，避免拖沓""",
        "is_default": True
    },
    "emotion_based": {
        "name": "情感驱动型",
        "description": "以情感变化为核心驱动剧情发展",
        "detailed_prompt": """每个场景聚焦情感转折。
要求：
1. 明确场景的情感起点和终点
2. 通过细节展现情感变化过程
3. 情感转折要有触发事件
4. 注意情感的层次感和真实性""",
        "is_default": True
    },
    "reveal_based": {
        "name": "揭示驱动型",
        "description": "以信息揭示为核心驱动剧情发展",
        "detailed_prompt": """每个场景包含关键信息揭露。
要求：
1. 信息揭示要有悬念和惊喜感
2. 控制信息量，避免一次性揭示过多
3. 揭示时机要与剧情节奏配合
4. 注意伏笔的铺垫与回收""",
        "is_default": True
    },
    "standard": {
        "name": "标准场景流",
        "description": "标准的场景划分，包含完整的起承转合",
        "detailed_prompt": """标准的场景划分，包含完整的起承转合。
要求：
1. 每个场景有明确的地点、人物、冲突
2. 场景之间要有自然的过渡
3. 控制单个场景的长度""",
        "is_default": True
    }
}

def get_fission_strategies(fission_type):
    """获取指定类型的所有策略（默认 + 自定义）"""
    defaults = {
        "volume": DEFAULT_VOLUME_FISSION_STRATEGIES,
        "chapter": DEFAULT_CHAPTER_FISSION_STRATEGIES,
        "scene": DEFAULT_SCENE_FISSION_STRATEGIES
    }
    result = defaults.get(fission_type, {}).copy()
    # 合并用户自定义策略
    custom = CFG.get('fission_strategies', {}).get(fission_type, {})
    result.update(custom)
    return result

def save_fission_strategy(fission_type, key, strategy):
    """保存自定义策略到 config.json"""
    if 'fission_strategies' not in CFG:
        CFG['fission_strategies'] = {}
    if fission_type not in CFG['fission_strategies']:
        CFG['fission_strategies'][fission_type] = {}
    CFG['fission_strategies'][fission_type][key] = strategy
    save_global_config(CFG)

def delete_fission_strategy(fission_type, key):
    """删除自定义策略（仅限非默认策略）"""
    strategies = CFG.get('fission_strategies', {}).get(fission_type, {})
    if key in strategies and not strategies[key].get('is_default', False):
        del strategies[key]
        save_global_config(CFG)
        return True
    return False

# ================= 默认模型配置 =================
DEFAULT_MODELS = {
    "writer": "deepseek-chat",
    "architect": "deepseek-reasoner",
    "editor": "deepseek-chat",
    "reviewer": "deepseek-chat",
    "timekeeper": "deepseek-chat",
    "auditor": "deepseek-reasoner",
    "summary": "deepseek-chat"
}

DEFAULT_TEMPERATURES = {
    "writer": 1.3,
    "architect": 1.0,
    "editor": 0.7,
    "reviewer": 0.5,
    "timekeeper": 0.1,
    "auditor": 0.6,
    "summary": 0.5
}

def get_model(task_type):
    """安全获取模型名称"""
    return CFG.get('models', {}).get(task_type, DEFAULT_MODELS.get(task_type, "deepseek-chat"))

def get_temperature(task_type):
    """安全获取温度参数"""
    return CFG.get('temperatures', {}).get(task_type, DEFAULT_TEMPERATURES.get(task_type, 0.7))

# 【修复】延迟初始化 OpenAI 客户端，避免启动时无 API key 崩溃
client = None

def get_client():
    """获取或创建 OpenAI 客户端（延迟初始化）"""
    global client
    if client is None:
        api_key = CFG.get('api_key')
        if not api_key:
            raise ValueError("未配置 API Key，请在系统配置中设置")
        client = OpenAI(api_key=api_key, base_url=CFG.get('base_url'))
    return client

# 【新增】保存配置并热重载
def save_global_config(new_config):
    global CFG, client
    try:
        # 1. 写入文件
        with open("config.json", 'w', encoding='utf-8') as f:
            json.dump(new_config, f, ensure_ascii=False, indent=4)

        # 2. 热更新内存中的配置
        CFG.update(new_config)

        # 3. 重置 OpenAI 客户端为 None，下次调用 get_client() 时会重新创建
        # 这样可以确保使用新的 API Key 和 base_url
        client = None

        return "✅ 配置已保存，系统已热重载"
    except Exception as e:
        return f"❌ 保存失败: {str(e)}"

# 1. 新增：书架管理器
class LibraryManager:
    def __init__(self):
        # 所有小说默认存放在 'projects' 文件夹下
        self.base_dir = CFG.get('project_base_dir', 'projects') # 建议读配置，无配置则默认为 'projects'
        if not os.path.exists(self.base_dir): os.makedirs(self.base_dir)

    def list_books(self):
        """列出所有项目"""
        books = []
        if not os.path.exists(self.base_dir): return []
        
        for name in os.listdir(self.base_dir):
            path = os.path.join(self.base_dir, name)
            if os.path.isdir(path):
                # 简单列出文件夹名作为书名
                books.append({"name": name})
        return books

    def create_book(self, book_name):
        """创建新书结构"""
        # 1. 净化文件名 (防止非法字符和路径遍历攻击)
        safe_name = "".join([c for c in book_name if c.isalnum() or c in (' ', '_', '-')]).strip()
        # 防止路径遍历
        safe_name = safe_name.replace("..", "").replace("/", "").replace("\\", "")
        if not safe_name: safe_name = f"Book_{datetime.now().strftime('%Y%m%d')}"

        path = os.path.join(self.base_dir, safe_name)

        # 2. 检查是否存在
        if os.path.exists(path): return False, "同名书籍已存在"

        try:
            # 3. 创建目录
            os.makedirs(path)

            # 4. 初始化该书的基础文件
            # 这里我们临时实例化一个 NovelManager 来帮我们生成文件结构
            # 注意：这里传入 project_root 让 Manager 知道去哪里初始化
            temp_mgr = NovelManager(project_root=path)

            return True, safe_name
        except Exception as e:
            return False, str(e)

    # --- 新增：重命名书籍 ---
    def rename_book(self, old_name, new_name):
        """重命名书籍文件夹"""
        # 1. 检查原书是否存在
        old_path = os.path.join(self.base_dir, old_name)
        if not os.path.exists(old_path):
            return False, "原书籍不存在"

        # 2. 净化新书名 (防止非法字符，但保留中文)
        # 允许：字母、数字、中文、空格、下划线、连字符
        safe_new_name = "".join([c for c in new_name if c.isalnum() or c in (' ', '_', '-') or '\u4e00' <= c <= '\u9fff']).strip()
        if not safe_new_name:
            return False, "新书名无效"
        
        new_path = os.path.join(self.base_dir, safe_new_name)

        # 3. 检查新名是否冲突
        if os.path.exists(new_path):
            return False, "该书名已存在"

        try:
            # 4. 执行重命名
            os.rename(old_path, new_path)
            
            # 【重要】如果这正是当前打开的书，也需要更新全局配置里的记录
            # 这部分逻辑通常在 UI 层处理状态，但在这里我们只负责文件系统
            
            return True, safe_new_name
        except Exception as e:
            return False, str(e)
    # --- 新增：删除书籍 ---
    def delete_book(self, book_name):
        print(f"[Backend] 正在尝试删除书籍: {book_name}") # <--- 调试日志
        
        # 1. 路径检查
        book_path = os.path.join(self.base_dir, book_name)
        if not os.path.exists(book_path):
            return False, "书籍目录不存在"

        try:
            # 2. 删除物理文件夹
            import shutil # 再次确保导入
            shutil.rmtree(book_path)
            
            # 3. 删除向量数据库
            try:
                import hashlib
                hash_object = hashlib.md5(book_name.encode('utf-8'))
                hex_dig = hash_object.hexdigest()
                collection_name = f"novel_{hex_dig}"
                
                db_path = "chroma_db_storage"
                if os.path.exists(db_path):
                    # 注意：这里需要新建一个 client 连接来执行删除
                    client = chromadb.PersistentClient(path=db_path)
                    client.delete_collection(collection_name)
                    print(f"[Backend] 向量库 {collection_name} 已删除")
            except Exception as e:
                print(f"[Backend] 向量库清理警告: {e}") # 也就是允许向量库删除失败，不影响主流程

            return True, f"《{book_name}》已永久删除"

        except Exception as e:
            import traceback
            traceback.print_exc() # 打印详细报错
            return False, f"删除失败: {str(e)}"
# ================= 小说管理器 (数据层) =================
class NovelManager:
    def __init__(self, project_root=None):
        # 如果传入了路径，就用传入的；否则读配置；最后回退到默认
        if project_root:
            self.root_dir = project_root
        else:
            self.root_dir = CFG.get('project_dir', 'projects/Default_Book')
            
        self.chapters_dir = os.path.join(self.root_dir, "chapters")
        self.setting_file = os.path.join(self.root_dir, "setting.json")
        self.char_file = os.path.join(self.root_dir, "characters.json")
        self.item_file = os.path.join(self.root_dir, "items.json")
        self.loc_file = os.path.join(self.root_dir, "locations.json")
        self.structure_file = os.path.join(self.root_dir, "structure.json")
        self.volume_file = os.path.join(self.root_dir, "volumes.json")
        self._init_fs()

    def _init_fs(self):
        if not os.path.exists(self.chapters_dir): os.makedirs(self.chapters_dir)
        
        if not os.path.exists(self.setting_file):
            with open(self.setting_file, 'w', encoding='utf-8') as f:
                json.dump({"world_view": "", "characters": "", "book_summary": ""}, f, ensure_ascii=False, indent=4)
        
        if not os.path.exists(self.char_file):
            default_chars = [{
                "name": "主角", "gender": "男", "role": "主角", 
                "status": "存活", "bio": "性格坚毅。", "relations": []
            }]
            with open(self.char_file, 'w', encoding='utf-8') as f:
                json.dump(default_chars, f, ensure_ascii=False, indent=4)

        if not os.path.exists(self.item_file):
            with open(self.item_file, 'w', encoding='utf-8') as f: json.dump([], f)
        
        if not os.path.exists(self.loc_file):
            with open(self.loc_file, 'w', encoding='utf-8') as f: json.dump([], f)

        if not os.path.exists(self.volume_file):
            default_vol = [{"id": "vol_default", "title": "正文卷", "order": 1}]
            with open(self.volume_file, 'w', encoding='utf-8') as f:
                json.dump(default_vol, f, ensure_ascii=False, indent=4)

        if not os.path.exists(self.structure_file):
            default_structure = [{
                "id": 1, 
                "title": "第一章", 
                "volume_id": "vol_default", 
                "outline": "开局。", 
                "summary": "", 
                "time_info": {"label": "故事开始", "duration": "0", "events": []}
            }]
            with open(self.structure_file, 'w', encoding='utf-8') as f:
                json.dump(default_structure, f, ensure_ascii=False, indent=4)

    # --- 基础读写 ---
    def load_settings(self):
        try:
            with open(self.setting_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            return {}

    def save_settings(self, data):
        with open(self.setting_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_characters(self):
        try:
            with open(self.char_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for char in data:
                    if 'relations' not in char: char['relations'] = []
                return data
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            return []

    def save_characters(self, data):
        with open(self.char_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_items(self):
        try:
            with open(self.item_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            return []

    def save_items(self, data):
        with open(self.item_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_locations(self):
        try:
            with open(self.loc_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            return []

    def save_locations(self, data):
        with open(self.loc_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_volumes(self):
        try:
            with open(self.volume_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            return []

    def save_volumes(self, data):
        with open(self.volume_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_structure(self):
        try:
            with open(self.structure_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for chap in data:
                    if 'time_info' not in chap:
                        chap['time_info'] = {"label": "未知时间", "duration": "-", "events": []}
                    if 'volume_id' not in chap:
                        chap['volume_id'] = "vol_default"
                return data
        except (FileNotFoundError, json.JSONDecodeError, PermissionError):
            return []

    def save_structure(self, data):
        # 清理不应保存到 structure.json 的字段
        cleaned_data = []
        for chap in data:
            # 创建副本，避免修改原数据
            chap_copy = chap.copy()
            # 移除不应该保存的字段
            chap_copy.pop('paragraphs', None)  # paragraphs 应保存在单独文件
            chap_copy.pop('content', None)  # content 应保存在单独文件
            cleaned_data.append(chap_copy)

        with open(self.structure_file, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, ensure_ascii=False, indent=4)
    
    def save_chapter_content(self, chapter_id, content):
        with open(os.path.join(self.chapters_dir, f"{chapter_id}.txt"), 'w', encoding='utf-8') as f:
            f.write(content)

    def load_chapter_content(self, chapter_id):
        path = os.path.join(self.chapters_dir, f"{chapter_id}.txt")
        if not os.path.exists(path):
            return ""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    # ================= 段落级别存储（新增） =================

    def text_to_paragraphs(self, text):
        """
        将纯文本转换为段落结构
        返回: [{"id": "p1", "text": "...", "word_count": 100}, ...]
        """
        if not text or not text.strip():
            return []

        paragraphs = []
        # 按换行符分割，保留非空段落
        lines = text.split('\n')
        para_id = 1
        current_para = []

        for line in lines:
            stripped = line.strip()
            if stripped:
                current_para.append(line)  # 保留原始缩进
            else:
                # 空行表示段落结束
                if current_para:
                    para_text = '\n'.join(current_para)
                    paragraphs.append({
                        "id": f"p{para_id}",
                        "text": para_text,
                        "word_count": count_words(para_text)['total_words']
                    })
                    para_id += 1
                    current_para = []

        # 处理最后一个段落
        if current_para:
            para_text = '\n'.join(current_para)
            paragraphs.append({
                "id": f"p{para_id}",
                "text": para_text,
                "word_count": count_words(para_text)['total_words']
            })

        return paragraphs

    def paragraphs_to_text(self, paragraphs):
        """将段落结构转换回纯文本"""
        if not paragraphs:
            return ""
        return '\n\n'.join(p['text'] for p in paragraphs)

    def save_chapter_paragraphs(self, chapter_id, paragraphs):
        """保存章节段落结构到JSON文件"""
        data = {
            "chapter_id": chapter_id,
            "paragraphs": paragraphs,
            "metadata": {
                "paragraph_count": len(paragraphs),
                "total_words": sum(p.get('word_count', 0) for p in paragraphs),
                "updated_at": datetime.now().isoformat()
            }
        }
        path = os.path.join(self.chapters_dir, f"{chapter_id}_paragraphs.json")
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 同时保存纯文本版本（兼容）
        text = self.paragraphs_to_text(paragraphs)
        self.save_chapter_content(chapter_id, text)

    def load_chapter_paragraphs(self, chapter_id):
        """
        加载章节段落结构
        如果JSON不存在，自动从txt转换（兼容旧数据）
        """
        json_path = os.path.join(self.chapters_dir, f"{chapter_id}_paragraphs.json")

        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get('paragraphs', [])
            except (json.JSONDecodeError, KeyError):
                pass  # 文件损坏，重新从txt转换

        # 从txt文件转换（兼容旧数据）
        text = self.load_chapter_content(chapter_id)
        if text:
            paragraphs = self.text_to_paragraphs(text)
            # 自动保存转换结果
            if paragraphs:
                self.save_chapter_paragraphs(chapter_id, paragraphs)
            return paragraphs

        return []

    def update_single_paragraph(self, chapter_id, paragraph_id, new_text):
        """
        更新单个段落内容
        返回更新后的段落列表
        """
        paragraphs = self.load_chapter_paragraphs(chapter_id)

        for i, p in enumerate(paragraphs):
            if p['id'] == paragraph_id:
                paragraphs[i]['text'] = new_text
                paragraphs[i]['word_count'] = count_words(new_text)['total_words']
                break

        self.save_chapter_paragraphs(chapter_id, paragraphs)
        return paragraphs

    def get_paragraph_by_id(self, chapter_id, paragraph_id):
        """根据ID获取单个段落"""
        paragraphs = self.load_chapter_paragraphs(chapter_id)
        for p in paragraphs:
            if p['id'] == paragraph_id:
                return p
        return None

    def add_paragraph(self, chapter_id, after_id, text):
        """在指定段落后插入新段落"""
        paragraphs = self.load_chapter_paragraphs(chapter_id)
        new_id = f"p{len(paragraphs) + 1}"
        new_para = {
            "id": new_id,
            "text": text,
            "word_count": count_words(text)['total_words']
        }

        # 找到插入位置
        insert_idx = len(paragraphs)
        for i, p in enumerate(paragraphs):
            if p['id'] == after_id:
                insert_idx = i + 1
                break

        paragraphs.insert(insert_idx, new_para)
        # 重新编号（可选，保持ID连续）
        for i, p in enumerate(paragraphs, 1):
            p['id'] = f"p{i}"

        self.save_chapter_paragraphs(chapter_id, paragraphs)
        return paragraphs

    def delete_paragraph(self, chapter_id, paragraph_id):
        """删除指定段落"""
        paragraphs = self.load_chapter_paragraphs(chapter_id)
        paragraphs = [p for p in paragraphs if p['id'] != paragraph_id]

        # 重新编号
        for i, p in enumerate(paragraphs, 1):
            p['id'] = f"p{i}"

        self.save_chapter_paragraphs(chapter_id, paragraphs)
        return paragraphs

    def split_paragraph(self, chapter_id, paragraph_id, split_position):
        """
        在指定位置分割段落
        split_position: 段落内的字符位置
        """
        paragraphs = self.load_chapter_paragraphs(chapter_id)

        for i, p in enumerate(paragraphs):
            if p['id'] == paragraph_id:
                text = p['text']
                if 0 < split_position < len(text):
                    # 分割
                    first_half = text[:split_position].strip()
                    second_half = text[split_position:].strip()

                    # 替换原段落
                    paragraphs[i]['text'] = first_half
                    paragraphs[i]['word_count'] = count_words(first_half)['total_words']

                    # 插入新段落
                    new_para = {
                        "id": f"p_temp",
                        "text": second_half,
                        "word_count": count_words(second_half)['total_words']
                    }
                    paragraphs.insert(i + 1, new_para)
                break

        # 重新编号
        for i, p in enumerate(paragraphs, 1):
            p['id'] = f"p{i}"

        self.save_chapter_paragraphs(chapter_id, paragraphs)
        return paragraphs

    def merge_paragraphs(self, chapter_id, paragraph_ids):
        """合并多个段落"""
        paragraphs = self.load_chapter_paragraphs(chapter_id)

        # 找到要合并的段落
        to_merge = []
        merge_indices = []
        for i, p in enumerate(paragraphs):
            if p['id'] in paragraph_ids:
                to_merge.append(p['text'])
                merge_indices.append(i)

        if len(to_merge) < 2:
            return paragraphs

        # 合并文本
        merged_text = '\n\n'.join(to_merge)
        merged_para = {
            "id": "p_temp",
            "text": merged_text,
            "word_count": count_words(merged_text)['total_words']
        }

        # 替换第一个段落，删除其余
        paragraphs[merge_indices[0]] = merged_para
        # 从后往前删除，避免索引变化
        for idx in sorted(merge_indices[1:], reverse=True):
            paragraphs.pop(idx)

        # 重新编号
        for i, p in enumerate(paragraphs, 1):
            p['id'] = f"p{i}"

        self.save_chapter_paragraphs(chapter_id, paragraphs)
        return paragraphs

    def get_total_word_count(self):
        """获取全书总字数（使用精确字数统计）"""
        structure = self.load_structure()
        total = 0
        for chap in structure:
            content = self.load_chapter_content(chap['id'])
            total += count_words(content)['total_words']
        return total

    def get_detailed_word_stats(self):
        """
        获取详细的字数统计信息
        返回: {
            'total_words': 全书总字数,
            'chinese': 全书中文字数,
            'english': 全书英文词数,
            'chapter_count': 章节数,
            'volume_count': 分卷数,
            'avg_words': 平均章节字数,
            'volumes': [分卷统计列表]
        }
        """
        structure = self.load_structure()
        volumes = self.load_volumes()

        total_stats = {'total_words': 0, 'chinese': 0, 'english': 0, 'numbers': 0, 'total_chars': 0}
        volume_stats = []

        # 建立分卷ID到章节列表的映射
        vol_chapters = {}
        for chap in structure:
            vol_id = chap.get('volume_id', 'vol_default')
            if vol_id not in vol_chapters:
                vol_chapters[vol_id] = []
            vol_chapters[vol_id].append(chap)

        # 统计每个分卷
        for vol in volumes:
            vol_id = vol['id']
            vol_title = vol.get('title', '未命名分卷')
            chapters = vol_chapters.get(vol_id, [])

            vol_total = 0
            vol_chinese = 0
            vol_english = 0
            chapter_details = []

            for chap in chapters:
                content = self.load_chapter_content(chap['id'])
                stats = count_words(content)
                vol_total += stats['total_words']
                vol_chinese += stats['chinese']
                vol_english += stats['english']
                chapter_details.append({
                    'id': chap['id'],
                    'title': chap.get('title', '未命名'),
                    'words': stats['total_words'],
                    'chinese': stats['chinese']
                })

            volume_stats.append({
                'id': vol_id,
                'title': vol_title,
                'words': vol_total,
                'chinese': vol_chinese,
                'english': vol_english,
                'chapter_count': len(chapters),
                'chapters': chapter_details
            })

            total_stats['total_words'] += vol_total
            total_stats['chinese'] += vol_chinese
            total_stats['english'] += vol_english

        chapter_count = len(structure)
        avg_words = total_stats['total_words'] // chapter_count if chapter_count > 0 else 0

        return {
            'total_words': total_stats['total_words'],
            'chinese': total_stats['chinese'],
            'english': total_stats['english'],
            'chapter_count': chapter_count,
            'volume_count': len(volumes),
            'avg_words': avg_words,
            'volumes': volume_stats
        }

    def get_relevant_context(self, text_context):
        chars = self.load_characters()
        items = self.load_items()
        locs = self.load_locations()
        
        active_info = []
        active_names = []

        found_chars = [c for c in chars if c['name'] in text_context]
        if not found_chars and chars: found_chars.append(chars[0])
        
        if found_chars:
            active_info.append("【相关人物】")
            for c in found_chars:
                rels = ", ".join([f"{r['type']}->{r['target']}" for r in c.get('relations', [])])
                rel_str = f" [关系: {rels}]" if rels else ""
                active_info.append(f"- {c['name']} ({c['gender']}/{c['role']}/{c['status']}){rel_str}: {c['bio']}")
                active_names.append(c['name'])

        found_items = [i for i in items if i['name'] in text_context]
        if found_items:
            active_info.append("【相关物品】")
            for i in found_items:
                active_info.append(f"- {i['name']} ({i['type']}/持有:{i['owner']}): {i['desc']}")
                active_names.append(i['name'])

        found_locs = [l for l in locs if l['name'] in text_context]
        if found_locs:
            active_info.append("【相关地点】")
            for l in found_locs:
                active_info.append(f"- {l['name']} ({l['faction']}): {l['desc']}")
                active_names.append(l['name'])

        return "\n".join(active_info), active_names

    def smart_rag_pipeline(self, query, current_chapter_id, memory_manager):
        print(f"\n[Smart RAG] 启动智能检索: {query[:20]}...")
        raw_docs, debug_info = memory_manager.query_related_memory(
            query, n_results=8, threshold=1.6, exclude_chapter_id=current_chapter_id
        )
        if not raw_docs: return "（无相关历史记忆）", []

        processed_snippets = []
        for item in debug_info:
            # 安全解析章节ID
            try:
                source_str = item['source'].replace("第", "").replace("章", "")
                source_id = int(source_str)
            except (ValueError, KeyError):
                source_id = 0
            distance = current_chapter_id - source_id
            prefix = "[REF]"
            if 1 <= distance <= 3: prefix = "[SKIP-RECENT]"
            snippet = f"{prefix} (第{source_id}章): {item['text']}"
            processed_snippets.append(snippet)
        
        context_block = "\n\n".join(processed_snippets)
        sys_prompt = get_prompt('knowledge_filter_system')
        filter_prompt = f"【本章大纲】{query}\n【检索片段】\n{context_block}\n【任务】筛选有用背景，忽略[SKIP-RECENT]，合并重复，输出简练背景。"
        print(f"\n[知识过滤] 检索片段数: {len(processed_snippets)} | 大纲长度: {len(query)}")
        filtered_context = sync_call_llm(filter_prompt, sys_prompt, task_type="editor")
        print(f"[知识过滤] 完成，过滤后长度: {len(filtered_context)}")
        return filtered_context, debug_info

    def update_chapter_summary(self, chapter_id, content):
        if len(content) < 100:
            print(f"[章节摘要] 第{chapter_id}章内容太短({len(content)}字)，跳过生成")
            return ""
        sys_prompt = get_prompt('summary_chapter_system')
        prompt = f"请阅读以下小说章节，用 150 字以内的篇幅，高度概括本章发生的**核心剧情**、**关键转折**和**重要伏笔**。\n\n【正文】\n{content[:4000]}"
        print(f"\n[章节摘要] 第{chapter_id}章 | 正文长度: {len(content)}")
        summary = sync_call_llm(prompt, sys_prompt, task_type="summary")
        if "Error" in summary:
            print(f"[章节摘要] 生成失败: {summary}")
            return summary
        structure = self.load_structure()
        for chap in structure:
            if chap['id'] == chapter_id:
                chap['summary'] = summary
                break
        self.save_structure(structure)
        print(f"[章节摘要] 完成，摘要长度: {len(summary)}")
        return summary

    def update_global_summary(self):
        structure = self.load_structure()
        all_summaries = []
        for chap in structure:
            if chap.get('summary'):
                all_summaries.append(f"第{chap['id']}章: {chap['summary']}")
        if not all_summaries:
            print("[全书总结] 暂无章节摘要，跳过生成")
            return "暂无剧情。"
        combined_text = "\n".join(all_summaries)
        sys_prompt = get_prompt('summary_book_system')
        prompt = f"以下是这就本小说目前的**分章剧情摘要**：\n{combined_text}\n【任务】请根据以上分章摘要，写一份**全书目前的剧情总纲**（500字左右）。"
        print(f"\n[全书总结] 汇总 {len(all_summaries)} 章摘要")
        global_summary = sync_call_llm(prompt, sys_prompt, task_type="summary")
        if "Error" in global_summary:
            print(f"[全书总结] 生成失败: {global_summary}")
            return global_summary
        settings = self.load_settings()
        settings['book_summary'] = global_summary
        self.save_settings(settings)
        print(f"[全书总结] 完成，总纲长度: {len(global_summary)}")
        return global_summary
    # 【新增】全局搜索
    def global_search(self, term):
        if not term: return []
        results = []
        
        # 1. 搜设定 (Settings)
        settings = self.load_settings()
        for k, v in settings.items():
            if isinstance(v, str) and term in v:
                results.append({"type": "setting", "key": k, "name": "系统设定", "preview": self._get_preview(v, term)})

        # 2. 搜章节列表 (Title/Outline)
        structure = self.load_structure()
        for chap in structure:
            if term in chap['title']:
                results.append({"type": "chap_meta", "id": chap['id'], "field": "title", "name": f"第{chap['id']}章标题", "preview": chap['title']})
            if term in chap['outline']:
                results.append({"type": "chap_meta", "id": chap['id'], "field": "outline", "name": f"第{chap['id']}章大纲", "preview": self._get_preview(chap['outline'], term)})
            
            # 3. 搜章节正文 (Content)
            content = self.load_chapter_content(chap['id'])
            if term in content:
                # 统计出现次数
                count = content.count(term)
                results.append({"type": "chap_content", "id": chap['id'], "name": f"第{chap['id']}章正文", "preview": self._get_preview(content, term), "count": count})

        # 4. 搜数据库 (Char/Item/Loc)
        chars = self.load_characters()
        for i, c in enumerate(chars):
            for k, v in c.items():
                if isinstance(v, str) and term in v:
                    results.append({"type": "char", "index": i, "field": k, "name": f"人物: {c['name']}", "preview": self._get_preview(v, term)})
        
        items = self.load_items()
        for i, it in enumerate(items):
            for k, v in it.items():
                if isinstance(v, str) and term in v:
                    results.append({"type": "item", "index": i, "field": k, "name": f"物品: {it['name']}", "preview": self._get_preview(v, term)})
                    
        locs = self.load_locations()
        for i, l in enumerate(locs):
            for k, v in l.items():
                if isinstance(v, str) and term in v:
                    results.append({"type": "loc", "index": i, "field": k, "name": f"地点: {l['name']}", "preview": self._get_preview(v, term)})

        return results

    # 辅助：获取带高亮的预览片段
    def _get_preview(self, text, term, window=20):
        idx = text.find(term)
        if idx == -1: return text[:50]
        start = max(0, idx - window)
        end = min(len(text), idx + len(term) + window)
        return f"...{text[start:end]}..."

    # 【新增】全局替换
    def global_replace(self, target_items, old_term, new_term):
        # 为了安全，重新加载所有数据
        settings = self.load_settings()
        structure = self.load_structure()
        chars = self.load_characters()
        items = self.load_items()
        locs = self.load_locations()
        
        updated_files = set() # 记录哪些文件被修改了
        
        for item in target_items:
            try:
                if item['type'] == 'setting':
                    settings[item['key']] = settings[item['key']].replace(old_term, new_term)
                    updated_files.add('settings')
                
                elif item['type'] == 'chap_meta':
                    for chap in structure:
                        if chap['id'] == item['id']:
                            chap[item['field']] = chap[item['field']].replace(old_term, new_term)
                            updated_files.add('structure')
                            break
                
                elif item['type'] == 'chap_content':
                    # 正文是单独的文件，直接读取-替换-保存
                    content = self.load_chapter_content(item['id'])
                    new_content = content.replace(old_term, new_term)
                    self.save_chapter_content(item['id'], new_content)
                    # 还需要更新向量库吗？理论上需要，但太慢了，建议用户手动触发或后台慢慢更。
                    # 这里为了速度暂不更新RAG，只更文件。
                
                elif item['type'] == 'char':
                    chars[item['index']][item['field']] = chars[item['index']][item['field']].replace(old_term, new_term)
                    updated_files.add('char')
                
                elif item['type'] == 'item':
                    items[item['index']][item['field']] = items[item['index']][item['field']].replace(old_term, new_term)
                    updated_files.add('item')
                
                elif item['type'] == 'loc':
                    locs[item['index']][item['field']] = locs[item['index']][item['field']].replace(old_term, new_term)
                    updated_files.add('loc')

            except Exception as e:
                print(f"Replace error at {item}: {e}")

        # 批量保存
        if 'settings' in updated_files: self.save_settings(settings)
        if 'structure' in updated_files: self.save_structure(structure)
        if 'char' in updated_files: self.save_characters(chars)
        if 'item' in updated_files: self.save_items(items)
        if 'loc' in updated_files: self.save_locations(locs)
        
        return f"已在 {len(target_items)} 处完成替换"
    
    # 1. 创建全项目备份 (ZIP)
    def create_project_backup(self, backup_dir="backups"):
        try:
            if not os.path.exists(backup_dir): os.makedirs(backup_dir)

            # 生成带时间戳的文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"novel_backup_{timestamp}"
            archive_path = os.path.join(backup_dir, filename)

            # 打包当前项目目录
            if os.path.exists(self.root_dir):
                shutil.make_archive(archive_path, 'zip', self.root_dir)

                # 清理旧备份 (只保留最近 20 个)
                backups = sorted(glob.glob(os.path.join(backup_dir, "*.zip")))
                if len(backups) > 20:
                    for b in backups[:-20]:
                        try: os.remove(b)
                        except OSError: pass
                return f"已备份: {filename}.zip"
            return "数据目录不存在，跳过备份"
        except Exception as e:
            return f"备份失败: {str(e)}"

    # 2. 创建章节快照 (History Snapshot)
    def create_chapter_snapshot(self, chapter_id, content):
        try:
            snapshot_dir = os.path.join(self.root_dir, "snapshots", str(chapter_id))
            if not os.path.exists(snapshot_dir): os.makedirs(snapshot_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(snapshot_dir, f"{timestamp}.txt")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 单章只保留最近 50 个快照，防止文件爆炸
            files = sorted(glob.glob(os.path.join(snapshot_dir, "*.txt")))
            if len(files) > 50:
                for f in files[:-50]:
                    try: os.remove(f)
                    except OSError: pass
        except Exception as e:
            print(f"Snapshot error: {e}")

    # 3. 获取章节快照列表
    def get_chapter_snapshots(self, chapter_id):
        snapshot_dir = os.path.join(self.root_dir, "snapshots", str(chapter_id))
        if not os.path.exists(snapshot_dir): return []

        snapshots = []
        files = sorted(glob.glob(os.path.join(snapshot_dir, "*.txt")), reverse=True)
        for f in files:
            ts_str = os.path.basename(f).replace(".txt", "")
            try:
                dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                display_time = ts_str

            try:
                with open(f, 'r', encoding='utf-8') as file:
                    preview = file.read(100).replace("\n", " ") + "..."
            except (FileNotFoundError, PermissionError, OSError):
                preview = "无法读取内容"
                
            snapshots.append({"filename": f, "time": display_time, "preview": preview, "raw_ts": ts_str})
        return snapshots
    # ================= 🎲 灵感生成 (新增) =================

    def generate_ideas(self, type_key, context=""):
        # 1. 定义提示词模板
        prompts = {
            "name_char_cn": "请生成 10 个好听的中文玄幻/古风人名，包含男女，格式如：叶凡、姬紫月。只返回名字，用逗号分隔。",
            "name_char_en": "请生成 10 个西幻风格的人名，格式如：亚瑟·潘德拉贡。只返回名字，用逗号分隔。",
            "name_org": "请生成 10 个霸气的宗派或组织名称，如：魂殿、炸天帮。只返回名字，用逗号分隔。",
            "name_skill": "请生成 10 个炫酷的功法或武技名称，如：佛怒火莲、大荒囚天指。只返回名字，用逗号分隔。",
            "name_item": "请生成 10 个传说级法宝或丹药名称，只返回名字，用逗号分隔。",
            "plot_twist": f"基于当前世界观：{context[:200]}...，请构思 3 个意想不到的剧情转折或突发事件，用于打破当前的平淡剧情。每个点子 50 字以内。",
            "gold_finger": "请脑洞大开，生成 5 个独特且爽点十足的网文「金手指」或「系统」设定。简短描述。"
        }
        
        prompt = prompts.get(type_key, "请随机生成一些灵感。")

        # 2. 调用 LLM (复用已有的 sync_call_llm，注意这里其实应该用异步，但为了代码简单复用 io_bound)
        # 这里我们临时构造一个 system prompt
        sys_prompt = get_prompt('inspiration_assistant_system')

        print(f"\n[灵感生成] 类型: {type_key}")
        try:
            # 使用 get_client() 获取客户端
            current_client = get_client()

            response = current_client.chat.completions.create(
                model=get_model('writer'), # 借用 writer 模型
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                temperature=0.9 # 灵感需要高创造性
            )
            result = response.choices[0].message.content
            print(f"[灵感生成] 完成，结果长度: {len(result)}")
            return result
        except ValueError as e:
            print(f"[灵感生成] ValueError: {str(e)}")
            return f"错误: {str(e)}"
        except Exception as e:
            print(f"[灵感生成] Exception: {str(e)}")
            return f"生成失败: {str(e)}"
    # --- 大纲树 (Blueprint) 管理 ---
    def load_outline_tree(self):
        path = os.path.join(self.root_dir, "outline_tree.json")
        if not os.path.exists(path):
            # 初始化根节点，读取现有的 book_summary
            settings = self.load_settings()
            root = {
                "id": "root", "type": "book", "label": "全书总纲", 
                "desc": settings.get('book_summary', '在此输入核心灵感...'), 
                "children": []
            }
            return [root]
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)

    def save_outline_tree(self, data):
        with open(os.path.join(self.root_dir, "outline_tree.json"), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    # --- 核心：AI 裂变推演 ---
    def ai_fractal_expand(self, node_data, context_summary):
        """
        分形裂变：
        - Book -> Volumes
        - Volume -> Chapters
        """
        node_type = node_data.get('type', 'book')
        current_desc = node_data.get('desc', '')
        
        # 1. 构造 Prompt
        if node_type == 'book':
            target_type = 'volume'
            prompt = f"【核心灵感】{current_desc}\n【任务】请将这本书拆分为 3-5 个分卷（Volume）。每卷要有明确的剧情阶段目标。"
        elif node_type == 'volume':
            target_type = 'chapter'
            prompt = f"【全书背景】{context_summary[:300]}...\n【当前分卷】{node_data['label']}\n【分卷剧情】{current_desc}\n【任务】请为该分卷规划 5-10 个具体章节（Chapter）。剧情要紧凑，要有起承转合。"
        else:
            return "错误：无法继续拆分章节"

        sys_prompt = get_prompt('architect_system')
        prompt += "\n【格式要求】严格返回JSON列表：[{'label': '标题', 'desc': '详细细纲'}, ...]"

        # 2. 调用 LLM (复用 sync_call_llm)
        res = sync_call_llm(prompt, sys_prompt, task_type="architect")
        
        # 3. 解析结果
        import uuid
        try:
            clean = res.replace("```json", "").replace("```", "").strip()
            items = json.loads(clean)
            new_nodes = []
            for item in items:
                new_nodes.append({
                    "id": str(uuid.uuid4())[:8],
                    "type": target_type,
                    "label": item['label'],
                    "desc": item['desc'],
                    "linked_id": None, # 初始未同步
                    "children": []
                })
            return new_nodes
        except Exception as e:
            return f"Error: {e} \nRaw: {res}"

    # --- 核心：同步到正式目录 (The Bridge) ---
    def sync_node_to_project(self, node):
        """将蓝图节点转换为正式的分卷或章节"""
        if node['linked_id']: return "已同步过，跳过创建"
        
        import uuid
        
        # 1. 同步分卷
        if node['type'] == 'volume':
            volumes = self.load_volumes()
            new_vol_id = f"vol_{str(uuid.uuid4())[:8]}"
            new_vol = {
                "id": new_vol_id, 
                "title": node['label'], 
                "order": len(volumes) + 1
            }
            volumes.append(new_vol)
            self.save_volumes(volumes)
            node['linked_id'] = new_vol_id
            return f"✅ 分卷 '{node['label']}' 已创建"

        # 2. 同步章节
        elif node['type'] == 'chapter':
            # 必须找到父级分卷 ID
            # 注意：这需要前端传参或者在树结构里向上查找，这里简化处理，假设前端传来 parent_vol_id
            # 实际实现建议在前端调用时，把父节点的 linked_id 传进来
            pass 
            # (具体实现在下面的 UI 部分完善)
    # --- 为 Architect UI 提供树状结构数据 ---
    def get_novel_tree(self, app_state):
        """
        将扁平的 volumes 和 structure 组装成 ui.tree 需要的嵌套格式
        """
        tree = []
        
        # 1. 根节点
        root_node = {
            'id': 'root',
            'label': '全书总纲 (Root)',
            'icon': 'menu_book',
            'children': []
        }
        
        # 2. 构建分卷
        # 假设 app_state.volumes 是列表 [{'id': 1, 'title': '...'}, ...]
        # 假设 app_state.structure 是列表 [{'id': 1, 'volume_id': 1, 'title': '...'}, ...]
        
        for vol in app_state.volumes:
            vol_node = {
                'id': f"vol_{vol['id']}", # 加上前缀防止ID冲突
                'label': vol['title'],
                'icon': 'inventory_2',
                'children': [],
                '_raw': vol # 暂存原始数据方便后续获取
            }
            
            # 3. 构建该卷下的章节
            vol_chapters = [c for c in app_state.structure if str(c.get('volume_id')) == str(vol['id'])]
            for chap in vol_chapters:
                chap_node = {
                    'id': f"chap_{chap['id']}",
                    'label': chap['title'],
                    'icon': 'article',
                    '_raw': chap
                }
                vol_node['children'].append(chap_node)
            
            root_node['children'].append(vol_node)
            
        tree.append(root_node)
        return tree

    # --- 获取节点上下文 (用于右侧面板渲染) ---
    def get_node_context(self, node_id, app_state):
        """
        返回: (node_type, context_dict, raw_data)
        """
        # 定义默认的安全返回 (兜底策略)
        safe_ctx = {
            'self_info': '暂无详细信息 (可能是未同步的节点或数据已变更)',
            'parent_info': None
        }
        
        try:
            settings = self.load_settings()
            
            # === Case 1: 根节点 ===
            if node_id == 'root':
                ctx = {
                    'self_info': settings.get('book_summary', '暂无全书简介'),
                    'parent_info': None
                }
                return 'root', ctx, {'title': '全书总纲'}
                
            # === Case 2: 分卷节点 ===
            if str(node_id).startswith('vol_'):
                # 【修复】只替换第一个 'vol_'，或者直接用切片
                # 错误写法: real_id = node_id.replace('vol_', '') 
                # 正确写法: 
                real_id = node_id.replace('vol_', '', 1) 
                
                # 或者更稳妥的切片写法 (因为前缀固定长度是4)
                # real_id = node_id[4:] 

                # 查找分卷数据
                vol_data = next((v for v in app_state.volumes if str(v['id']) == str(real_id)), None)
                
                if not vol_data: 
                    return 'unknown', safe_ctx, {}
                
                ctx = {
                    'self_info': vol_data.get('desc', '（该分卷暂无详细描述）'),
                    'parent_info': f"**全书目标**：\n{settings.get('book_summary', '')[:100]}..."
                }
                return 'volume', ctx, vol_data
                
            # === Case 3: 章节节点 ===
            if str(node_id).startswith('chap_'):
                # 【修复】同理，只替换第一个 'chap_'
                real_id = node_id.replace('chap_', '', 1)
                
                chap_data = next((c for c in app_state.structure if str(c['id']) == str(real_id)), None)
                
                if not chap_data: 
                    return 'unknown', safe_ctx, {} # <--- 修复点：返回 safe_ctx
                
                # 找父级分卷信息
                parent_vol = next((v for v in app_state.volumes if str(v['id']) == str(chap_data.get('volume_id'))), None)
                parent_title = parent_vol['title'] if parent_vol else "未知分卷"
                parent_desc = parent_vol.get('desc', parent_title) if parent_vol else ""
                
                ctx = {
                    'self_info': chap_data.get('outline', '暂无大纲'),
                    'parent_info': f"**所属分卷**：{parent_title}\n**分卷目标**：{parent_desc[:100]}..."
                }
                return 'chapter', ctx, chap_data
                
            # === Case 4: 未知/兜底 ===
            return 'unknown', safe_ctx, {}

        except Exception as e:
            print(f"Error in get_node_context: {e}")
            return 'error', safe_ctx, {}

# ================= 向量库管理器 (RAG) =================
class MemoryManager:
    def __init__(self, book_name="default"):
        self.root_dir = "chroma_db_storage" 
        if not os.path.exists(self.root_dir): os.makedirs(self.root_dir)
        
        self.client = chromadb.PersistentClient(path=self.root_dir)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        # 【修复核心】使用 MD5 哈希生成合法的 Collection 名称
        # 无论 book_name 是中文、英文还是特殊字符，hash 永远是合法的字母数字组合
        hash_object = hashlib.md5(book_name.encode('utf-8'))
        hex_dig = hash_object.hexdigest() # 生成类似 'e10adc3949ba59abbe56e057f20f883e'
        
        # 加上前缀，确保以字母开头 (ChromaDB 要求)
        safe_name = f"novel_{hex_dig}"
        
        # 打印一下，方便调试看到中文书名对应什么哈希
        print(f"[RAG] 书籍 '{book_name}' 对应向量库: {safe_name}")

        self.collection = self.client.get_or_create_collection(
            name=safe_name, 
            embedding_function=self.embedding_fn
        )

    def add_chapter_memory(self, chapter_id, content):
        self.delete_chapter_memory(chapter_id)
        chunk_size = CFG.get('chunk_size', 500)
        step = chunk_size - CFG.get('overlap', 100)
        chunks = [content[i:i+chunk_size] for i in range(0, len(content), step) if len(content[i:i+chunk_size]) > 50]
        if not chunks: return
        ids = [f"ch_{chapter_id}_{i}" for i in range(len(chunks))]
        metadatas = [{"chapter_id": chapter_id, "chunk_index": i} for i in range(len(chunks))]
        self.collection.upsert(documents=chunks, metadatas=metadatas, ids=ids)

    def delete_chapter_memory(self, chapter_id):
        try: self.collection.delete(where={"chapter_id": chapter_id})
        except Exception as e: print(f"[RAG Error] {e}")

    def query_related_memory(self, query_text, n_results=5, threshold=1.5, exclude_chapter_id=None):
        where_filter = None
        if exclude_chapter_id is not None:
            where_filter = {"chapter_id": {"$ne": exclude_chapter_id}}
        try:
            if self.collection.count() == 0: return [], []
            results = self.collection.query(query_texts=[query_text], n_results=n_results, include=['documents', 'distances', 'metadatas'], where=where_filter)
        except Exception as e: return [], []

        valid_docs = []
        debug_info = []
        if results['documents'] and results['documents'][0]:
            for doc, dist, meta in zip(results['documents'][0], results['distances'][0], results['metadatas'][0]):
                is_valid = dist < threshold
                debug_info.append({"text": doc, "distance": round(dist, 4), "source": f"第{meta['chapter_id']}章", "valid": is_valid})
                if is_valid: valid_docs.append(doc)
        return valid_docs, debug_info

# ================= LLM 调用接口 =================

def classify_error(error):
    """分类错误类型，返回 (错误类型, 是否可重试, 详细信息)"""
    error_str = str(error).lower()
    error_type = type(error).__name__

    # 连接错误 - 可重试
    if any(x in error_str for x in ['connection', 'connect', 'network', 'socket', 'timeout', 'timed out']):
        return ('CONNECTION_ERROR', True, f'网络连接问题: {error}')

    # API 错误 - 通常不可重试
    if 'api' in error_str or 'key' in error_str or 'auth' in error_str:
        if 'rate' in error_str or 'limit' in error_str:
            return ('RATE_LIMIT', True, f'API 限流: {error}')
        if 'invalid' in error_str or 'unauthorized' in error_str:
            return ('AUTH_ERROR', False, f'认证失败: {error}')
        return ('API_ERROR', False, f'API 错误: {error}')

    # 超时错误 - 可重试
    if 'timeout' in error_str:
        return ('TIMEOUT', True, f'请求超时: {error}')

    # JSON 解析错误 - 不可重试（需要重新生成或修复prompt）
    if 'json' in error_str or 'decode' in error_str or 'parse' in error_str:
        return ('PARSE_ERROR', False, f'解析失败: {error}')

    # 其他错误
    return ('UNKNOWN_ERROR', False, f'未知错误 ({error_type}): {error}')

def sync_call_llm(prompt, system_prompt, task_type="writer"):
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    print(f"\n[LLM Router] 任务: {task_type} | 模型: {model_name}")
    print(f"[LLM Router] Prompt 长度: {len(prompt)} | System 长度: {len(system_prompt)}")

    # 重试机制
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"[LLM Router] 第 {attempt + 1} 次重试...")
                time.sleep(retry_delay * attempt)  # 递增延迟

            current_client = get_client()
            response = current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                stream=False,
                temperature=temperature
            )

            # 检查响应有效性
            if not response.choices:
                return "Error: API 返回空响应"

            result = response.choices[0].message.content
            if not result:
                return "Error: API 返回空内容"

            print(f"[LLM Router] ✅ 成功，结果长度: {len(result)}")
            return result

        except ValueError as e:
            error_type, retryable, detail = classify_error(e)
            print(f"[LLM Router] ❌ {error_type}: {detail}")
            return f"Error [{error_type}]: {str(e)}"

        except Exception as e:
            error_type, retryable, detail = classify_error(e)
            print(f"[LLM Router] ❌ {error_type} (尝试 {attempt + 1}/{max_retries}): {detail}")

            # 如果不可重试，直接返回
            if not retryable:
                print(f"[LLM Router] 此类错误不可重试，直接返回")
                return f"Error [{error_type}]: {str(e)}"

            # 如果是最后一次重试，返回错误
            if attempt == max_retries - 1:
                print(f"[LLM Router] 已达最大重试次数")
                return f"Error [{error_type}]: {str(e)}"

    return "Error: 未知失败"

def stream_call_llm(prompt, system_prompt, task_type="writer"):
    """流式调用 LLM，返回生成器（同步生成器）"""
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    print(f"\n[LLM Router - Stream] 任务: {task_type} | 模型: {model_name}")
    try:
        current_client = get_client()
        stream = current_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            stream=True,
            temperature=temperature
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        print("[LLM Router - Stream] 完成")
    except ValueError as e:
        print(f"[LLM Router - Stream] ValueError: {str(e)}")
        yield f"Error: {str(e)}"
    except Exception as e:
        error_msg = str(e)
        print(f"[LLM Router - Stream] Exception: {error_msg}")
        yield f"Error: {error_msg}"

async def async_stream_call_llm(prompt, system_prompt, task_type="writer"):
    """异步流式调用 LLM，返回异步生成器（适用于 NiceGUI）"""
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    print(f"\n[LLM Router - Async Stream] 任务: {task_type} | 模型: {model_name}")
    try:
        current_client = get_client()
        stream = await asyncio.to_thread(
            lambda: current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                stream=True,
                temperature=temperature
            )
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            await asyncio.sleep(0)  # 让出控制权
    except ValueError as e:
        yield f"Error: {str(e)}"
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"LLM异步流式调用失败: {error_msg}")
        yield error_msg

def sync_rewrite_llm(selected_text, context_pre, context_post, instruction):
    task_type = "editor"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    prompt = f"【任务】重写文本。\n【上文】...{context_pre[-500:]}\n【待修改】{selected_text}\n【下文】{context_post[:500]}...\n【要求】{instruction}"
    try:
        current_client = get_client()
        response = current_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": "专业编辑"}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )
        return response.choices[0].message.content
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

def stream_rewrite_llm(selected_text, context_pre, context_post, instruction):
    """流式调用重写 LLM，返回生成器"""
    task_type = "editor"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    prompt = f"【任务】重写文本。\n【上文】...{context_pre[-500:]}\n【待修改】{selected_text}\n【下文】{context_post[:500]}...\n【要求】{instruction}"
    try:
        current_client = get_client()
        stream = current_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": "专业编辑"}, {"role": "user", "content": prompt}],
            stream=True,
            temperature=temperature
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except ValueError as e:
        yield f"Error: {str(e)}"
    except Exception as e:
        yield f"Error: {str(e)}"

def sync_review_chapter(content, context_str):
    task_type = "reviewer"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    sys_prompt = get_prompt('reviewer_system')
    prompt = f"【待审查正文】\n{content}\n【参考设定】\n{context_str}\n【任务】审查逻辑一致性、剧情节奏、文笔。输出Markdown报告。"
    print(f"\n[审稿] 模型: {model_name} | 温度: {temperature}")
    print(f"[审稿] 正文长度: {len(content)} | 设定长度: {len(context_str)}")

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"[审稿] 第 {attempt + 1} 次重试...")
                time.sleep(retry_delay * attempt)

            current_client = get_client()
            response = current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                stream=False,
                temperature=temperature
            )

            if not response.choices:
                return "Error [PARSE_ERROR]: API 返回空响应"
            result = response.choices[0].message.content
            if not result:
                return "Error [PARSE_ERROR]: API 返回空内容"

            print(f"[审稿] ✅ 成功，报告长度: {len(result)}")
            return result

        except ValueError as e:
            error_type, retryable, detail = classify_error(e)
            print(f"[审稿] ❌ {error_type}: {detail}")
            return f"Error [{error_type}]: {str(e)}"

        except Exception as e:
            error_type, retryable, detail = classify_error(e)
            print(f"[审稿] ❌ {error_type} (尝试 {attempt + 1}/{max_retries}): {detail}")

            if not retryable:
                print(f"[审稿] 此类错误不可重试")
                return f"Error [{error_type}]: {str(e)}"

            if attempt == max_retries - 1:
                return f"Error [{error_type}]: {str(e)}"

    return "Error: 未知失败"

def stream_review_chapter(content, context_str):
    """流式调用审稿 LLM，返回生成器"""
    task_type = "reviewer"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    sys_prompt = get_prompt('reviewer_system')
    prompt = f"【待审查正文】\n{content}\n【参考设定】\n{context_str}\n【任务】审查逻辑一致性、剧情节奏、文笔。输出Markdown报告。"
    print(f"\n[审稿-流式] 模型: {model_name} | 温度: {temperature}")
    print(f"[审稿-流式] 正文长度: {len(content)} | 设定长度: {len(context_str)}")
    try:
        current_client = get_client()
        stream = current_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
            stream=True,
            temperature=temperature
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        print("[审稿-流式] 完成")
    except ValueError as e:
        print(f"[审稿-流式] ValueError: {str(e)}")
        yield f"Error: {str(e)}"
    except Exception as e:
        print(f"[审稿-流式] Exception: {str(e)}")
        yield f"Error: {str(e)}"

def sync_analyze_time(content, prev_time_label):
    task_type = "timekeeper"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    sys_prompt = get_prompt('timekeeper_system')
    prompt = f"【上一章时间】{prev_time_label}\n【本章正文】{content[:3000]}...\n【任务】1.分析时间流逝 2.推算当前时间 3.提取事件\n【输出格式】严格JSON: {{\"label\": \"...\", \"duration\": \"...\", \"events\": [\"...\"]}}"
    print(f"\n[时间分析] 模型: {model_name} | 温度: {temperature}")
    print(f"[时间分析] 正文长度: {len(content)} | 上一章时间: {prev_time_label}")

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"[时间分析] 第 {attempt + 1} 次重试...")
                time.sleep(retry_delay * attempt)

            current_client = get_client()
            response = current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                stream=False,
                temperature=temperature
            )

            if not response.choices:
                return "Error [PARSE_ERROR]: API 返回空响应"
            result = response.choices[0].message.content
            if not result:
                return "Error [PARSE_ERROR]: API 返回空内容"

            print(f"[时间分析] ✅ 成功，结果长度: {len(result)}")
            return result

        except ValueError as e:
            error_type, retryable, detail = classify_error(e)
            print(f"[时间分析] ❌ {error_type}: {detail}")
            return f"Error [{error_type}]: {str(e)}"

        except Exception as e:
            error_type, retryable, detail = classify_error(e)
            print(f"[时间分析] ❌ {error_type} (尝试 {attempt + 1}/{max_retries}): {detail}")

            if not retryable:
                print(f"[时间分析] 此类错误不可重试")
                return f"Error [{error_type}]: {str(e)}"

            if attempt == max_retries - 1:
                return f"Error [{error_type}]: {str(e)}"

    return "Error: 未知失败"

# 【修改】状态分析接口：增加提取"地点连接"的指令
def sync_analyze_state(content, current_data_summary):
    task_type = "auditor"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    sys_prompt = get_prompt('auditor_system')

    prompt = f"""
    【当前正文】
    {content[:4000]}...

    【现有数据库摘要】
    {current_data_summary}

    【任务】
    请分析正文，检测以下变化（请严格区分"更新"和"新增"）：
    1. **人物状态变更**：已有的人物等级、状态(受伤/死亡)、所属势力发生变化。
    2. **物品变更**：已有的物品发生持有者转移、状态变化。
    3. **新实体提取**：正文中首次出现的**重要**新人物、新物品（如法宝、神兵、特殊道具）或新地点。必须放入对应的 new_ 数组中！
    4. **人际关系变更**：提取新关系（如拜师、结仇）或关系变化。
    5. **地点连接**：主角从一个地点移动到了另一个地点，提取这种拓扑关系。

    【输出格式】
    严格 JSON 格式，不要包含任何 Markdown 标记（如 ```json），字段如下：
    {{
        "char_updates": [{{"name": "...", "field": "...", "new_value": "...", "reason": "..."}}],
        "item_updates": [{{"name": "...", "field": "...", "new_value": "..."}}],
        "new_chars": [{{"name": "...", "gender": "...", "role": "...", "status": "...", "bio": "..."}}],
        "new_items": [{{"name": "...", "type": "...", "owner": "主角或其他人物", "desc": "物品的详细功能描述"}}],
        "new_locs": [{{"name": "...", "faction": "...", "desc": "..."}}],
        "relation_updates": [
            {{"source": "主动方", "target": "被动方", "type": "关系类型", "desc": "说明"}}
        ],
        "loc_connections": [
            {{"source": "地点A", "target": "地点B", "desc": "移动/连接说明"}}
        ]
    }}
    """
    print(f"\n[状态审计] 模型: {model_name} | 温度: {temperature}")
    print(f"[状态审计] 正文长度: {len(content)} | 数据库摘要长度: {len(current_data_summary)}")

    max_retries = 3
    retry_delay = 3  # reasoner 模型较慢，用更长延迟

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                print(f"[状态审计] 第 {attempt + 1} 次重试...")
                time.sleep(retry_delay * attempt)

            current_client = get_client()
            response = current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                stream=False,
                temperature=temperature
            )

            if not response.choices:
                print("[状态审计] ❌ API 返回空响应")
                return "Error [PARSE_ERROR]: API 返回空响应"
            result = response.choices[0].message.content
            if not result:
                print("[状态审计] ❌ API 返回空内容")
                return "Error [PARSE_ERROR]: API 返回空内容"

            print(f"[状态审计] ✅ 成功，结果长度: {len(result)}")
            return result

        except ValueError as e:
            error_type, retryable, detail = classify_error(e)
            print(f"[状态审计] ❌ {error_type}: {detail}")
            return f"Error [{error_type}]: {str(e)}"

        except Exception as e:
            error_type, retryable, detail = classify_error(e)
            print(f"[状态审计] ❌ {error_type} (尝试 {attempt + 1}/{max_retries}): {detail}")

            if not retryable:
                print(f"[状态审计] 此类错误不可重试")
                return f"Error [{error_type}]: {str(e)}"

            if attempt == max_retries - 1:
                return f"Error [{error_type}]: {str(e)}"

    return "Error: 未知失败"

# 【修改】应用变更：增加处理"地点连接"的逻辑
def apply_state_changes(novel_manager, changes):
    logs = []
    
    # 1. 更新人物 (保持不变)
    chars = novel_manager.load_characters()
    for update in changes.get('char_updates', []):
        for char in chars:
            if char['name'] == update['name']:
                char[update['field']] = update['new_value']
                logs.append(f"更新人物 [{char['name']}]: {update['field']} -> {update['new_value']}")
    
    for new_char in changes.get('new_chars', []):
        if not any(c['name'] == new_char['name'] for c in chars):
            if 'relations' not in new_char: new_char['relations'] = []
            chars.append(new_char)
            logs.append(f"新增人物: {new_char['name']}")
            
    for rel in changes.get('relation_updates', []):
        source_char = next((c for c in chars if c['name'] == rel['source']), None)
        if source_char:
            existing_rel = next((r for r in source_char['relations'] if r['target'] == rel['target']), None)
            if existing_rel:
                existing_rel['type'] = rel['type']
                logs.append(f"更新关系: {rel['source']} -> {rel['target']} ({rel['type']})")
            else:
                source_char['relations'].append({"target": rel['target'], "type": rel['type']})
                logs.append(f"新增关系: {rel['source']} -> {rel['target']} ({rel['type']})")
    
    novel_manager.save_characters(chars)

    # 2. 更新物品 (保持不变)
    items = novel_manager.load_items()
    for update in changes.get('item_updates', []):
        for item in items:
            if item['name'] == update['name']:
                item[update['field']] = update['new_value']
                logs.append(f"更新物品 [{item['name']}]: {update['field']} -> {update['new_value']}")
    for new_item in changes.get('new_items', []):
        if not any(i['name'] == new_item['name'] for i in items):
            # 【关键修复】补全默认字段，防止前端渲染时因缺少字段而报错！
            if 'owner' not in new_item: 
                new_item['owner'] = '未知'
            if 'desc' not in new_item: 
                new_item['desc'] = 'AI自动提取'
                
            items.append(new_item)
            logs.append(f"新增物品: {new_item['name']}")
    novel_manager.save_items(items)

    # 3. 更新地点 (增加连接处理逻辑)
    locs = novel_manager.load_locations()
    
    # A. 先处理新地点 (防止连接时找不到地点)
    for new_loc in changes.get('new_locs', []):
        if not any(l['name'] == new_loc['name'] for l in locs):
            if 'neighbors' not in new_loc: new_loc['neighbors'] = []
            locs.append(new_loc)
            logs.append(f"新增地点: {new_loc['name']}")
    
    # B. 处理连接关系
    for conn in changes.get('loc_connections', []):
        loc_a = next((l for l in locs if l['name'] == conn['source']), None)
        loc_b = next((l for l in locs if l['name'] == conn['target']), None)
        
        if loc_a and loc_b:
            # 确保有 neighbors 字段
            if 'neighbors' not in loc_a: loc_a['neighbors'] = []
            if 'neighbors' not in loc_b: loc_b['neighbors'] = []
            
            # 双向添加 (避免重复)
            added = False
            if conn['target'] not in loc_a['neighbors']:
                loc_a['neighbors'].append(conn['target'])
                added = True
            if conn['source'] not in loc_b['neighbors']:
                loc_b['neighbors'].append(conn['source'])
                added = True
            
            if added:
                logs.append(f"新增地图连接: {conn['source']} ↔️ {conn['target']}")

    novel_manager.save_locations(locs)

    return logs

def export_full_novel(novel_manager):
    structure = novel_manager.load_structure()
    full_text = [f"《AI 生成长篇小说》\n总字数：{novel_manager.get_total_word_count()}\n{'='*30}\n\n"]
    for chap in structure:
        title = f"第{chap['id']}章 {chap['title']}"
        content = novel_manager.load_chapter_content(chap['id'])
        full_text.extend([title, "-" * 20, content, "\n\n"])
    return "\n".join(full_text)


# ================= 分段审稿与重绘功能 =================

def split_content_into_sections(content, min_section_length=500):
    """
    将正文按段落分割成多个部分，用于分段审稿
    返回: [(section_id, section_text, start_pos, end_pos), ...]
    """
    if not content:
        return []

    # 按换行符分割段落
    paragraphs = content.split('\n')
    sections = []
    current_section = []
    current_start = 0
    section_id = 1
    char_pos = 0

    for para in paragraphs:
        para_len = len(para) + 1  # +1 for newline
        current_section.append(para)

        # 当累积够一定长度，或者段落明显是一个场景结束
        joined = '\n'.join(current_section)
        if len(joined) >= min_section_length or (para.strip() and para.strip()[-1] in '。！？"」』）'):
            if len(joined) >= 200:  # 至少 200 字才算一个 section
                sections.append({
                    'id': section_id,
                    'text': joined,
                    'start': current_start,
                    'end': char_pos + para_len - 1,
                    'word_count': count_words(joined)['total_words']
                })
                section_id += 1
                current_section = []
                current_start = char_pos + para_len

        char_pos += para_len

    # 处理剩余内容
    if current_section:
        joined = '\n'.join(current_section)
        sections.append({
            'id': section_id,
            'text': joined,
            'start': current_start,
            'end': len(content),
            'word_count': count_words(joined)['total_words']
        })

    return sections


def sync_review_section(section_text, section_id, context_str):
    """
    审稿单个段落/部分
    返回该部分的审稿意见（JSON格式）
    """
    task_type = "reviewer"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    sys_prompt = get_prompt('reviewer_system')

    prompt = f"""【任务】审查以下段落（第{section_id}部分），输出JSON格式的审稿意见。

【待审查段落】
{section_text}

【参考设定】
{context_str}

【输出要求】
请严格按以下JSON格式输出（不要使用Markdown代码块）：
{{
    "overall_score": 1-10分,
    "issues": [
        {{
            "type": "人设/逻辑/节奏/文笔/其他",
            "severity": "严重/中等/轻微",
            "location": "问题描述位置（引用原文）",
            "description": "具体问题描述",
            "suggestion": "修改建议"
        }}
    ],
    "highlights": ["亮点1", "亮点2"],
    "summary": "一句话总结这段的问题"
}}
"""

    print(f"[分段审稿] 第{section_id}部分 | 长度: {len(section_text)}")

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(retry_delay * attempt)

            current_client = get_client()
            response = current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                stream=False,
                temperature=temperature
            )

            if not response.choices:
                return {"error": "API返回空响应"}

            result = response.choices[0].message.content
            if not result:
                return {"error": "API返回空内容"}

            # 解析 JSON
            import re
            clean = result.replace("```json", "").replace("```", "").strip()
            start, end = clean.find('{'), clean.rfind('}')
            if start >= 0 and end > start:
                return json.loads(clean[start:end+1])
            return {"error": "无法解析JSON", "raw": result}

        except json.JSONDecodeError as e:
            print(f"[分段审稿] JSON解析失败: {e}")
            return {"error": f"JSON解析失败: {e}", "raw": result}
        except Exception as e:
            print(f"[分段审稿] 异常 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return {"error": str(e)}

    return {"error": "未知失败"}


def sync_review_full_chapter_with_sections(content, context_str):
    """
    分段审稿整章，返回完整的审稿报告
    包含：整体评价 + 各部分详细意见
    """
    print(f"\n[分段审稿] 开始 | 正文长度: {len(content)}")

    # 1. 分割内容
    sections = split_content_into_sections(content)
    print(f"[分段审稿] 共分割为 {len(sections)} 个部分")

    if not sections:
        return {"error": "内容太短，无法分段审稿"}

    # 2. 审稿每个部分
    section_reviews = []
    total_score = 0
    all_issues = []

    for sec in sections:
        review = sync_review_section(sec['text'], sec['id'], context_str)
        section_reviews.append({
            'id': sec['id'],
            'text_preview': sec['text'][:100] + '...' if len(sec['text']) > 100 else sec['text'],
            'word_count': sec['word_count'],
            'start': sec['start'],
            'end': sec['end'],
            'review': review
        })

        if 'overall_score' in review:
            total_score += review['overall_score']
        if 'issues' in review:
            for issue in review['issues']:
                issue['section_id'] = sec['id']
                all_issues.append(issue)

    # 3. 生成整体评价
    avg_score = total_score / len(sections) if sections else 0

    # 按严重程度分类问题
    severe_issues = [i for i in all_issues if i.get('severity') == '严重']
    medium_issues = [i for i in all_issues if i.get('severity') == '中等']
    minor_issues = [i for i in all_issues if i.get('severity') == '轻微']

    # 生成 Markdown 报告
    report = f"""# 📋 章节审稿报告

## 📊 整体评价

| 指标 | 数值 |
|------|------|
| 综合评分 | {avg_score:.1f}/10 |
| 段落数 | {len(sections)} |
| 严重问题 | {len(severe_issues)} 个 |
| 中等问题 | {len(medium_issues)} 个 |
| 轻微问题 | {len(minor_issues)} 个 |

---

## 📝 分段详细意见

"""
    for sr in section_reviews:
        review = sr['review']
        score = review.get('overall_score', '?')
        summary = review.get('summary', '无总结')
        issues_count = len(review.get('issues', []))

        report += f"""### 第 {sr['id']} 部分 ({sr['word_count']}字)

**评分**: {score}/10 | **问题数**: {issues_count}

> 预览：{sr['text_preview']}

**总结**: {summary}

"""
        if review.get('issues'):
            report += "**问题列表**:\n"
            for idx, issue in enumerate(review['issues'], 1):
                report += f"{idx}. [{issue.get('type', '未知')}] {issue.get('description', '')}\n"
                report += f"   - 位置: _{issue.get('location', '未指定')}_\n"
                report += f"   - 建议: {issue.get('suggestion', '无')}\n"
            report += "\n"

        if review.get('highlights'):
            report += f"**亮点**: {', '.join(review['highlights'])}\n\n"

        report += "---\n\n"

    # 汇总严重问题
    if severe_issues:
        report += "## ⚠️ 严重问题汇总\n\n"
        for i, issue in enumerate(severe_issues, 1):
            report += f"{i}. **第{issue.get('section_id', '?')}部分**: {issue.get('description', '')}\n"
            report += f"   - 建议: {issue.get('suggestion', '无')}\n\n"

    print(f"[分段审稿] 完成 | 平均分: {avg_score:.1f} | 问题数: {len(all_issues)}")

    return {
        'avg_score': avg_score,
        'section_count': len(sections),
        'total_issues': len(all_issues),
        'severe_issues': len(severe_issues),
        'section_reviews': section_reviews,
        'markdown_report': report
    }


def sync_rewrite_section(section_text, instruction, context_str):
    """
    重写单个段落
    返回重写后的文本
    """
    task_type = "writer"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)

    sys_prompt = get_prompt('writer_system')

    prompt = f"""【任务】根据修改要求重写以下段落。

【原段落】
{section_text}

【修改要求】
{instruction}

【参考设定】
{context_str}

【输出要求】
1. 只输出重写后的段落内容，不要包含任何解释或说明
2. 保持字数相近，除非修改要求明确要求扩展或缩减
3. 保持文风一致
4. 确保重写后的内容与修改要求高度相关
"""

    print(f"[段落重绘] 长度: {len(section_text)} | 要求: {instruction[:50]}...")

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(retry_delay * attempt)

            current_client = get_client()
            response = current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                stream=False,
                temperature=temperature
            )

            if not response.choices:
                return None, "API返回空响应"

            result = response.choices[0].message.content
            if not result:
                return None, "API返回空内容"

            print(f"[段落重绘] 完成 | 结果长度: {len(result)}")
            return result.strip(), None

        except Exception as e:
            print(f"[段落重绘] 异常 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return None, str(e)

    return None, "未知失败"


# ================= 基于段落结构的审稿与重绘 =================

def _clean_control_chars_in_json(json_str):
    """
    清理JSON字符串中的无效控制字符
    这些字符可能是AI在生成时意外引入的（如字符串内部的换行符）
    """
    import re
    # 在JSON字符串值内部，将未转义的控制字符转义
    # 这是一个简化处理：替换所有未转义的控制字符
    result = []
    in_string = False
    escape_next = False

    for char in json_str:
        if escape_next:
            result.append(char)
            escape_next = False
            continue

        if char == '\\' and in_string:
            result.append(char)
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
            continue

        if in_string:
            # 在字符串内部，控制字符需要转义
            if ord(char) < 32:
                if char == '\n':
                    result.append('\\n')
                elif char == '\r':
                    result.append('\\r')
                elif char == '\t':
                    result.append('\\t')
                else:
                    result.append(f'\\u{ord(char):04x}')
            else:
                result.append(char)
        else:
            result.append(char)

    return ''.join(result)


def _parse_json_aggressive(json_str):
    """
    激进的JSON解析，用于处理AI返回的不规范JSON
    """
    import re

    # 尝试提取关键字段
    result = {
        "overall_score": 5,
        "overall_comment": "",
        "issues": []
    }

    try:
        # 尝试提取评分
        score_match = re.search(r'"overall_score"\s*:\s*(\d+)', json_str)
        if score_match:
            result["overall_score"] = int(score_match.group(1))

        # 尝试提取总体评价
        comment_match = re.search(r'"overall_comment"\s*:\s*"([^"]*)"', json_str)
        if comment_match:
            result["overall_comment"] = comment_match.group(1)

        # 尝试提取问题列表（简化处理）
        issues_pattern = r'"issues"\s*:\s*\[(.*?)\](?=\s*\})'
        issues_match = re.search(issues_pattern, json_str, re.DOTALL)
        if issues_match:
            issues_text = issues_match.group(1)
            # 简化：提取每个问题对象
            issue_objects = re.findall(r'\{[^{}]*\}', issues_text)
            for i, obj in enumerate(issue_objects):
                issue = {
                    "id": f"issue_{i+1}",
                    "paragraph_id": "p1",
                    "quote": "",
                    "type": "其他",
                    "severity": "轻微",
                    "description": "",
                    "suggestion": ""
                }

                # 提取各个字段
                for field in ['paragraph_id', 'quote', 'type', 'severity', 'description', 'suggestion']:
                    match = re.search(f'"{field}"\\s*:\\s*"([^"]*)"', obj)
                    if match:
                        issue[field] = match.group(1)

                if issue.get('description'):
                    result['issues'].append(issue)

    except Exception as e:
        print(f"[激进JSON解析] 失败: {e}")

    return result

def sync_review_chapter_by_paragraphs(paragraphs, context_str):
    """
    基于段落结构的章节审稿
    整体审稿，问题关联到段落ID

    Args:
        paragraphs: [{"id": "p1", "text": "...", "word_count": 100}, ...]
        context_str: 世界观、人物等背景信息

    Returns:
        {
            "overall_score": 7,
            "overall_comment": "整体评价...",
            "issues": [
                {
                    "id": "issue_1",
                    "paragraph_id": "p3",
                    "quote": "原文引用...",
                    "type": "人设",
                    "severity": "严重",
                    "description": "问题描述",
                    "suggestion": "修改建议"
                },
                ...
            ]
        }
    """
    task_type = "reviewer"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)
    sys_prompt = get_prompt('reviewer_system')

    # 构建带段落标记的正文
    numbered_content = ""
    for p in paragraphs:
        numbered_content += f"【段落{p['id']}】({p['word_count']}字)\n{p['text']}\n\n"

    prompt = f"""【任务】审查以下章节，输出JSON格式的审稿意见。问题必须关联到具体段落ID。

【待审章节】
{numbered_content}

【参考设定】
{context_str}

【输出要求】
请严格按以下JSON格式输出（不要使用Markdown代码块）：
{{
    "overall_score": 1-10分,
    "overall_comment": "对整章的总体评价",
    "issues": [
        {{
            "id": "issue_1",
            "paragraph_id": "段落ID（如p1, p2等）",
            "quote": "问题所在位置的原文引用（用于定位）",
            "type": "人设/逻辑/节奏/文笔/其他",
            "severity": "严重/中等/轻微",
            "description": "具体问题描述",
            "suggestion": "修改建议"
        }}
    ]
}}

注意：
1. 每个问题必须准确标注段落ID（p1, p2, p3...）
2. quote字段必须是从原文中精确引用的短语或句子
3. 只报告真正需要修改的问题，不要吹毛求疵
"""

    print(f"\n[段落审稿] 段落数: {len(paragraphs)} | 总字数: {sum(p['word_count'] for p in paragraphs)}")

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(retry_delay * attempt)

            current_client = get_client()
            response = current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                stream=False,
                temperature=temperature
            )

            if not response.choices:
                return {"error": "API返回空响应"}

            result = response.choices[0].message.content
            if not result:
                return {"error": "API返回空内容"}

            # 解析 JSON
            clean = result.replace("```json", "").replace("```", "").strip()
            start, end = clean.find('{'), clean.rfind('}')
            if start >= 0 and end > start:
                json_str = clean[start:end+1]

                # 清理无效控制字符
                json_str = _clean_control_chars_in_json(json_str)

                try:
                    parsed = json.loads(json_str)
                except json.JSONDecodeError as parse_err:
                    print(f"[段落审稿] 标准解析失败: {parse_err}，尝试激进解析")
                    parsed = _parse_json_aggressive(json_str)

                # 验证并修正段落ID
                valid_ids = {p['id'] for p in paragraphs}
                if 'issues' in parsed:
                    for issue in parsed['issues']:
                        pid = issue.get('paragraph_id', '')
                        # 如果段落ID无效，尝试通过quote匹配
                        if pid not in valid_ids:
                            matched_id = find_paragraph_by_quote(paragraphs, issue.get('quote', ''))
                            if matched_id:
                                issue['paragraph_id'] = matched_id
                            else:
                                issue['paragraph_id'] = paragraphs[0]['id'] if paragraphs else 'p1'

                print(f"[段落审稿] 完成 | 评分: {parsed.get('overall_score', '?')} | 问题数: {len(parsed.get('issues', []))}")
                return parsed

            return {"error": "无法解析JSON", "raw": result}

        except json.JSONDecodeError as e:
            print(f"[段落审稿] JSON解析失败: {e}")
            return {"error": f"JSON解析失败: {e}", "raw": result}
        except Exception as e:
            print(f"[段落审稿] 异常 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return {"error": str(e)}

    return {"error": "未知失败"}


def find_paragraph_by_quote(paragraphs, quote):
    """
    通过原文引用找到对应的段落ID
    """
    if not quote:
        return None

    quote = quote.strip()
    if len(quote) < 5:  # 太短不可靠
        return None

    for p in paragraphs:
        if quote in p['text']:
            return p['id']

    return None


def sync_rewrite_paragraph(paragraph_text, issues, context_str):
    """
    根据审稿问题重写单个段落

    Args:
        paragraph_text: 原段落文本
        issues: 该段落的问题列表
        context_str: 背景信息

    Returns:
        (new_text, error) 元组
    """
    task_type = "writer"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)

    # 计算字数
    original_word_count = count_words(paragraph_text)['total_words']
    original_char_count = len(paragraph_text)

    # 字数限制：最多3倍，但不超过800字
    max_chars = min(original_char_count * 3, 800)
    # 计算合理的目标字数范围
    target_min = original_char_count
    target_max = max_chars

    # 整理问题（包含更完整的信息）
    issues_text = ""
    for i, issue in enumerate(issues, 1):
        issues_text += f"{i}. [{issue.get('severity', '未知')}] {issue.get('description', '')}\n"
        quote = issue.get('quote', '')
        if quote:
            issues_text += f"   原文片段: \"{quote[:50]}...\"\n"
        suggestion = issue.get('suggestion', '')
        if suggestion:
            issues_text += f"   修改建议: {suggestion[:100]}\n"

    prompt = f"""【任务】根据审稿意见修改以下段落。

【原段落】（{original_char_count}字）
{paragraph_text}

【背景信息】
{context_str[:500] if context_str else '无'}

【需要修复的问题】
{issues_text}

【严格要求】
1. 只输出修改后的段落正文，不要有任何解释或开头结尾
2. 针对上述问题进行修改，可适当增删内容
3. 【字数硬限制】输出长度必须在{target_min}-{target_max}字之间，不得超过{max_chars}字
4. 保持原有文风和叙事风格
"""

    print(f"[段落重写] 原长度: {original_char_count}字 | 上限: {max_chars}字")

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(retry_delay * attempt)

            current_client = get_client()
            response = current_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=temperature,
                max_tokens=max_chars * 2  # 硬性限制输出token数（中文约1.5-2 token/字）
            )

            if not response.choices:
                return None, "API返回空响应"

            result = response.choices[0].message.content
            if not result:
                return None, "API返回空内容"

            result = result.strip()

            # 检查字数是否严重超标（超过800字的1.5倍才截断）
            if len(result) > 1200:
                print(f"[段落重写] ⚠️ 结果过长 ({len(result)}字)，截取前{max_chars}字")
                # 按段落分割
                paragraphs = result.split('\n\n')
                if len(paragraphs[0]) <= max_chars:
                    result = paragraphs[0].strip()
                else:
                    # 在句号处截断
                    result = result[:max_chars]
                    last_period = result.rfind('。')
                    if last_period > max_chars // 2:
                        result = result[:last_period + 1]

            print(f"[段落重写] 完成 | 新长度: {len(result)}字")
            return result, None

        except Exception as e:
            print(f"[段落重写] 异常 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                return None, str(e)

    return None, "未知失败"


def apply_paragraph_rewrite(novel_manager, chapter_id, paragraph_id, new_text):
    """
    应用段落重写结果（安全更新单个段落）

    Returns:
        更新后的段落列表
    """
    return novel_manager.update_single_paragraph(chapter_id, paragraph_id, new_text)


# ================= 分维度审稿功能 =================

def sync_review_character_consistency(paragraphs, characters_info):
    """
    人设一致性检查维度
    检查人物行为、语言、性格是否符合设定

    Args:
        paragraphs: 段落列表
        characters_info: 人物设定信息字符串

    Returns:
        {"score": 8, "issues": [...]}
    """
    task_type = "reviewer"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)  # 更低温度，更严格

    # 构建带段落标记的正文
    numbered_content = ""
    for p in paragraphs:
        numbered_content += f"【段落{p['id']}】\n{p['text']}\n\n"

    prompt = f"""【任务】作为人设审核专家，检查以下章节中人物行为是否符合其性格设定。

【人物设定】
{characters_info}

【待审章节】
{numbered_content}

【检查要点】
1. 人物言行是否符合其性格特点？
2. 人物能力表现是否合理（不要超出或低于其能力范围）？
3. 人物之间的关系互动是否符合设定？
4. 是否有OOC（Out of Character）行为？

【输出要求】
严格按JSON格式输出（不要用Markdown代码块）：
{{
    "score": 1-10分,
    "issues": [
        {{
            "paragraph_id": "段落ID",
            "character": "人物名",
            "quote": "问题原文引用",
            "problem": "违反了什么设定",
            "severity": "严重/中等/轻微",
            "suggestion": "修改建议"
        }}
    ]
}}

注意：只报告真正的人设问题，不要过度解读。如果没有问题，issues可以为空数组。
"""

    print(f"\n[人设检查] 开始检查...")

    try:
        current_client = get_client()
        response = current_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )

        result = response.choices[0].message.content if response.choices else ""

        # 解析JSON
        clean = result.replace("```json", "").replace("```", "").strip()
        start, end = clean.find('{'), clean.rfind('}')
        if start >= 0 and end > start:
            json_str = _clean_control_chars_in_json(clean[start:end+1])
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                parsed = _parse_json_aggressive(json_str)

            # 标准化issue格式
            issues = []
            for i, issue in enumerate(parsed.get('issues', [])):
                issues.append({
                    "id": f"char_{i+1}",
                    "paragraph_id": issue.get('paragraph_id', 'p1'),
                    "dimension": "人设",
                    "type": "人设不一致",
                    "severity": issue.get('severity', '轻微'),
                    "quote": issue.get('quote', ''),
                    "description": f"[{issue.get('character', '人物')}] {issue.get('problem', '')}",
                    "suggestion": issue.get('suggestion', '')
                })

            print(f"[人设检查] 完成 | 评分: {parsed.get('score', '?')} | 问题数: {len(issues)}")
            return {"score": parsed.get('score', 5), "issues": issues}

    except Exception as e:
        print(f"[人设检查] 异常: {e}")

    return {"score": 5, "issues": []}


def sync_review_plot_logic(paragraphs, world_setting, chapter_outline):
    """
    剧情逻辑检查维度
    检查情节发展是否合理、有无逻辑漏洞

    Args:
        paragraphs: 段落列表
        world_setting: 世界观设定
        chapter_outline: 本章大纲

    Returns:
        {"score": 8, "issues": [...]}
    """
    task_type = "reviewer"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)

    numbered_content = ""
    for p in paragraphs:
        numbered_content += f"【段落{p['id']}】\n{p['text']}\n\n"

    prompt = f"""【任务】作为剧情逻辑审核专家，检查以下章节是否存在逻辑漏洞。

【世界观设定】
{world_setting}

【本章大纲】
{chapter_outline}

【待审章节】
{numbered_content}

【检查要点】
1. 事件因果关系是否合理？
2. 时间线是否清晰、有无矛盾？
3. 人物行为动机是否充分？
4. 是否有"机械降神"或不合理的巧合？
5. 伏笔埋设是否自然？
6. 冲突解决是否合理？

【输出要求】
严格按JSON格式输出（不要用Markdown代码块）：
{{
    "score": 1-10分,
    "issues": [
        {{
            "paragraph_id": "段落ID",
            "quote": "问题原文引用",
            "problem": "逻辑问题描述",
            "severity": "严重/中等/轻微",
            "suggestion": "修改建议"
        }}
    ]
}}
"""

    print(f"\n[逻辑检查] 开始检查...")

    try:
        current_client = get_client()
        response = current_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )

        result = response.choices[0].message.content if response.choices else ""

        clean = result.replace("```json", "").replace("```", "").strip()
        start, end = clean.find('{'), clean.rfind('}')
        if start >= 0 and end > start:
            json_str = _clean_control_chars_in_json(clean[start:end+1])
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                parsed = _parse_json_aggressive(json_str)

            issues = []
            for i, issue in enumerate(parsed.get('issues', [])):
                issues.append({
                    "id": f"logic_{i+1}",
                    "paragraph_id": issue.get('paragraph_id', 'p1'),
                    "dimension": "逻辑",
                    "type": "剧情逻辑",
                    "severity": issue.get('severity', '轻微'),
                    "quote": issue.get('quote', ''),
                    "description": issue.get('problem', ''),
                    "suggestion": issue.get('suggestion', '')
                })

            print(f"[逻辑检查] 完成 | 评分: {parsed.get('score', '?')} | 问题数: {len(issues)}")
            return {"score": parsed.get('score', 5), "issues": issues}

    except Exception as e:
        print(f"[逻辑检查] 异常: {e}")

    return {"score": 5, "issues": []}


def sync_review_pacing(paragraphs):
    """
    节奏把控检查维度
    检查叙事节奏、信息密度、读者体验

    Args:
        paragraphs: 段落列表

    Returns:
        {"score": 8, "issues": [...]}
    """
    task_type = "reviewer"
    model_name = get_model(task_type)
    temperature = get_temperature(task_type)

    numbered_content = ""
    for p in paragraphs:
        numbered_content += f"【段落{p['id']}】({p['word_count']}字)\n{p['text']}\n\n"

    total_words = sum(p['word_count'] for p in paragraphs)

    prompt = f"""【任务】作为叙事节奏审核专家，检查以下章节的节奏把控是否得当。

【待审章节】（共{len(paragraphs)}个段落，{total_words}字）
{numbered_content}

【检查要点】
1. 开头是否能在3个段落内抓住读者注意力？
2. 节奏张弛是否得当？是否有冗长的无意义描写？
3. 对话与叙述的比例是否合理？
4. 情绪高潮是否铺垫到位？
5. 结尾是否有钩子或悬念？
6. 信息密度是否适中（不要过于密集或过于稀疏）？
7. 场景转换是否自然？

【输出要求】
严格按JSON格式输出（不要用Markdown代码块）：
{{
    "score": 1-10分,
    "issues": [
        {{
            "paragraph_id": "段落ID",
            "quote": "问题原文引用（如适用）",
            "problem": "节奏问题描述",
            "severity": "严重/中等/轻微",
            "suggestion": "修改建议"
        }}
    ]
}}
"""

    print(f"\n[节奏检查] 开始检查...")

    try:
        current_client = get_client()
        response = current_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )

        result = response.choices[0].message.content if response.choices else ""

        clean = result.replace("```json", "").replace("```", "").strip()
        start, end = clean.find('{'), clean.rfind('}')
        if start >= 0 and end > start:
            json_str = _clean_control_chars_in_json(clean[start:end+1])
            try:
                parsed = json.loads(json_str)
            except json.JSONDecodeError:
                parsed = _parse_json_aggressive(json_str)

            issues = []
            for i, issue in enumerate(parsed.get('issues', [])):
                issues.append({
                    "id": f"pacing_{i+1}",
                    "paragraph_id": issue.get('paragraph_id', 'p1'),
                    "dimension": "节奏",
                    "type": "节奏把控",
                    "severity": issue.get('severity', '轻微'),
                    "quote": issue.get('quote', ''),
                    "description": issue.get('problem', ''),
                    "suggestion": issue.get('suggestion', '')
                })

            print(f"[节奏检查] 完成 | 评分: {parsed.get('score', '?')} | 问题数: {len(issues)}")
            return {"score": parsed.get('score', 5), "issues": issues}

    except Exception as e:
        print(f"[节奏检查] 异常: {e}")

    return {"score": 5, "issues": []}


def sync_review_chapter_multi_dimension(paragraphs, context_info):
    """
    多维度综合审稿
    分别进行人设、逻辑、节奏检查，然后汇总

    Args:
        paragraphs: 段落列表
        context_info: {
            "characters": "人物设定字符串",
            "world_setting": "世界观设定",
            "chapter_outline": "本章大纲"
        }

    Returns:
        {
            "overall_score": 7,
            "dimension_scores": {"人设": 8, "逻辑": 7, "节奏": 6},
            "issues": [...],
            "summary": "整体评价"
        }
    """
    print(f"\n{'='*50}")
    print(f"[多维度审稿] 开始 | 段落数: {len(paragraphs)}")
    print(f"{'='*50}")

    all_issues = []
    dimension_results = {}

    # 1. 人设一致性检查
    characters_info = context_info.get('characters', '')
    if characters_info:
        char_result = sync_review_character_consistency(paragraphs, characters_info)
        dimension_results['人设'] = char_result
        all_issues.extend(char_result['issues'])
    else:
        dimension_results['人设'] = {"score": 0, "issues": [], "skipped": True}

    # 2. 剧情逻辑检查
    world_setting = context_info.get('world_setting', '')
    chapter_outline = context_info.get('chapter_outline', '')
    if world_setting or chapter_outline:
        logic_result = sync_review_plot_logic(paragraphs, world_setting, chapter_outline)
        dimension_results['逻辑'] = logic_result
        all_issues.extend(logic_result['issues'])
    else:
        dimension_results['逻辑'] = {"score": 0, "issues": [], "skipped": True}

    # 3. 节奏把控检查
    pacing_result = sync_review_pacing(paragraphs)
    dimension_results['节奏'] = pacing_result
    all_issues.extend(pacing_result['issues'])

    # 计算总体评分
    scores = [r['score'] for r in dimension_results.values() if r.get('score', 0) > 0]
    overall_score = sum(scores) / len(scores) if scores else 5

    # 按严重程度统计
    severe_count = len([i for i in all_issues if i.get('severity') == '严重'])
    medium_count = len([i for i in all_issues if i.get('severity') == '中等'])
    minor_count = len([i for i in all_issues if i.get('severity') == '轻微'])

    # 验证段落ID
    valid_ids = {p['id'] for p in paragraphs}
    for issue in all_issues:
        if issue.get('paragraph_id') not in valid_ids:
            # 尝试通过quote匹配
            matched = find_paragraph_by_quote(paragraphs, issue.get('quote', ''))
            issue['paragraph_id'] = matched if matched else 'p1'

    result = {
        "overall_score": round(overall_score, 1),
        "dimension_scores": {
            name: result['score'] for name, result in dimension_results.items()
        },
        "issues": all_issues,
        "statistics": {
            "total_issues": len(all_issues),
            "severe": severe_count,
            "medium": medium_count,
            "minor": minor_count
        }
    }

    print(f"\n[多维度审稿] 完成！")
    print(f"  总分: {result['overall_score']}/10")
    print(f"  各维度: {result['dimension_scores']}")
    print(f"  问题数: {len(all_issues)} (严重:{severe_count} 中等:{medium_count} 轻微:{minor_count})")

    return result