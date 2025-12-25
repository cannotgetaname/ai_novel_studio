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

# ================= 调试日志 =================
def log(message):
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")

# ================= 后端逻辑 (IO Driver) =================

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
            default_structure = [
                {"id": 1, "title": "第一章：初入江湖", "outline": "主角醒来，发现自己穿越了。", "summary": "主角穿越到了异界。"}
            ]
            with open(self.structure_file, 'w', encoding='utf-8') as f:
                json.dump(default_structure, f, ensure_ascii=False, indent=4)

    def load_settings(self):
        with open(self.setting_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_settings(self, data):
        with open(self.setting_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_structure(self):
        with open(self.structure_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_structure(self, data):
        with open(self.structure_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def save_chapter_content(self, chapter_id, content):
        path = os.path.join(self.chapters_dir, f"{chapter_id}.txt")
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

    def load_chapter_content(self, chapter_id):
        path = os.path.join(self.chapters_dir, f"{chapter_id}.txt")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    # 【优化】只在初始化时调用一次，平时不调用
    def calculate_total_words_from_disk(self):
        log(">>> [IO操作] 正在扫描硬盘计算总字数...")
        total_count = 0
        structure = self.load_structure()
        for chapter in structure:
            content = self.load_chapter_content(chapter['id'])
            total_count += len(content)
        return total_count

manager = NovelManager(PROJECT_DIR)

# ================= AI 调用函数 =================

def call_llm(prompt, system_prompt="你是一个网文作家"):
    log("--- 开始调用 DeepSeek API ---")
    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            stream=False
        )
        log(f"--- API 调用结束，耗时: {time.time() - start_time:.2f}s ---")
        return response.choices[0].message.content
    except Exception as e:
        log(f"API Error: {e}")
        st.error(f"API Error: {e}")
        return ""

def auto_summarize(content):
    prompt = f"请将以下小说正文总结为200字以内的剧情摘要，包含关键人物动作和结果，不要废话：\n\n{content[:3000]}"
    return call_llm(prompt, system_prompt="你是一个专业的编辑")

# ================= 前端界面 (UI) =================

def main():
    st.set_page_config(page_title="AI Novel Studio V2.3 (Fast)", layout="wide")
    st.title("📚 AI 网文工作站 (V2.3 极速版)")

    # ================= 1. 缓存层 (SRAM) =================
    # 只有当 session_state 为空时，才去读硬盘
    
    if 'settings' not in st.session_state:
        log("初始化：加载设定到内存")
        st.session_state['settings'] = manager.load_settings()

    if 'structure' not in st.session_state:
        log("初始化：加载大纲到内存")
        st.session_state['structure'] = manager.load_structure()

    if 'total_words' not in st.session_state:
        # 第一次启动算一次，后面只做加减法
        st.session_state['total_words'] = manager.calculate_total_words_from_disk()

    # 快捷引用 (Pointer)
    settings = st.session_state['settings']
    structure = st.session_state['structure']

    # ================= 2. 侧边栏 =================
    with st.sidebar:
        st.header("🗂️ 章节管理")
        
        # 直接读内存，不读硬盘，瞬间完成
        st.metric(label="全书总字数", value=f"{st.session_state['total_words']:,}")
        st.divider()

        chapter_titles = [f"{c['id']}. {c['title']}" for c in structure]
        
        # 章节选择器
        selected_idx = st.selectbox("选择章节", range(len(structure)), format_func=lambda x: chapter_titles[x], key="chapter_selector")
        current_chapter = structure[selected_idx]
        
        # 章节切换检测
        if 'last_selected_idx' not in st.session_state:
            st.session_state['last_selected_idx'] = selected_idx
        
        if st.session_state['last_selected_idx'] != selected_idx:
            log(f"切换章节: {st.session_state['last_selected_idx']} -> {selected_idx}")
            st.session_state['last_selected_idx'] = selected_idx
            # 切换章节时，清除编辑器缓存，强制重新加载
            editor_key = f"editor_{current_chapter['id']}"
            if editor_key in st.session_state:
                del st.session_state[editor_key]

        if st.button("➕ 新建下一章"):
            new_id = structure[-1]['id'] + 1
            new_chapter = {
                "id": new_id, 
                "title": f"第{new_id}章：(待定)", 
                "outline": "请输入本章大纲...", 
                "summary": ""
            }
            structure.append(new_chapter)
            # 更新内存
            st.session_state['structure'] = structure
            # 异步写入硬盘 (这里为了安全还是同步写，但只写结构文件，很快)
            manager.save_structure(structure)
            st.rerun()

    # ================= 3. 主工作区 =================
    tab1, tab2 = st.tabs(["⚙️ 世界观设定", "✍️ 写作工作台"])

    with tab1:
        col_a, col_b = st.columns(2)
        with col_a:
            # 绑定 session_state，修改时直接更新内存
            new_world = st.text_area("世界观/力量体系", value=settings['world_view'], height=300, key="input_world")
        with col_b:
            new_chars = st.text_area("人物档案", value=settings['characters'], height=300, key="input_chars")
        
        if st.button("💾 保存设定"):
            # 更新内存
            settings['world_view'] = new_world
            settings['characters'] = new_chars
            st.session_state['settings'] = settings
            # 写入硬盘
            manager.save_settings(settings)
            st.success("设定已保存！")

    with tab2:
        st.subheader(f"正在编辑：{current_chapter['title']}")
        
        # 标题和大纲输入
        new_title = st.text_input("章节标题", value=current_chapter['title'])
        new_outline = st.text_area("本章细纲", value=current_chapter['outline'], height=100)
        
        prev_summary = "无（这是第一章）"
        if selected_idx > 0:
            prev_summary = structure[selected_idx - 1]['summary']
        
        with st.expander("查看上一章剧情摘要", expanded=False):
            st.info(prev_summary)

        col_gen, col_save = st.columns([1, 4])
        
        # --- 编辑器逻辑 (核心优化) ---
        editor_key = f"editor_{current_chapter['id']}"
        
        # 只有当内存里没有这个章节的内容时，才去读硬盘
        if editor_key not in st.session_state:
            # log(f"Cache Miss: 从硬盘读取章节 {current_chapter['id']}")
            disk_content = manager.load_chapter_content(current_chapter['id'])
            st.session_state[editor_key] = disk_content
        
        with col_gen:
            if st.button("🚀 生成/重写"):
                with st.spinner("AI 正在生成..."):
                    prompt = f"""
                    【世界观】
                    {settings['world_view']}
                    【人物】
                    {settings['characters']}
                    【前情提要】
                    {prev_summary}
                    【本章要求】
                    标题：{new_title}
                    大纲：{new_outline}
                    请撰写正文，2000字左右。
                    """
                    res = call_llm(prompt)
                    if res:
                        st.session_state[editor_key] = res
                        st.rerun()

        # 编辑器直接绑定 Session State
        final_content = st.text_area("正文内容", height=500, key=editor_key)
        
        # 实时字数 (现在只计算内存里的字符串，极快)
        current_len = len(final_content)
        st.caption(f"当前章节字数：{current_len} 字")

        with col_save:
            if st.button("💾 保存并更新摘要"):
                # 1. 计算字数差值，更新总字数 (避免重新扫描硬盘)
                old_len = len(manager.load_chapter_content(current_chapter['id'])) # 这里读一次硬盘没办法，为了准确
                diff = current_len - old_len
                st.session_state['total_words'] += diff

                # 2. 写入硬盘
                manager.save_chapter_content(current_chapter['id'], final_content)
                
                # 3. 更新大纲结构
                structure[selected_idx]['title'] = new_title
                structure[selected_idx]['outline'] = new_outline
                
                # 4. 生成摘要
                with st.spinner("生成摘要中..."):
                    summary = auto_summarize(final_content)
                    structure[selected_idx]['summary'] = summary
                
                # 5. 保存结构并更新内存
                manager.save_structure(structure)
                st.session_state['structure'] = structure
                
                st.success("保存成功！")
                time.sleep(1) # 给个视觉反馈
                st.rerun()

if __name__ == "__main__":
    main()