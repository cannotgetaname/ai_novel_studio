import streamlit as st
from openai import OpenAI
import json
import os
import datetime
import time
import chromadb
from chromadb.utils import embedding_functions

# ================= 0. 配置加载模块 (Config Loader) =================
CONFIG_FILE = "config.json"

def load_config():
    # 如果没有配置文件，创建一个默认的
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "api_key": "sk-your-key-here",
            "base_url": "https://api.deepseek.com",
            "model_name": "deepseek-chat",
            "temperature": 1.3,
            "project_dir": "MyNovel_Data",
            "prompts": {
                "writer_system": "你是一个网文作家。",
                "editor_system": "你是一个编辑。",
                "architect_system": "你是一个架构师，只返回JSON。"
            }
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        return default_config
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# 加载配置
CFG = load_config()

# 初始化客户端
client = OpenAI(api_key=CFG['api_key'], base_url=CFG['base_url'])

# ================= 工具函数 =================
def log(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

# ================= 核心模块 1: 文件管理 =================
class NovelManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.chapters_dir = os.path.join(root_dir, "chapters")
        self.setting_file = os.path.join(root_dir, "setting.json")
        self.structure_file = os.path.join(root_dir, "structure.json")
        self._init_fs()

    def _init_fs(self):
        if not os.path.exists(self.chapters_dir): os.makedirs(self.chapters_dir)
        if not os.path.exists(self.setting_file):
            with open(self.setting_file, 'w', encoding='utf-8') as f:
                json.dump({"world_view": "", "characters": ""}, f, ensure_ascii=False, indent=4)
        if not os.path.exists(self.structure_file):
            default_structure = [{"id": 1, "title": "第一章", "outline": "开局。", "summary": ""}]
            with open(self.structure_file, 'w', encoding='utf-8') as f:
                json.dump(default_structure, f, ensure_ascii=False, indent=4)

    def load_settings(self):
        with open(self.setting_file, 'r', encoding='utf-8') as f: return json.load(f)
    def save_settings(self, data):
        with open(self.setting_file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
    def load_structure(self):
        with open(self.structure_file, 'r', encoding='utf-8') as f: return json.load(f)
    def save_structure(self, data):
        with open(self.structure_file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=4)
    def save_chapter_content(self, chapter_id, content):
        with open(os.path.join(self.chapters_dir, f"{chapter_id}.txt"), 'w', encoding='utf-8') as f: f.write(content)
    def load_chapter_content(self, chapter_id):
        path = os.path.join(self.chapters_dir, f"{chapter_id}.txt")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f: return f.read()
        return ""
    def delete_chapter(self, chapter_id):
        path = os.path.join(self.chapters_dir, f"{chapter_id}.txt")
        if os.path.exists(path): os.remove(path)

# ================= 核心模块 2: 记忆向量库 =================
class MemoryManager:
    def __init__(self, root_dir):
        db_path = os.path.join(root_dir, "chroma_db")
        self.client = chromadb.PersistentClient(path=db_path)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.client.get_or_create_collection(
            name="novel_memory",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "l2"} 
        )

    def add_chapter_memory(self, chapter_id, content):
        chunk_size = CFG.get('chunk_size', 500)
        overlap = CFG.get('overlap', 100)
        step = chunk_size - overlap
        chunks = []
        for i in range(0, len(content), step):
            chunk = content[i : i + chunk_size]
            if len(chunk) > 50: chunks.append(chunk)
        
        if not chunks: return
        ids = [f"ch_{chapter_id}_{i}" for i in range(len(chunks))]
        metadatas = [{"chapter_id": chapter_id, "chunk_index": i} for i in range(len(chunks))]
        self.collection.upsert(documents=chunks, metadatas=metadatas, ids=ids)

    def query_related_memory(self, query_text, n_results=5, threshold=1.5):
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=['documents', 'distances', 'metadatas'] 
        )
        valid_docs = []
        debug_info = []
        if results['documents']:
            docs = results['documents'][0]
            dists = results['distances'][0]
            metas = results['metadatas'][0]
            for doc, dist, meta in zip(docs, dists, metas):
                is_valid = dist < threshold
                info = {"text": doc, "distance": round(dist, 4), "source": f"第{meta['chapter_id']}章", "valid": is_valid}
                debug_info.append(info)
                if is_valid: valid_docs.append(doc)
        return valid_docs, debug_info

manager = NovelManager(CFG['project_dir'])
memory_manager = MemoryManager(CFG['project_dir'])

# ================= AI 调用函数 =================
def call_llm(prompt, system_prompt):
    try:
        response = client.chat.completions.create(
            model=CFG['model_name'],
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=CFG['temperature']
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"API Error: {e}")
        return ""

def generate_batch_outlines(settings, start_id, volume_theme, count=5):
    prompt = f"""
    【任务】生成{count}章大纲，起始ID{start_id}。
    【世界观】{settings['world_view'][:500]}...
    【主题】{volume_theme}
    【要求】纯JSON列表，格式：[{{'title':'xx','outline':'xx'}}]
    """
    res = call_llm(prompt, CFG['prompts']['architect_system'])
    clean_res = res.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_res)
    except:
        return None

# ================= 前端界面 (优化版) =================
def main():
    st.set_page_config(page_title="AI Novel Studio V6.0", layout="wide")
    st.title("📚 AI 网文工作站 (V6.0 配置化+低延迟版)")

    # 初始化 Session
    if 'structure' not in st.session_state: st.session_state['structure'] = manager.load_structure()
    if 'settings' not in st.session_state: st.session_state['settings'] = manager.load_settings()

    structure = st.session_state['structure']
    settings = st.session_state['settings']

    # Sidebar
    with st.sidebar:
        st.header("🗂️ 章节导航")
        chapter_titles = [f"{c['id']}. {c['title']}" for c in structure]
        
        if 'chap_sel_idx' not in st.session_state: st.session_state['chap_sel_idx'] = 0
        if st.session_state['chap_sel_idx'] >= len(structure): st.session_state['chap_sel_idx'] = len(structure) - 1

        # 这里的 selectbox 依然会触发刷新，这是必要的，否则无法切换章节
        selected_idx = st.selectbox("选择章节", range(len(structure)), 
                                    format_func=lambda x: chapter_titles[x], 
                                    index=st.session_state['chap_sel_idx'],
                                    key="chap_selector")
        
        st.session_state['chap_sel_idx'] = selected_idx
        current_chapter = structure[selected_idx]
        
        # 切换章节清理缓存
        if 'last_idx' not in st.session_state: st.session_state['last_idx'] = selected_idx
        if st.session_state['last_idx'] != selected_idx:
            st.session_state['last_idx'] = selected_idx
            key = f"editor_{current_chapter['id']}"
            if key in st.session_state: del st.session_state[key]
            if 'retrieved_debug' in st.session_state: del st.session_state['retrieved_debug']

        st.divider()
        with st.expander("🗑️ 危险区域"):
            confirm_del = st.checkbox("确认删除")
            if st.button("执行删除", disabled=not confirm_del):
                if len(structure) <= 1: st.error("至少保留一章")
                else:
                    manager.delete_chapter(current_chapter['id'])
                    del structure[selected_idx]
                    manager.save_structure(structure)
                    st.session_state['structure'] = structure
                    st.session_state['chap_sel_idx'] = 0
                    st.rerun()

    tab1, tab2, tab3 = st.tabs(["⚙️ 设定", "✍️ 写作 (RAG)", "🏗️ 架构师"])

    # Tab 1: 设定 (使用 Form 优化)
    with tab1:
        # 【优化点】使用 st.form 包裹输入框
        # 这样你在打字时，页面不会刷新，只有点“保存设定”才会刷新
        with st.form("setting_form"):
            col1, col2 = st.columns(2)
            with col1: 
                new_world = st.text_area("世界观", settings['world_view'], height=300)
            with col2: 
                new_chars = st.text_area("人物", settings['characters'], height=300)
            
            submitted = st.form_submit_button("💾 保存设定")
            if submitted:
                settings['world_view'] = new_world
                settings['characters'] = new_chars
                manager.save_settings(settings)
                st.success("保存成功")

    # Tab 2: 写作 (使用 Form 优化)
    with tab2:
        st.subheader(f"编辑：{current_chapter['title']}")
        
        editor_key = f"editor_{current_chapter['id']}"
        if editor_key not in st.session_state:
            st.session_state[editor_key] = manager.load_chapter_content(current_chapter['id'])

        # RAG 调试区 (保持独立，方便实时调试)
        with st.expander("🔍 记忆检索控制台", expanded=False):
            col_ctrl, col_view = st.columns([1, 2])
            with col_ctrl:
                threshold = st.slider("距离阈值", 0.5, 2.0, 1.4, 0.1)
                if st.button("手动检索测试"):
                    query = f"{current_chapter['title']} {current_chapter['outline']}"
                    valid_docs, debug_info = memory_manager.query_related_memory(query, threshold=threshold)
                    st.session_state['retrieved_debug'] = debug_info
            with col_view:
                if 'retrieved_debug' in st.session_state:
                    for item in st.session_state['retrieved_debug']:
                        icon = "✅" if item['valid'] else "🚫"
                        st.markdown(f"**{icon} {item['distance']}** - {item['source']}")

        # 【优化点】核心写作区使用 Form
        # 这样你手动修改正文时，不会每打一个字就卡一下
        with st.form("writer_form"):
            new_title = st.text_input("标题", current_chapter['title'])
            new_outline = st.text_area("大纲", current_chapter['outline'])
            
            # 生成按钮和保存按钮不能同时放在 form 里，因为 form 只有一个 submit
            # 所以我们把“生成”放在 form 外面，或者用两个 form
            # 这里为了流畅，我们把“手动编辑”和“保存”放在一个 form 里
            
            content = st.text_area("正文", value=st.session_state[editor_key], height=500)
            
            col_s1, col_s2 = st.columns([1, 1])
            with col_s1:
                save_submitted = st.form_submit_button("💾 保存并存入记忆库")
            
            if save_submitted:
                st.session_state[editor_key] = content # 更新 session
                manager.save_chapter_content(current_chapter['id'], content)
                structure[selected_idx]['title'] = new_title
                structure[selected_idx]['outline'] = new_outline
                manager.save_structure(structure)
                with st.spinner("存入向量库..."):
                    memory_manager.add_chapter_memory(current_chapter['id'], content)
                st.success("保存成功！")

        # 生成按钮放在 Form 外面，因为它需要触发 API 调用
        if st.button("🚀 AI 生成正文"):
            with st.spinner("检索记忆 -> 生成中..."):
                query = f"{new_title} {new_outline}"
                valid_docs, _ = memory_manager.query_related_memory(query, threshold=threshold)
                context_str = "\n".join(valid_docs)
                prompt = f"【世界观】\n{settings['world_view']}\n【相关记忆】\n{context_str}\n【本章大纲】\n标题：{new_title}\n内容：{new_outline}\n请撰写正文。"
                res = call_llm(prompt, CFG['prompts']['writer_system'])
                if res: 
                    st.session_state[editor_key] = res
                    st.rerun()

    # Tab 3: 架构师 (使用 Form 优化)
    with tab3:
        st.header("🏗️ 批量剧情生成")
        with st.form("architect_form"):
            next_volume_theme = st.text_area("接下来的剧情梗概", height=150)
            batch_count = st.slider("生成章节数量", 3, 10, 5)
            submitted_arch = st.form_submit_button("🎲 生成后续大纲")
            
            if submitted_arch:
                start_id = structure[-1]['id'] + 1
                with st.spinner("架构师正在思考..."):
                    new_outlines = generate_batch_outlines(settings, start_id, next_volume_theme, batch_count)
                    if new_outlines:
                        st.session_state['temp_batch_outlines'] = new_outlines
                        st.success("生成完毕，请在下方确认")

        if 'temp_batch_outlines' in st.session_state:
            st.subheader("预览")
            new_data = st.session_state['temp_batch_outlines']
            for item in new_data:
                st.text(f"{item['title']}")
                st.caption(f"{item['outline']}")
            
            if st.button("✅ 确认添加"):
                for item in new_data:
                    new_chapter = {"id": structure[-1]['id'] + 1, "title": item['title'], "outline": item['outline'], "summary": ""}
                    structure.append(new_chapter)
                manager.save_structure(structure)
                st.session_state['structure'] = structure
                del st.session_state['temp_batch_outlines']
                st.rerun()

if __name__ == "__main__":
    main()