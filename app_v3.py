import streamlit as st
from openai import OpenAI
import json
import os
import datetime
import time

# ================= 配置区 =================
API_KEY = "sk-1807d7a148974eaf9f68eed88b0b2322"  # 记得换回你的 Key
BASE_URL = "https://api.deepseek.com"
PROJECT_DIR = "MyNovel_Data"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# ================= 工具函数 =================
def log(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

# ================= 后端逻辑 =================
class NovelManager:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.chapters_dir = os.path.join(root_dir, "chapters")
        self.setting_file = os.path.join(root_dir, "setting.json")
        self.structure_file = os.path.join(root_dir, "structure.json")
        self._init_fs()

    def _init_fs(self):
        if not os.path.exists(self.chapters_dir):
            os.makedirs(self.chapters_dir)
        if not os.path.exists(self.setting_file):
            default_setting = {"world_view": "待补充...", "characters": "待补充..."}
            with open(self.setting_file, 'w', encoding='utf-8') as f:
                json.dump(default_setting, f, ensure_ascii=False, indent=4)
        if not os.path.exists(self.structure_file):
            default_structure = [{"id": 1, "title": "第一章：初入江湖", "outline": "主角醒来。", "summary": ""}]
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
    
    # 【修复】这里是之前报错的地方，已修正为标准写法
    def load_chapter_content(self, chapter_id):
        path = os.path.join(self.chapters_dir, f"{chapter_id}.txt")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

manager = NovelManager(PROJECT_DIR)

# ================= AI 调用函数 =================
def call_llm(prompt, system_prompt="你是一个网文作家"):
    log("--- Call API ---")
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

# 批量大纲生成器
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
    
    # 清洗数据
    clean_res = res.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean_res)
    except json.JSONDecodeError:
        log("JSON 解析失败，返回原始文本")
        return None

# ================= 前端界面 =================
def main():
    st.set_page_config(page_title="AI Novel Studio V3.1", layout="wide")
    st.title("📚 AI 网文工作站 (V3.1 修复版)")

    # 初始化 Session
    if 'structure' not in st.session_state:
        st.session_state['structure'] = manager.load_structure()
    if 'settings' not in st.session_state:
        st.session_state['settings'] = manager.load_settings()

    structure = st.session_state['structure']
    settings = st.session_state['settings']

    # Sidebar
    with st.sidebar:
        st.header("🗂️ 章节导航")
        chapter_titles = [f"{c['id']}. {c['title']}" for c in structure]
        selected_idx = st.selectbox("选择章节", range(len(structure)), format_func=lambda x: chapter_titles[x], key="chap_sel")
        current_chapter = structure[selected_idx]
        
        # 章节切换逻辑
        if 'last_idx' not in st.session_state: st.session_state['last_idx'] = selected_idx
        if st.session_state['last_idx'] != selected_idx:
            st.session_state['last_idx'] = selected_idx
            key = f"editor_{current_chapter['id']}"
            if key in st.session_state: del st.session_state[key] # 清除缓存

    # Main Tabs
    tab1, tab2, tab3 = st.tabs(["⚙️ 设定", "✍️ 写作", "🏗️ 架构师(批量)"])

    # Tab 1: 设定
    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            new_world = st.text_area("世界观", settings['world_view'], height=300)
        with col2:
            new_chars = st.text_area("人物", settings['characters'], height=300)
        if st.button("保存设定"):
            settings['world_view'] = new_world
            settings['characters'] = new_chars
            manager.save_settings(settings)
            st.success("保存成功")

    # Tab 2: 写作
    with tab2:
        st.subheader(f"编辑：{current_chapter['title']}")
        new_title = st.text_input("标题", current_chapter['title'])
        new_outline = st.text_area("大纲", current_chapter['outline'])
        
        editor_key = f"editor_{current_chapter['id']}"
        
        # 只有当缓存里没有时，才去读硬盘
        if editor_key not in st.session_state:
            st.session_state[editor_key] = manager.load_chapter_content(current_chapter['id'])

        if st.button("🚀 生成正文"):
            with st.spinner("生成中..."):
                prompt = f"设定：{settings['world_view']}\n大纲：{new_outline}\n请写2000字正文。"
                res = call_llm(prompt)
                if res: 
                    st.session_state[editor_key] = res
                    st.rerun()
        
        content = st.text_area("正文", height=500, key=editor_key)
        
        if st.button("💾 保存章节"):
            manager.save_chapter_content(current_chapter['id'], content)
            structure[selected_idx]['title'] = new_title
            structure[selected_idx]['outline'] = new_outline
            manager.save_structure(structure)
            st.success("已保存")

    # Tab 3: 架构师
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