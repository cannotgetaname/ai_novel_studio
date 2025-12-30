import json
import os
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI

# ================= 配置加载 =================
def load_config():
    if not os.path.exists("config.json"):
        return {}
    with open("config.json", 'r', encoding='utf-8') as f:
        return json.load(f)

CFG = load_config()
client = OpenAI(api_key=CFG.get('api_key'), base_url=CFG.get('base_url'))

# ================= 小说管理器 (数据层) =================
class NovelManager:
    def __init__(self):
        self.root_dir = CFG.get('project_dir', 'MyNovel_Data')
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

# ================= 向量库管理器 (RAG) =================
class MemoryManager:
    def __init__(self):
        self.root_dir = CFG.get('project_dir', 'MyNovel_Data')
        db_path = os.path.join(self.root_dir, "chroma_db")
        self.client = chromadb.PersistentClient(path=db_path)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(name="novel_memory", embedding_function=self.embedding_fn)

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
    except Exception as e: return f"Error: {str(e)}"

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

def sync_analyze_state(content, current_data_summary):
    task_type = "auditor"
    model_name = CFG['models'].get(task_type, "deepseek-reasoner")
    temperature = CFG['temperatures'].get(task_type, 1.0)
    sys_prompt = CFG['prompts'].get('auditor_system', "你是一个世界观管理员。")
    prompt = f"【当前正文】\n{content[:4000]}...\n【现有数据库摘要】\n{current_data_summary}\n【任务】提取状态变更、物品变更、新实体、关系变更。请严格返回 JSON。"
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception as e: return f"Error: {str(e)}"

def apply_state_changes(novel_manager, changes):
    logs = []
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

    items = novel_manager.load_items()
    for update in changes.get('item_updates', []):
        for item in items:
            if item['name'] == update['name']:
                item[update['field']] = update['new_value']
                logs.append(f"更新物品 [{item['name']}]: {update['field']} -> {update['new_value']}")
    for new_item in changes.get('new_items', []):
        if not any(i['name'] == new_item['name'] for i in items):
            items.append(new_item)
            logs.append(f"新增物品: {new_item['name']}")
    novel_manager.save_items(items)

    locs = novel_manager.load_locations()
    for new_loc in changes.get('new_locs', []):
        if not any(l['name'] == new_loc['name'] for l in locs):
            locs.append(new_loc)
            logs.append(f"新增地点: {new_loc['name']}")
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