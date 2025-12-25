import streamlit as st
from openai import OpenAI
import json
import os

# 1. 配置部分 (就像 Header 文件)
# 建议去 DeepSeek 官网申请 Key，便宜且好用
API_KEY = "sk-1807d7a148974eaf9f68eed88b0b2322" 
BASE_URL = "https://api.deepseek.com"

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

# 2. 核心函数 (IP Core)
def call_llm(prompt, system_prompt="你是一个专业的网文作家"):
    """
    发送请求给大模型
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat", # 或者 deepseek-reasoner
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            stream=False
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# 3. 界面逻辑 (Main Function)
def main():
    st.set_page_config(page_title="AI 网文生成器", layout="wide")
    
    st.title("🚀 自动化网文生成控制台")

    # 侧边栏：全局设定 (Global Config)
    with st.sidebar:
        st.header("🌍 世界观设定")
        world_setting = st.text_area("输入世界观/力量体系", height=300, 
                                     value="主角：林风，修仙者。\n金手指：能看到万物的数据面板。")
    
    # 主界面：分两列
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📝 章节大纲输入")
        chapter_outline = st.text_area("本章大纲", height=150, 
                                       value="林风在坊市发现了一把生锈的铁剑，发现是上古神器。")
        
        st.subheader("⏮️ 上文摘要 (Context)")
        prev_summary = st.text_area("上一章发生了什么", height=100, 
                                    value="林风刚刚突破练气三层，出门历练。")

        if st.button("开始生成 (Run)"):
            with st.spinner("AI 正在疯狂码字中..."):
                # 拼装 Prompt (指令集)
                full_prompt = f"""
                【世界观设定】
                {world_setting}
                
                【前情提要】
                {prev_summary}
                
                【本章大纲】
                {chapter_outline}
                
                请根据以上信息，撰写本章正文，要求2000字左右，节奏紧凑。
                """
                
                # 调用函数
                result = call_llm(full_prompt)
                
                # 存入 Session State (临时寄存器)
                st.session_state['result'] = result

    with col2:
        st.subheader("📄 生成结果")
        if 'result' in st.session_state:
            st.text_area("正文内容", value=st.session_state['result'], height=600)
            st.download_button("下载为TXT", st.session_state['result'], "chapter.txt")

if __name__ == "__main__":
    main()