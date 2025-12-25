import streamlit as st
from openai import OpenAI
import json
import os
import datetime
import time
import chromadb
from chromadb.utils import embedding_functions

# ================= 配置区 =================
API_KEY = "sk-xxxxxxxxxxxxxxxxxxxxxxxx"  # 记得换回你的 Key
BASE_URL = "https://api.deepseek.com"
PROJECT_DIR = "MyNovel_Data"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ================= 工具函数 =================
def log(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

# ================= 核心模块 1: 文件管理 (Storage Controller) =================
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
    
    # 【新增】删除章节 (Free Memory)
    def delete_chapter(self, chapter_id):
        # 1. 删除物理文件
        path = os.path.join(self.chapters_dir, f"{chapter_id}.txt")
        if os.path.exists(path):
            os.remove(path)
            log(f"已删除文件: {path}")
        
        # 2. 更新结构表 (需在外部调用 save_structure)
        # 这里只负责文件层面的清理，逻辑层面的清理在 main 函数里做

# ================= 核心模块 2: 记忆向量库 (RAG) =================
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
        log(f"正在处理第 {chapter_id} 章记忆...")
        chunk_size = 500
        overlap = 100
        step = chunk_size - overlap
        chunks = []
        for i in range(0, len(content), step):
            chunk = content[i : i + chunk_size]
            if len(chunk) > 50: chunks.append(chunk)
        
        if not chunks: return

        ids = [f"ch_{chapter_id}_{i}" for i in range(len(chunks))]
        metadatas = [{"chapter_id": chapter_id, "chunk_index": i} for i in range(len(chunks))]
        
        self.collection.upsert(documents=chunks, metadatas=metadatas, ids=ids)
        log(f"记忆存储完成，生成 {len(chunks)} 个重叠片段")

    def query_related_memory(self, query_text, n_results=5, threshold=1.5):
        log(f"检索: {query_text[:15]}... (阈值: {threshold})")
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

manager = NovelManager(PROJECT_DIR)
memory_manager = MemoryManager(PROJECT_DIR)

# ================= AI 调用函数 =================
def call_llm(prompt, system_prompt="你是一个网文作家"):
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            stream=False,
            temperature=1.3
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"API Error: {e}")
        return ""

# 【恢复】批量大纲生成器
def generate_batch_outlines(settings, start_id, volume_theme, count=5):
    prompt = f"""
    【任务】
    请根据以下世界观和当前剧情走向，为接下来的 {count} 章设计详细大纲。
    
    【世界观】
    {settings['world_view'][:500]}...
    
    【当前卷/剧情阶段主题】
    {volume_theme}
    
    【要求】
    1. 起始章节ID：{start_id}
    2. 输出格式必须是纯 JSON 列表，不要包含 Markdown 代码块标记。
    3. 格式示例：
    [
        {{"title": "第{start_id}章：xxxx", "outline": "主角做了什么..."}},
        {{"title": "第{start_id+1}章：xxxx", "outline": "反派做了什么..."}}
    ]
    """
    res = call_llm(prompt, system_prompt="你是一个专业的网文主编，擅长规划剧情节奏。请只返回JSON数据。")
    clean_res = res.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_res)
    except json.JSONDecodeError:
        log("JSON 解析失败")
        return None

# ================= 前端界面 =================
def main():
    st.set_page_config(page_title="AI Novel Studio V5.0", layout="wide")
    st.title("📚 AI 网文工作站 (V5.0 完整版)")

    if 'structure' not in st.session_state: st.session_state['structure'] = manager.load_structure()
    if 'settings' not in st.session_state: st.session_state['settings'] = manager.load_settings()

    structure = st.session_state['structure']
    settings = st.session_state['settings']

    # ================= 侧边栏：章节管理 =================
    with st.sidebar:
        st.header("🗂️ 章节导航")
        chapter_titles = [f"{c['id']}. {c['title']}" for c in structure]
        
        # 这里的 key 很重要，防止删除后索引越界
        if 'chap_sel_idx' not in st.session_state: st.session_state['chap_sel_idx'] = 0
        
        # 保护机制：如果索引越界（比如删除了最后一章），重置为 0
        if st.session_state['chap_sel_idx'] >= len(structure):
            st.session_state['chap_sel_idx'] = len(structure) - 1

        selected_idx = st.selectbox("选择章节", range(len(structure)), 
                                    format_func=lambda x: chapter_titles[x], 
                                    index=st.session_state['chap_sel_idx'],
                                    key="chap_selector")
        
        # 更新 session 中的索引
        st.session_state['chap_sel_idx'] = selected_idx
        current_chapter = structure[selected_idx]
        
        # 章节切换清理缓存
        if 'last_idx' not in st.session_state: st.session_state['last_idx'] = selected_idx
        if st.session_state['last_idx'] != selected_idx:
            st.session_state['last_idx'] = selected_idx
            key = f"editor_{current_chapter['id']}"
            if key in st.session_state: del st.session_state[key]
            if 'retrieved_debug' in st.session_state: del st.session_state['retrieved_debug']

        st.divider()
        
        # 【新增】删除功能区
        with st.expander("🗑️ 危险区域 (Delete)", expanded=False):
            st.warning(f"正在操作：{current_chapter['title']}")
            confirm_del = st.checkbox("我确定要删除此章节")
            if st.button("执行删除", disabled=not confirm_del):
                if len(structure) <= 1:
                    st.error("至少保留一章！")
                else:
                    # 1. 物理删除
                    manager.delete_chapter(current_chapter['id'])
                    # 2. 逻辑删除
                    del structure[selected_idx]
                    manager.save_structure(structure)
                    # 3. 刷新状态
                    st.session_state['structure'] = structure
                    st.session_state['chap_sel_idx'] = 0 # 删完回到第一章
                    st.success("删除成功！")
                    time.sleep(1)
                    st.rerun()

    # ================= 主界面 Tabs =================
    tab1, tab2, tab3 = st.tabs(["⚙️ 设定", "✍️ 写作 (RAG)", "🏗️ 架构师 (批量)"])

    # Tab 1: 设定
    with tab1:
        col1, col2 = st.columns(2)
        with col1: new_world = st.text_area("世界观", settings['world_view'], height=300)
        with col2: new_chars = st.text_area("人物", settings['characters'], height=300)
        if st.button("保存设定"):
            settings['world_view'] = new_world
            settings['characters'] = new_chars
            manager.save_settings(settings)
            st.success("保存成功")

    # Tab 2: 写作 (RAG)
    with tab2:
        st.subheader(f"编辑：{current_chapter['title']}")
        new_title = st.text_input("标题", current_chapter['title'])
        new_outline = st.text_area("大纲", current_chapter['outline'])
        
        editor_key = f"editor_{current_chapter['id']}"
        if editor_key not in st.session_state:
            st.session_state[editor_key] = manager.load_chapter_content(current_chapter['id'])

        # RAG 调试区
        with st.expander("🔍 记忆检索控制台 (Signal Monitor)", expanded=True):
            col_ctrl, col_view = st.columns([1, 2])
            with col_ctrl:
                threshold = st.slider("距离阈值", 0.5, 2.0, 1.4, 0.1)
                if st.button("手动检索测试"):
                    query = f"{new_title} {new_outline}"
                    valid_docs, debug_info = memory_manager.query_related_memory(query, threshold=threshold)
                    st.session_state['retrieved_debug'] = debug_info
            with col_view:
                if 'retrieved_debug' in st.session_state:
                    for item in st.session_state['retrieved_debug']:
                        icon = "✅" if item['valid'] else "🚫"
                        st.markdown(f"**{icon} Dist: {item['distance']}** - {item['source']}")
                        st.caption(f"{item['text'][:60]}...")

        col_gen, col_save = st.columns([1, 4])
        with col_gen:
            if st.button("🚀 生成正文"):
                with st.spinner("检索记忆 -> 生成中..."):
                    query = f"{new_title} {new_outline}"
                    valid_docs, _ = memory_manager.query_related_memory(query, threshold=threshold)
                    context_str = "\n".join(valid_docs)
                    prompt = f"【世界观】\n{settings['world_view']}\n【相关记忆】\n{context_str}\n【本章大纲】\n标题：{new_title}\n内容：{new_outline}\n请撰写正文。"
                    res = call_llm(prompt)
                    if res: 
                        st.session_state[editor_key] = res
                        st.rerun()
        
        content = st.text_area("正文", height=500, key=editor_key)
        
        with col_save:
            if st.button("💾 保存并存入记忆库"):
                manager.save_chapter_content(current_chapter['id'], content)
                structure[selected_idx]['title'] = new_title
                structure[selected_idx]['outline'] = new_outline
                manager.save_structure(structure)
                with st.spinner("存入向量库..."):
                    memory_manager.add_chapter_memory(current_chapter['id'], content)
                st.success("保存成功！")

    # Tab 3: 架构师 (完整恢复)
    with tab3:
        st.header("🏗️ 批量剧情生成")
        st.info("输入接下来的剧情走向，AI 将自动为你规划后续章节的大纲。")
        
        col_input, col_preview = st.columns([1, 1])
        
        with col_input:
            next_volume_theme = st.text_area("接下来的剧情梗概 (例如：主角进入秘境，遇到仇家，获得神器)", height=150)
            batch_count = st.slider("生成章节数量", 3, 10, 5)
            
            if st.button("🎲 生成后续大纲"):
                start_id = structure[-1]['id'] + 1
                with st.spinner("架构师正在思考剧情..."):
                    new_outlines = generate_batch_outlines(settings, start_id, next_volume_theme, batch_count)
                    
                    if new_outlines:
                        st.session_state['temp_batch_outlines'] = new_outlines
                        st.success("大纲生成完毕！请在右侧确认。")
                    else:
                        st.error("生成失败，请重试")

        with col_preview:
            if 'temp_batch_outlines' in st.session_state:
                st.subheader("预览与确认")
                new_data = st.session_state['temp_batch_outlines']
                
                # 显示预览
                for item in new_data:
                    st.text(f"{item['title']}")
                    st.caption(f"{item['outline']}")
                    st.divider()
                
                if st.button("✅ 确认并添加到书籍"):
                    # 将新生成的章节追加到 structure 列表
                    for item in new_data:
                        new_chapter = {
                            "id": structure[-1]['id'] + 1, # 自动递增ID
                            "title": item['title'],
                            "outline": item['outline'],
                            "summary": "" # 新章节摘要为空
                        }
                        structure.append(new_chapter)
                    
                    # 保存并刷新
                    manager.save_structure(structure)
                    st.session_state['structure'] = structure
                    del st.session_state['temp_batch_outlines'] # 清除临时数据
                    st.success(f"成功添加 {len(new_data)} 章！请回到'写作'标签页开始创作。")
                    time.sleep(1)
                    st.rerun()

if __name__ == "__main__":
    main()