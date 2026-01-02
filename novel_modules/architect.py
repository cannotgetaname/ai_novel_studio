from nicegui import ui, run
import json
import backend
from .state import app_state, manager, ui_refs
from backend import CFG
import uuid

def create_architect_ui():
    # 使用 Splitter，设定更舒适的默认比例
    with ui.splitter(value=22, limits=(15, 40)).classes('w-full h-full bg-gray-50') as splitter:
        
        # --- 拖拽条样式优化 (更隐形但易用) ---
        with splitter.separator:
            with ui.column().classes('w-1 h-full bg-gray-200 hover:bg-purple-400 transition-colors cursor-col-resize items-center justify-center'):
                # 只有鼠标悬停或拖拽时才明显，平时像一条淡淡的分界线
                pass 

        # ================= 🌲 左侧：导航树 (侧边栏风格) =================
        with splitter.before:
            with ui.column().classes('w-full h-full p-3 bg-white border-r border-gray-200 overflow-auto'):
                # 顶部标题栏
                with ui.row().classes('items-center justify-between w-full mb-4 px-1'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('account_tree', color='purple').classes('text-lg')
                        ui.label('结构视图').classes('text-sm font-bold text-gray-800')
                    
                    ui.button(icon='refresh', on_click=lambda: refresh_tree()) \
                        .props('flat round dense color=grey size=sm').tooltip('刷新结构')

                # 树容器
                tree_container = ui.element('div').classes('w-full')
                
                def refresh_tree():
                    tree_container.clear()
                    data = manager.get_novel_tree(app_state)
                    
                    # --- 辅助函数：递归获取所有节点 ID ---
                    def get_all_ids(nodes):
                        ids = []
                        for node in nodes:
                            ids.append(node['id'])
                            if node.get('children'):
                                ids.extend(get_all_ids(node['children']))
                        return ids

                    with tree_container:
                        # 1. 创建树组件
                        tree = ui.tree(data, label_key='label', on_select=lambda e: update_panel(e.value)) \
                            .props('node-key="id" tick-strategy="none" selected-color="purple"') \
                            .classes('text-gray-700')
                        
                        # 2. 【关键修复】手动调用 expand() 展开所有节点
                        # NiceGUI 的 expand() 需要传入节点 ID 列表
                        all_ids = get_all_ids(data)
                        tree.expand(all_ids)
                            
                refresh_tree()

        # ================= 🎛️ 右侧：操作控制台 (现代化卡片风格) =================
        with splitter.after:
            # 背景色设为极淡的灰色，突出中间的白色卡片
            panel_container = ui.column().classes('w-full h-full p-6 overflow-auto bg-gray-50')
            
            with panel_container:
                render_empty_state()

            async def update_panel(node_id):
                if not node_id: return
                
                panel_container.clear()
                node_type, ctx, raw_data = manager.get_node_context(node_id, app_state)
                
                with panel_container:
                    # 1. 顶部大标题 (Header)
                    with ui.row().classes('items-center gap-3 mb-6 shrink-0 w-full'):
                        # 图标容器
                        icon_bg_map = {'root': 'bg-blue-100', 'volume': 'bg-purple-100', 'chapter': 'bg-green-100'}
                        icon_color_map = {'root': 'text-blue-600', 'volume': 'text-purple-600', 'chapter': 'text-green-600'}
                        icon_map = {'root': 'menu_book', 'volume': 'inventory_2', 'chapter': 'article'}
                        
                        bg_class = icon_bg_map.get(node_type, 'bg-gray-100')
                        text_class = icon_color_map.get(node_type, 'text-gray-600')
                        
                        with ui.element('div').classes(f'p-3 rounded-xl {bg_class} shadow-sm'):
                            ui.icon(icon_map.get(node_type, 'help')).classes(f'text-2xl {text_class}')
                        
                        with ui.column().classes('gap-0'):
                            type_map = {'root': '全书规划 (Root)', 'volume': '分卷拆解 (Volume)', 'chapter': '场景细化 (Chapter)'}
                            ui.label(type_map.get(node_type, node_type)).classes('text-xs font-bold text-gray-500 uppercase tracking-wide')
                            
                            title = raw_data.get('title', '未命名') if isinstance(raw_data, dict) else '全书总览'
                            ui.label(title).classes('text-2xl font-bold text-gray-900 leading-tight')

                    # 2. 档案卡 (Info Card) - 【修复：自然展开，去除滚动条】
                    with ui.card().classes('w-full bg-white border border-gray-100 shadow-sm rounded-xl p-6 mb-8'):
                        with ui.row().classes('items-center gap-2 mb-3 border-b border-gray-100 pb-2'):
                            ui.icon('info', size='xs', color='blue-500')
                            ui.label('当前节点档案').classes('text-sm font-bold text-gray-700')
                        
                        # 核心内容：自然文本，无边框，易读
                        ui.markdown(ctx.get('self_info', '数据加载异常')).classes('text-base text-gray-800 leading-7 prose max-w-none')
                        
                        # 上下文：用引用块样式
                        if ctx['parent_info']:
                            with ui.element('div').classes('mt-4 p-3 bg-gray-50 rounded-lg border-l-4 border-blue-300'):
                                ui.label('📌 上下文 / 上级目标').classes('text-xs font-bold text-gray-500 mb-1')
                                ui.markdown(ctx['parent_info']).classes('text-sm text-gray-600 italic leading-relaxed')

                    # 3. 操作区 (Action Area)
                    # 增加分割标题
                    with ui.row().classes('items-center gap-2 mb-4 w-full'):
                        ui.icon('auto_awesome', color='purple').classes('text-lg')
                        ui.label('AI 剧情推演').classes('text-lg font-bold text-gray-800')
                        ui.element('div').classes('h-px bg-gray-200 flex-grow ml-2')

                    if node_type == 'root':
                        render_root_actions(ctx)
                    elif node_type == 'volume':
                        render_volume_actions(ctx, raw_data)
                    elif node_type == 'chapter':
                        render_chapter_actions(ctx, raw_data)

def render_empty_state():
    with ui.column().classes('w-full h-full items-center justify-center text-gray-400'):
        with ui.element('div').classes('p-6 bg-white rounded-full shadow-sm mb-4'):
             ui.icon('account_tree', size='4rem', color='gray-300')
        ui.label('请在左侧选择一个节点').classes('text-xl font-bold text-gray-600')
        ui.label('点击结构树，开始您的分形创作之旅').classes('text-sm text-gray-400')

# ================= 🎮 操作面板 (样式升级) =================

def render_root_actions(ctx):
    # 使用白色大卡片包裹操作区
    with ui.card().classes('w-full bg-white shadow-md rounded-xl p-6 gap-6'):
        # 左右布局：左侧输入，右侧参数
        with ui.row().classes('w-full gap-8 items-start no-wrap'):
            # 左侧
            with ui.column().classes('flex-grow gap-2'):
                ui.label('核心构思 / 引导').classes('text-sm font-bold text-gray-700')
                guidance = ui.textarea(placeholder='例如：主角从地球穿越，每隔100章飞升一次...').classes('w-full').props('outlined rows=6')
                ui.label('越详细的引导，生成的骨架越精准。').classes('text-xs text-gray-400')

            # 右侧参数栏
            with ui.column().classes('w-1/3 gap-6 min-w-[250px] bg-gray-50 p-4 rounded-lg border border-gray-100'):
                # 模板选择
                ui.label('📚 叙事模型').classes('text-xs font-bold text-gray-500')
                template = ui.select(
                    ['网文升级流 (换地图)', '英雄之旅 (12步)', '救猫咪 (15节拍)', '无限流 (单元剧)', '三段式 (起承转合)'], 
                    value='网文升级流 (换地图)'
                ).classes('w-full').props('outlined dense bg-white')
                
                # 滑块
                ui.separator().classes('bg-gray-200')
                with ui.column().classes('w-full gap-1'):
                     with ui.row().classes('justify-between w-full'):
                        ui.label('分卷数量').classes('text-xs font-bold text-gray-500')
                        count_label = ui.label('5 卷').classes('text-xs font-bold text-purple-600')
                     
                     vol_count = ui.slider(min=3, max=20, value=5, step=1).props('color=purple label-always') \
                        .on_value_change(lambda e: count_label.set_text(f'{e.value} 卷'))

        # 底部大按钮
        async def do_plan():
            print("\n>>> [DEBUG] 1. '生成分卷'按钮被点击") # <--- DEBUG
            
            # 1. 检查 API Key
            api_key = CFG.get('api_key')
            if not api_key:
                print(">>> [ERROR] API Key 未配置！")
                ui.notify('请先在系统配置中填写 API Key', type='negative')
                return
            print(f">>> [DEBUG] 2. API Key 检查通过: {api_key[:4]}***")

            # 2. 构建 Prompt
            prompt = f"""
            你是一个网文主编。请基于以下信息，为全书规划 {vol_count.value} 个左右的【分卷 (Volumes)】。
            【全书核心】{ctx.get('self_info', '')}
            【用户引导】{guidance.value}
            【采用模型】{template.value}
            要求：JSON格式列表，包含 title, desc。
            """
            print(f">>> [DEBUG] 3. Prompt 构建完成 (长度: {len(prompt)})")
            
            # 3. 调用执行函数
            try:
                print(">>> [DEBUG] 4. 准备调用 call_ai_and_preview...")
                await call_ai_and_preview(prompt, 'create_volumes')
                print(">>> [DEBUG] 5. call_ai_and_preview 调用结束")
            except Exception as e:
                import traceback
                print(f">>> [FATAL ERROR] do_plan 执行崩溃: {e}")
                traceback.print_exc()

        ui.button('生成全书分卷骨架', icon='auto_awesome', on_click=do_plan) \
            .props('unelevated size=lg color=deep-purple') \
            .classes('w-full shadow-lg hover:shadow-xl transition-shadow rounded-lg font-bold text-lg')

def render_volume_actions(ctx, vol_data):
    with ui.card().classes('w-full bg-white shadow-md rounded-xl p-6 gap-6'):
        with ui.row().classes('w-full gap-8 items-start no-wrap'):
            # 左侧引导
            with ui.column().classes('flex-grow gap-2'):
                ui.label('本卷剧情走向').classes('text-sm font-bold text-gray-700')
                guidance = ui.textarea(placeholder='例如：主角刚进入宗门，被师兄刁难...').classes('w-full').props('outlined rows=6')

            # 右侧参数
            with ui.column().classes('w-1/3 gap-5 min-w-[250px] bg-gray-50 p-4 rounded-lg border border-gray-100'):
                ui.label('🎭 风格与节奏').classes('text-xs font-bold text-gray-500')
                template = ui.select(['爽文打脸流', '三幕式结构', '悬疑解谜流', '日常种田流'], value='爽文打脸流').classes('w-full').props('outlined dense bg-white')
                
                ui.label('📄 预计章节数').classes('text-xs font-bold text-gray-500 mt-2')
                count = ui.number(value=15, min=1, max=100).classes('w-full').props('outlined dense bg-white suffix="章"')
        
        async def do_plan():
            prompt = f"""
            你是一个网文架构师。请将【{vol_data['title']}】拆解为 {int(count.value)} 个左右的章节。
            【本卷目标】{ctx['self_info']}
            【用户引导】{guidance.value}
            【风格模型】{template.value}
            要求：JSON格式列表，包含 title, outline。
            """
            await call_ai_and_preview(prompt, 'create_chapters', parent_id=vol_data['id'])
            
        ui.button('推演本卷章节细纲', icon='psychology', on_click=do_plan) \
            .props('unelevated size=lg color=purple') \
            .classes('w-full shadow-lg hover:shadow-xl transition-shadow rounded-lg font-bold')

def render_chapter_actions(ctx, chap_data):
    with ui.card().classes('w-full bg-white shadow-md rounded-xl p-6 gap-6'):
        with ui.row().classes('w-full gap-8 items-start no-wrap'):
            with ui.column().classes('flex-grow gap-2'):
                ui.label('本章具体构思').classes('text-sm font-bold text-gray-700')
                guidance = ui.textarea(value=chap_data.get('outline', ''), placeholder='如果大纲为空，请先补充...').classes('w-full').props('outlined rows=6')

            with ui.column().classes('w-1/3 gap-4 min-w-[250px] bg-gray-50 p-4 rounded-lg border border-gray-100'):
                with ui.row().classes('justify-between w-full'):
                    ui.label('场景切分 (Beats)').classes('text-xs font-bold text-gray-500')
                    scene_label = ui.label('4 个').classes('text-xs font-bold text-indigo-600')
                
                scene_count = ui.slider(min=2, max=8, value=4, step=1).props('color=indigo label-always') \
                    .on_value_change(lambda e: scene_label.set_text(f'{e.value} 个'))
                
                ui.label('提示：场景是写作的最小单位，包含地点、人物和冲突。').classes('text-xs text-gray-400 italic leading-tight')

        async def do_plan():
            prompt = f"""
            微观剧情设计：将【{chap_data['title']}】拆解为 {scene_count.value} 个具体的【场景】。
            【本章大纲】{guidance.value}
            【上级分卷】{ctx['parent_info']}
            要求：JSON格式列表，包含 scene, desc, est_words。
            """
            await call_ai_and_preview(prompt, 'update_outline', target_chap=chap_data)
            
        ui.button('生成场景流 (Beat Sheet)', icon='movie_filter', on_click=do_plan) \
            .props('unelevated size=lg color=indigo') \
            .classes('w-full shadow-lg hover:shadow-xl transition-shadow rounded-lg font-bold')

# ================= ⚡ 预览窗口 (AI Result) =================

async def call_ai_and_preview(prompt, action_type, **kwargs):
    print(f">>> [DEBUG] A. 进入 call_ai_and_preview (Type: {action_type})")

    result_area = ui.dialog().classes('backdrop-blur-sm')
    
    # 弹窗本体
    with result_area, ui.card().classes('w-3/4 h-5/6 flex flex-col rounded-2xl shadow-2xl p-0 overflow-hidden'):
        
        # 1. 顶部 Header
        with ui.row().classes('w-full items-center justify-between bg-gray-900 text-white p-4 shrink-0'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('smart_toy', color='purple-300')
                ui.label('AI 推演结果').classes('text-lg font-bold')
            ui.button(icon='close', on_click=result_area.close).props('flat round dense color=white')
            
        # 2. 内容容器 (关键：这里只定义容器，不预先创建内部元素)
        content_wrapper = ui.column().classes('w-full flex-grow relative bg-gray-50')
        
        # 3. 初始显示 Loading
        with content_wrapper:
            with ui.column().classes('absolute-center items-center gap-4'):
                ui.spinner('dots', size='4rem', color='purple')
                ui.label('DeepSeek 正在疯狂烧脑中...').classes('text-purple-600 font-bold animate-pulse')

        result_area.open()
        
        try:
            print(">>> [DEBUG] C. 请求后端 LLM...")
            # 调用后端
            res = await run.io_bound(backend.sync_call_llm, prompt, "你是一个只输出JSON的架构师。", "architect")
            print(f">>> [DEBUG] D. 后端返回: {len(res)} chars")
            
            # JSON 解析
            clean_json = res.replace("```json", "").replace("```", "").strip()
            start, end = clean_json.find('['), clean_json.rfind(']')
            if start != -1 and end != -1: clean_json = clean_json[start:end+1]
            data = json.loads(clean_json)
            
            print(f">>> [DEBUG] F. 解析成功: {len(data)} 条")

            # ==========================================
            # 【核心修复】直接清空容器，从头绘制结果
            # ==========================================
            content_wrapper.clear() 
            
            with content_wrapper:
                # 重新创建一个占满空间的 Scroll Area
                with ui.scroll_area().classes('w-full h-full p-6'):
                    
                    ui.label(f'🎉 推演成功！生成 {len(data)} 条结果').classes('text-green-600 font-bold text-lg mb-4')
                    
                    # --- 渲染逻辑 (保持不变) ---
                    if action_type == 'create_volumes':
                        with ui.column().classes('gap-4 w-full'):
                            for item in data:
                                with ui.card().classes('w-full bg-white p-4 border-l-4 border-purple-500 shadow-sm'):
                                    ui.label(item.get('title', '无标题')).classes('font-bold text-lg text-gray-800')
                                    ui.markdown(item.get('desc', '')).classes('text-sm text-gray-600 mt-1')
                        
                        def apply_vols():
                            print(">>> [DEBUG] 用户点击了'采纳分卷'")
                            
                            # 【修复前】错误代码: start_id = max([v['id']...]) + 1
                            # 【修复后】使用 UUID 生成不重复的字符串 ID
                            
                            # 1. 计算当前的排序顺位 (order)
                            current_max_order = max([v.get('order', 0) for v in app_state.volumes] or [0])
                            
                            for i, item in enumerate(data):
                                # 生成类似 'vol_a1b2c3d4' 的唯一ID
                                new_vol_id = f"vol_{str(uuid.uuid4())[:8]}"
                                
                                app_state.volumes.append({
                                    "id": new_vol_id, 
                                    "title": item.get('title', '新分卷'), 
                                    "desc": item.get('desc', ''),
                                    "order": current_max_order + 1 + i # 维护排序
                                })
                                
                            manager.save_volumes(app_state.volumes)
                            ui.notify('分卷已创建！', type='positive')
                            
                            if hasattr(app_state, 'refresh_sidebar') and app_state.refresh_sidebar:
                                app_state.refresh_sidebar()
                            result_area.close()
                        
                        ui.separator().classes('my-6')
                        ui.button('✨ 采纳并创建分卷', on_click=apply_vols).props('unelevated size=lg color=green').classes('w-full font-bold shadow-md')

                    elif action_type == 'create_chapters':
                        with ui.column().classes('gap-3 w-full'):
                            for item in data:
                                with ui.card().classes('w-full bg-white p-3 border border-gray-200 shadow-sm hover:shadow-md transition-shadow'):
                                    with ui.row().classes('items-center gap-2'):
                                        ui.icon('article', color='purple-400')
                                        ui.label(item.get('title', '无标题')).classes('font-bold text-gray-800')
                                    ui.markdown(item.get('outline', '')).classes('text-sm text-gray-600 mt-1 pl-6')

                        def apply_chaps():
                            print(">>> [DEBUG] 用户点击了'采纳章节'")
                        
                            # 【优化】取当前最大ID + 1，防止 ID 冲突
                            current_max_id = max([c['id'] for c in app_state.structure] or [0])
                            start_id = current_max_id + 1
                            
                            vol_id = kwargs.get('parent_id')
                            # 如果没有指定父卷，默认放入最后一卷
                            if not vol_id and app_state.volumes:
                                vol_id = app_state.volumes[-1]['id']

                            for i, item in enumerate(data):
                                app_state.structure.append({
                                    "id": start_id + i, 
                                    "title": item.get('title', f'第{start_id+i}章'), 
                                    "volume_id": vol_id, 
                                    "content": "", 
                                    "outline": item.get('outline', '')
                                })
                                
                            manager.save_structure(app_state.structure)
                            ui.notify('章节已创建！', type='positive')
                            
                            if hasattr(app_state, 'refresh_sidebar') and app_state.refresh_sidebar:
                                app_state.refresh_sidebar()
                            result_area.close()

                        ui.separator().classes('my-6')
                        ui.button('✨ 采纳并创建章节', on_click=apply_chaps).props('unelevated size=lg color=green').classes('w-full font-bold shadow-md')

                    elif action_type == 'update_outline':
                        with ui.column().classes('gap-4 w-full'):
                            for item in data:
                                 with ui.card().classes('w-full bg-white p-4 border-l-4 border-indigo-500 shadow-sm'):
                                     with ui.row().classes('justify-between w-full'):
                                         ui.label(item.get('scene', '场景')).classes('font-bold text-indigo-700')
                                         ui.badge(item.get('est_words', '未知字数'), color='indigo-100').classes('text-indigo-800')
                                     ui.markdown(item.get('desc', '')).classes('text-sm text-gray-700 mt-2 leading-relaxed')

                        preview_text = "".join([f"### {item.get('scene', '场景')}\n_{item.get('est_words', '未知字数')}_\n\n{item.get('desc', '')}\n\n" for item in data])
                        
                        def apply_scenes():
                            target_chap = kwargs.get('target_chap')
                            if target_chap:
                                original = target_chap.get('outline', '')
                                target_chap['outline'] = (original + ("\n\n---\n\n" if original else "") + preview_text)
                                manager.save_structure(app_state.structure)
                                ui.notify('场景流已写入大纲！', type='positive')
                            result_area.close()

                        ui.separator().classes('my-6')
                        ui.button('✨ 写入章节大纲', on_click=apply_scenes).props('unelevated size=lg color=green').classes('w-full font-bold shadow-md')

        except Exception as e:
            import traceback
            traceback.print_exc()
            
            # 出错时也直接清空重绘
            content_wrapper.clear()
            with content_wrapper:
                with ui.column().classes('w-full h-full items-center justify-center bg-red-50 p-6'):
                    ui.icon('error_outline', size='4rem', color='red-400')
                    ui.label('推演失败').classes('text-xl font-bold text-red-700 mt-2')
                    ui.label(str(e)).classes('text-red-500 mt-2 text-center')
                    with ui.expansion('原始数据'):
                        ui.code(res if 'res' in locals() else 'No response').classes('text-xs')

def run_architect(theme, slider): pass