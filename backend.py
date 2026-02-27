import json
import os
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
import shutil # <--- 新增
import glob   # <--- 新增
from datetime import datetime # <--- 必须加这一行！

import networkx as nx

import hashlib

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

    # --- GraphRAG 功能：获取某人的“关系网文本” ---
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
        except:
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
# 初始化全局 client
client = OpenAI(api_key=CFG.get('api_key'), base_url=CFG.get('base_url'))

# 【新增】保存配置并热重载
def save_global_config(new_config):
    global CFG, client
    try:
        # 1. 写入文件
        with open("config.json", 'w', encoding='utf-8') as f:
            json.dump(new_config, f, ensure_ascii=False, indent=4)
        
        # 2. 热更新内存中的配置
        CFG.update(new_config)
        
        # 3. 重置 OpenAI 客户端 (这一步很关键，否则改了 Key 不生效)
        client = OpenAI(api_key=CFG.get('api_key'), base_url=CFG.get('base_url'))
        
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

        # 2. 净化新书名 (防止非法字符)
        safe_new_name = "".join([c for c in new_name if c.isalpha() or c.isdigit() or c in (' ', '_', '-')]).strip()
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
        except:
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
        except: return []

    def save_characters(self, data):
        with open(self.char_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_items(self):
        try:
            with open(self.item_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def save_items(self, data):
        with open(self.item_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_locations(self):
        try:
            with open(self.loc_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []

    def save_locations(self, data):
        with open(self.loc_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_volumes(self):
        try:
            with open(self.volume_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
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
        except: return []

    def save_structure(self, data):
        with open(self.structure_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    def save_chapter_content(self, chapter_id, content):
        with open(os.path.join(self.chapters_dir, f"{chapter_id}.txt"), 'w', encoding='utf-8') as f:
            f.write(content)
    
    def load_chapter_content(self, chapter_id):
        path = os.path.join(self.chapters_dir, f"{chapter_id}.txt")
        return open(path, 'r', encoding='utf-8').read() if os.path.exists(path) else ""
    
    def delete_chapter(self, chapter_id):
        path = os.path.join(self.chapters_dir, f"{chapter_id}.txt")
        if os.path.exists(path): os.remove(path)

    def get_total_word_count(self):
        structure = self.load_structure()
        total = 0
        for chap in structure:
            content = self.load_chapter_content(chap['id'])
            total += len(content)
        return total

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
            source_id = int(item['source'].replace("第", "").replace("章", ""))
            distance = current_chapter_id - source_id
            prefix = "[REF]"
            if 1 <= distance <= 3: prefix = "[SKIP-RECENT]"
            snippet = f"{prefix} (第{source_id}章): {item['text']}"
            processed_snippets.append(snippet)
        
        context_block = "\n\n".join(processed_snippets)
        sys_prompt = CFG['prompts'].get('knowledge_filter_system', "请筛选有用的背景信息。")
        filter_prompt = f"【本章大纲】{query}\n【检索片段】\n{context_block}\n【任务】筛选有用背景，忽略[SKIP-RECENT]，合并重复，输出简练背景。"
        filtered_context = sync_call_llm(filter_prompt, sys_prompt, task_type="editor")
        return filtered_context, debug_info
    
    def update_chapter_summary(self, chapter_id, content):
        if len(content) < 100: return ""
        sys_prompt = CFG['prompts'].get('summary_chapter_system', "请总结章节。")
        prompt = f"请阅读以下小说章节，用 150 字以内的篇幅，高度概括本章发生的**核心剧情**、**关键转折**和**重要伏笔**。\n\n【正文】\n{content[:4000]}"
        summary = sync_call_llm(prompt, sys_prompt, task_type="writer")
        structure = self.load_structure()
        for chap in structure:
            if chap['id'] == chapter_id:
                chap['summary'] = summary
                break
        self.save_structure(structure)
        return summary

    def update_global_summary(self):
        structure = self.load_structure()
        all_summaries = []
        for chap in structure:
            if chap.get('summary'):
                all_summaries.append(f"第{chap['id']}章: {chap['summary']}")
        if not all_summaries: return "暂无剧情。"
        combined_text = "\n".join(all_summaries)
        sys_prompt = CFG['prompts'].get('summary_book_system', "请总结全书。")
        prompt = f"以下是这就本小说目前的**分章剧情摘要**：\n{combined_text}\n【任务】请根据以上分章摘要，写一份**全书目前的剧情总纲**（500字左右）。"
        global_summary = sync_call_llm(prompt, sys_prompt, task_type="architect")
        settings = self.load_settings()
        settings['book_summary'] = global_summary
        self.save_settings(settings)
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
            
            # 打包 data 目录
            if os.path.exists("data"):
                shutil.make_archive(archive_path, 'zip', "data")
                
                # 清理旧备份 (只保留最近 20 个)
                backups = sorted(glob.glob(os.path.join(backup_dir, "*.zip")))
                if len(backups) > 20:
                    for b in backups[:-20]:
                        try: os.remove(b)
                        except: pass
                return f"已备份: {filename}.zip"
            return "数据目录不存在，跳过备份"
        except Exception as e:
            return f"备份失败: {str(e)}"

    # 2. 创建章节快照 (History Snapshot)
    def create_chapter_snapshot(self, chapter_id, content):
        try:
            snapshot_dir = os.path.join("data", "snapshots", str(chapter_id))
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
                    except: pass
        except Exception as e:
            print(f"Snapshot error: {e}")

    # 3. 获取章节快照列表
    def get_chapter_snapshots(self, chapter_id):
        snapshot_dir = os.path.join("data", "snapshots", str(chapter_id))
        if not os.path.exists(snapshot_dir): return []
        
        snapshots = []
        files = sorted(glob.glob(os.path.join(snapshot_dir, "*.txt")), reverse=True)
        for f in files:
            ts_str = os.path.basename(f).replace(".txt", "")
            try:
                dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                display_time = ts_str
            
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    preview = file.read(100).replace("\n", " ") + "..."
            except: preview = "无法读取内容"
                
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
            "gold_finger": "请脑洞大开，生成 5 个独特且爽点十足的网文“金手指”或“系统”设定。简短描述。"
        }
        
        prompt = prompts.get(type_key, "请随机生成一些灵感。")
        
        # 2. 调用 LLM (复用已有的 sync_call_llm，注意这里其实应该用异步，但为了代码简单复用 io_bound)
        # 这里我们临时构造一个 system prompt
        sys_prompt = CFG['prompts'].get('inspiration_assistant_system', "你是一个网文灵感助手。请只返回请求的内容，不要废话。")
        
        try:
            # 使用已有的 client
            if not client: return "错误：未配置 API Key"
            
            response = client.chat.completions.create(
                model=CFG['models'].get('writer', 'gpt-3.5-turbo'), # 借用 writer 模型
                messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
                temperature=0.9 # 灵感需要高创造性
            )
            return response.choices[0].message.content
        except Exception as e:
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

        sys_prompt = CFG['prompts']['architect_system']
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

def sync_call_llm(prompt, system_prompt, task_type="writer"):
    model_name = CFG['models'].get(task_type, "deepseek-chat")
    temperature = CFG['temperatures'].get(task_type, 1.3)
    print(f"\n[LLM Router] 任务: {task_type} | 模型: {model_name}")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"LLM调用失败: {error_msg}")
        return error_msg

def sync_rewrite_llm(selected_text, context_pre, context_post, instruction):
    task_type = "editor"
    model_name = CFG['models'].get(task_type, "deepseek-chat")
    temperature = CFG['temperatures'].get(task_type, 0.7)
    prompt = f"【任务】重写文本。\n【上文】...{context_pre[-500:]}\n【待修改】{selected_text}\n【下文】{context_post[:500]}...\n【要求】{instruction}"
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": "专业编辑"}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e: return f"Error: {str(e)}"

def sync_review_chapter(content, context_str):
    task_type = "reviewer"
    model_name = CFG['models'].get(task_type, "deepseek-chat")
    temperature = CFG['temperatures'].get(task_type, 0.5)
    sys_prompt = CFG['prompts'].get('reviewer_system', "你是一个严厉的编辑。")
    prompt = f"【待审查正文】\n{content}\n【参考设定】\n{context_str}\n【任务】审查逻辑一致性、剧情节奏、文笔。输出Markdown报告。"
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e: return f"Error: {str(e)}"

def sync_analyze_time(content, prev_time_label):
    task_type = "timekeeper"
    model_name = CFG['models'].get(task_type, "deepseek-chat")
    temperature = CFG['temperatures'].get(task_type, 0.1)
    sys_prompt = CFG['prompts'].get('timekeeper_system', "你是一个时间记录员。")
    prompt = f"【上一章时间】{prev_time_label}\n【本章正文】{content[:3000]}...\n【任务】1.分析时间流逝 2.推算当前时间 3.提取事件\n【输出格式】严格JSON: {{\"label\": \"...\", \"duration\": \"...\", \"events\": [\"...\"]}}"
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e: return f"Error: {str(e)}"

# 【修改】状态分析接口：增加提取“地点连接”的指令
def sync_analyze_state(content, current_data_summary):
    task_type = "auditor"
    model_name = CFG['models'].get(task_type, "deepseek-reasoner")
    temperature = CFG['temperatures'].get(task_type, 1.0)
    sys_prompt = CFG['prompts'].get('auditor_system', "你是一个世界观管理员。")
    
    prompt = f"""
    【当前正文】
    {content[:4000]}...
    
    【现有数据库摘要】
    {current_data_summary}
    
    【任务】
    请分析正文，检测以下变化（请严格区分“更新”和“新增”）：
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
    print(f"\n[LLM Router] 任务: State Auditor | 模型: {model_name}")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e: return f"Error: {str(e)}"

# 【修改】应用变更：增加处理“地点连接”的逻辑
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