from nicegui import ui, run
import json
from .state import app_state, manager, ui_refs
from backend import CFG

# 临时存储生成的剧情卡片
generated_plots = []

def create_architect_ui():
    # 使用 full height column
    with ui.column().classes('w-full h-full p-4 gap-4'):
        
        # ================= 1. 顶部：推演控制台 =================
        with ui.card().classes('w-full p-4 bg-grey-1 border shrink-0'):
            with ui.row().classes('items-center gap-2 mb-2'):
                ui.icon('psychology', color='deep-purple', size='md')
                ui.label('剧情推演引擎 (Architect Pro)').classes('text-lg font-bold text-deep-purple')
                ui.label('· 基于 DeepSeek-R1').classes('text-xs text-grey-6 bg-white px-2 rounded border')

            ui.label('基于“全书梗概”和“世界观图谱”，推演未来的剧情细纲。').classes('text-xs text-grey-6 mb-2')
            
            with ui.row().classes('w-full items-start gap-4'):
                # --- 左侧：引导输入 ---
                guidance_input = ui.textarea(
                    label='剧情引导 / 你的期望',
                    placeholder='例如：主角到达京城，遭遇反派挑衅，准备打脸...（留空则由 AI 自由发挥）'
                ).classes('w-2/3').props('outlined bg-white')
                
                # --- 右侧：参数与启动 ---
                with ui.column().classes('w-1/3 gap-3'):
                    # 【修复】使用 Label + Slider 组合，解决显示 {} 的问题
                    with ui.column().classes('w-full gap-0'):
                        count_label = ui.label('生成章节数: 3').classes('text-sm font-bold text-purple-800')
                        chapter_count = ui.slider(min=1, max=10, value=3, step=1) \
                            .props('color=purple') \
                            .on_value_change(lambda e: count_label.set_text(f'生成章节数: {e.value}'))
                    
                    async def start_deduction():
                        if not CFG.get('api_key'):
                            ui.notify('请先配置 API Key', type='negative')
                            return
                        await run_plot_deduction(guidance_input.value, chapter_count.value)

                    ui.button('🚀 开始推演', on_click=start_deduction) \
                        .props('color=deep-purple icon=auto_awesome w-full size=lg') \
                        .classes('shadow-md')

        # ================= 2. 底部：推演结果 (卡片流) =================
        with ui.row().classes('w-full justify-between items-center mt-2'):
            ui.label('推演结果 (Result Cards)').classes('text-sm font-bold text-grey-7')
            ui.button('清空结果', on_click=lambda: ui_refs.get('architect_results').clear() if ui_refs.get('architect_results') else None) \
                .props('flat size=sm color=grey icon=delete_sweep')
        
        # 结果容器 (占满剩余高度，可滚动)
        results_container = ui.column().classes('w-full flex-grow overflow-auto gap-3 p-1')
        ui_refs['architect_results'] = results_container
        
        # 初始显示空状态
        with results_container:
            with ui.column().classes('w-full h-full items-center justify-center text-grey-4'):
                ui.icon('auto_stories', size='4rem')
                ui.label('暂无推演结果，请在上方输入引导并开始。').classes('text-lg mt-2')


async def run_plot_deduction(guidance, count):
    container = ui_refs.get('architect_results')
    if not container: return
    
    container.clear()
    with container:
        with ui.column().classes('w-full items-center mt-10'):
            ui.spinner('dots', size='3rem', color='purple')
            ui.label('DeepSeek 正在疯狂烧脑中...').classes('text-purple animate-pulse font-bold mt-2')
            ui.label('正在读取世界观、回顾前文摘要、构建逻辑链...').classes('text-xs text-grey')
    
    # 1. 准备 Context
    summary = app_state.settings.get('book_summary', '暂无全书总结')
    world = app_state.settings.get('world_view', '暂无世界观')
    
    # 2. 构造 Prompt (强制 JSON 输出)
    prompt = f"""
    【任务】
    你是一个网文剧情架构师。请基于以下背景，推演接下来的 {count} 个章节的大纲。
    
    【世界观】
    {world[:800]}...
    
    【目前剧情进度】
    {summary}
    
    【作者的引导/期望】
    {guidance}
    
    【要求】
    1. 剧情要有起承转合，符合网文爽点节奏。
    2. 必须严格按照 JSON 格式返回一个列表，不要Markdown标记，不要废话。
    3. 格式示例：
    [
        {{"title": "第X章 遭遇埋伏", "summary": "主角在...", "pacing": "铺垫", "conflict": "敌强我弱"}},
        {{"title": "第X章 绝地反击", "summary": "主角使用...", "pacing": "高潮", "conflict": "反杀"}}
    ]
    """
    
    # 3. 调用 LLM
    try:
        # 使用 architect 模型 (建议配置为 deepseek-reasoner)
        response_text = await run.io_bound(manager.sync_call_llm, prompt, "你是一个只输出JSON的剧情架构师。", "architect")
        
        # 清洗数据 (防止 DeepSeek 输出 ```json ... ```)
        clean_text = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        
        # 4. 渲染卡片
        container.clear()
        with container:
            if not isinstance(data, list):
                ui.label(f"格式解析错误: {response_text[:100]}...").classes('text-red')
                return

            for i, chap in enumerate(data):
                # 每一章的卡片
                with ui.card().classes('w-full bg-white border-l-4 border-purple-500 shadow-sm hover:shadow-md transition-shadow'):
                    with ui.row().classes('w-full justify-between items-start'):
                        # --- 左侧：信息展示 ---
                        with ui.column().classes('gap-1 flex-grow pr-4'):
                            with ui.row().classes('items-center gap-2'):
                                ui.label(chap.get('title', f'新章节')).classes('text-lg font-bold text-grey-9')
                                
                                # 节奏标签
                                pacing = chap.get('pacing', '正常')
                                color_map = {'高潮': 'red', '爽点': 'orange', '铺垫': 'blue', '日常': 'green'}
                                tag_color = color_map.get(pacing, 'blue')
                                ui.badge(pacing, color=tag_color).props('outline')
                            
                            # 冲突点
                            ui.label(f"⚔️ 核心冲突: {chap.get('conflict', '无')}").classes('text-xs text-red-600 font-bold bg-red-50 px-1 rounded self-start')
                            
                            # 摘要内容
                            with ui.expansion('查看详细细纲', icon='article', value=True).classes('w-full text-grey-8').props('dense header-class="text-sm"'):
                                ui.markdown(chap.get('summary', '')).classes('text-sm leading-relaxed p-2 bg-grey-1 rounded')
                        
                        # --- 右侧：采纳按钮 ---
                        def adopt_chapter(c=chap):
                            try:
                                # 1. 确定 Volume ID (如果未设置，默认取最后一个分卷，或者第一卷)
                                target_vol_id = getattr(app_state, 'current_volume_id', 1)
                                if not app_state.volumes:
                                    ui.notify('请先至少创建一个分卷！', type='negative')
                                    return
                                    
                                # 智能查找：如果当前没有选中的卷，就放到最后一卷
                                if target_vol_id not in [v['id'] for v in app_state.volumes]:
                                    target_vol_id = app_state.volumes[-1]['id']

                                # 2. 创建数据
                                new_id = len(app_state.structure) + 1
                                new_chap = {
                                    "id": new_id,
                                    "title": c.get('title', '新章节'),
                                    "volume_id": target_vol_id,
                                    "content": "",
                                    "outline": c.get('summary', '') # 自动填入大纲
                                }
                                app_state.structure.append(new_chap)
                                manager.save_structure(app_state.structure)
                                
                                # 3. 刷新左侧目录
                                if hasattr(app_state, 'refresh_sidebar'): 
                                    app_state.refresh_sidebar()
                                
                                ui.notify(f"✅ 已创建: {c['title']}", type='positive')
                            except Exception as ex:
                                ui.notify(f"创建失败: {ex}", type='negative')

                        with ui.column().classes('items-center justify-center min-h-[80px] border-l pl-4'):
                            ui.button('采纳', icon='add_circle', on_click=adopt_chapter) \
                                .props('flat color=green size=md stack') \
                                .tooltip('直接生成到目录树')

    except Exception as e:
        container.clear()
        with container:
            with ui.card().classes('w-full bg-red-50 border-red'):
                ui.label(f"💥 推演过程中发生错误").classes('text-red font-bold')
                ui.label(str(e)).classes('text-xs text-red-800')
                with ui.expansion('查看原始返回'):
                    ui.code(response_text if 'response_text' in locals() else 'No response').classes('text-xs')

# 兼容接口 (防止 main.py 旧代码报错)
def run_architect(theme, slider):
    pass