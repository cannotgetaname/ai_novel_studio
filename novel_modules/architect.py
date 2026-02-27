from nicegui import ui, run
import json
import backend
from .state import app_state, manager, ui_refs
from backend import CFG
import uuid

# ================= 🌀 裂变类型定义 =================
FISSION_TYPES = {
    "time_based": {
        "name": "时间裂变",
        "icon": "schedule",
        "color": "blue",
        "description": "按时间顺序拆分为多个阶段"
    },
    "space_based": {
        "name": "空间裂变",
        "icon": "place",
        "color": "green",
        "description": "按空间位置拆分为多个场景"
    },
    "character_based": {
        "name": "人物裂变",
        "icon": "people",
        "color": "purple",
        "description": "从剧情中提取人物支线"
    },
    "conflict_based": {
        "name": "冲突裂变",
        "icon": "flash_on",
        "color": "red",
        "description": "将主要冲突拆分为多个回合"
    },
    "standard": {
        "name": "标准裂变",
        "icon": "account_tree",
        "color": "grey",
        "description": "通用剧情拆分"
    }
}

# ================= 📊 节点状态定义 =================
NODE_STATUS = {
    "planned": {"name": "规划中", "icon": "edit_note", "color": "gray", "badge": "📝"},
    "writing": {"name": "写作中", "icon": "edit", "color": "blue", "badge": "✍️"},
    "done": {"name": "已完成", "icon": "check_circle", "color": "green", "badge": "✅"},
    "review": {"name": "待审核", "icon": "rate_review", "color": "orange", "badge": "🔍"},
    "hold": {"name": "暂缓", "icon": "pause_circle", "color": "red", "badge": "⏸️"}
}

# 节点状态存储（内存中，会话级别）
node_status_store = {}

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
                    
                    with ui.row().classes('items-center gap-1'):
                        ui.button(icon='refresh', on_click=lambda: refresh_tree()) \
                            .props('flat round dense color=grey size=sm').tooltip('刷新结构')
                        
                        # 更多操作菜单
                        with ui.menu().props('anchor=bottom-end') as more_menu:
                            async def export_architecture():
                                """导出架构为JSON文件"""
                                data = manager.get_novel_tree(app_state)
                                json_str = json.dumps(data, ensure_ascii=False, indent=2)
                                ui.download(json_str.encode('utf-8'), 'novel_architecture.json')
                                ui.notify('架构已导出为JSON文件', type='positive')
                                more_menu.close()
                            
                            ui.item('📤 导出架构为JSON', on_click=export_architecture).props('dense')
                            
                            async def import_architecture():
                                """从JSON文件导入架构"""
                                # 注意：这是一个概念实现，实际项目中需要更完整的导入逻辑
                                ui.notify('导入功能开发中...', type='info')
                                more_menu.close()
                            
                            ui.item('📥 从JSON导入架构', on_click=import_architecture).props('dense')
                            
                            ui.separator()
                            
                            ui.item('📊 生成架构报告', on_click=lambda: ui.notify('报告功能开发中...', type='info')).props('dense')
                            
                            ui.item('🔄 重置所有状态', on_click=lambda: [node_status_store.clear(), refresh_tree(), ui.notify('状态已重置', type='info')]).props('dense')
                        
                        ui.button(icon='more_vert', on_click=more_menu.open) \
                            .props('flat round dense color=grey size=sm').tooltip('更多操作')
                
                # 状态筛选工具栏
                with ui.row().classes('w-full gap-1 mb-2 px-1'):
                    # 全选按钮
                    ui.button('全部', on_click=lambda: filter_by_status('all')) \
                        .props('flat size=sm color=grey').classes('text-xs')
                    
                    # 状态筛选按钮
                    for status_key, status_info in NODE_STATUS.items():
                        def make_status_handler(key=status_key):
                            return lambda: filter_by_status(key)
                        ui.button(status_info['badge'], on_click=make_status_handler()) \
                            .props(f'flat size=sm color={status_info["color"]}').classes('text-xs')
                    
                    # 状态图例说明
                    with ui.menu().props('anchor=bottom-end') as status_menu:
                        ui.item('📝 规划中：尚未开始写作').props('dense')
                        ui.item('✍️ 写作中：正在创作中').props('dense')
                        ui.item('✅ 已完成：内容已基本完成').props('dense')
                        ui.item('🔍 待审核：需要审稿或修改').props('dense')
                        ui.item('⏸️ 暂缓：暂时搁置').props('dense')
                    
                    ui.button(icon='help', on_click=status_menu.open).props('flat round dense size=sm color=grey').tooltip('状态说明')

                # 树容器
                tree_container = ui.element('div').classes('w-full')
                
                # 状态筛选函数
                def filter_by_status(status_key):
                    """按状态筛选节点"""
                    # 由于NiceGUI树组件不支持动态筛选，我们这里实现一个简单的视觉提示
                    # 实际项目中可能需要更复杂的实现
                    ui.notify(f'筛选状态: {NODE_STATUS.get(status_key, {"name": "全部"})["name"]}', type='info')
                
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
                    
                    # --- 辅助函数：为节点添加状态标记 ---
                    def enhance_node_with_status(node):
                        """为树节点添加状态标记"""
                        node_id = node['id']
                        node_type = None
                        raw_data = node.get('_raw', {})
                        
                        # 首先检查状态存储中是否有手动设置的状态
                        if node_id in node_status_store:
                            status = node_status_store[node_id]
                        else:
                            # 自动判断状态
                            if node_id == 'root':
                                node_type = 'root'
                                status = 'planned'  # 根节点总是规划中
                            elif 'vol_' in node_id:
                                node_type = 'volume'
                                # 分卷状态：检查其下章节状态
                                chapter_statuses = []
                                for child in node.get('children', []):
                                    if 'status' in child:
                                        chapter_statuses.append(child['status'])
                                
                                if not chapter_statuses:
                                    status = 'planned'
                                elif 'writing' in chapter_statuses or 'done' in chapter_statuses:
                                    status = 'writing'
                                else:
                                    status = 'planned'
                            elif 'chap_' in node_id:
                                node_type = 'chapter'
                                # 章节状态：检查是否有内容
                                chap_id = node_id.replace('chap_', '', 1)
                                try:
                                    content = manager.load_chapter_content(int(chap_id))
                                    if len(content) > 1000:
                                        status = 'done'
                                    elif len(content) > 100:
                                        status = 'writing'
                                    else:
                                        status = 'planned'
                                except:
                                    status = 'planned'
                            else:
                                status = 'planned'
                        
                        # 添加状态信息
                        status_info = NODE_STATUS.get(status, NODE_STATUS['planned'])
                        node['status'] = status
                        node['status_badge'] = status_info['badge']
                        node['status_color'] = status_info['color']
                        
                        # 修改标签，添加状态标记
                        original_label = node['label']
                        node['label'] = f"{status_info['badge']} {original_label}"
                        
                        # 递归处理子节点
                        if node.get('children'):
                            for child in node['children']:
                                enhance_node_with_status(child)
                        
                        return node
                    
                    # 增强所有节点
                    enhanced_data = []
                    for node in data:
                        enhanced_data.append(enhance_node_with_status(node))

                    with tree_container:
                        # 1. 创建树组件
                        tree = ui.tree(enhanced_data, label_key='label', on_select=lambda e: update_panel(e.value)) \
                            .props('node-key="id" tick-strategy="none" selected-color="purple"') \
                            .classes('text-gray-700')
                        
                        # 2. 【关键修复】手动调用 expand() 展开所有节点
                        # NiceGUI 的 expand() 需要传入节点 ID 列表
                        all_ids = get_all_ids(enhanced_data)
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
                        with ui.row().classes('items-center justify-between mb-3 border-b border-gray-100 pb-2'):
                            with ui.row().classes('items-center gap-2'):
                                ui.icon('info', size='xs', color='blue-500')
                                ui.label('当前节点档案').classes('text-sm font-bold text-gray-700')
                            
                            # 节点状态显示与编辑
                            if node_type in ['volume', 'chapter']:
                                # 获取当前状态
                                current_status = node_status_store.get(node_id, 'planned')
                                status_info = NODE_STATUS.get(current_status, NODE_STATUS['planned'])
                                status_badge = status_info['badge']
                                status_color = status_info['color']
                                
                                # with ui.menu().props('anchor=bottom-end') as status_edit_menu:
                                #     for status_key, status_info in NODE_STATUS.items():
                                #         # 捕获循环变量的当前值
                                #         current_status_key = status_key
                                #         current_status_info = status_info
                                        
                                #         async def change_status(s=current_status_key, info=current_status_info):
                                #             # 保存状态到内存存储
                                #             node_status_store[node_id] = s
                                #             ui.notify(f'状态已更改为: {info["name"]}', type='info')
                                #             # 刷新树和面板
                                #             refresh_tree()
                                #             await update_panel(node_id)
                                #             status_edit_menu.close()
                                        
                                #         ui.item(f"{current_status_info['badge']} {current_status_info['name']}", 
                                #                on_click=change_status).props('dense')
                                
                                # ui.button(f"{status_badge} {status_info['name']}", 
                                #          on_click=status_edit_menu.open) \
                                #     .props(f'flat size=sm color={status_color}').classes('text-xs')
                                
                                # 1. 先用 with 定义按钮容器 (注意把原来的 on_click 删掉了，框架会自动绑定内部的 menu)
                                with ui.button(f"{status_badge} {status_info['name']}") \
                                        .props(f'flat size=sm color={status_color}').classes('text-xs'):
                                    
                                    # 2. 将 menu 直接嵌套在按钮内部
                                    with ui.menu().props('anchor=top-end') as status_edit_menu:
                                        for status_key, status_info in NODE_STATUS.items():
                                            # 捕获循环变量的当前值
                                            current_status_key = status_key
                                            current_status_info = status_info
                                            
                                            async def change_status(s=current_status_key, info=current_status_info):
                                                # 保存状态到内存存储
                                                node_status_store[node_id] = s
                                                ui.notify(f'状态已更改为: {info["name"]}', type='info')
                                                # 刷新树和面板
                                                refresh_tree()
                                                await update_panel(node_id)
                                                # status_edit_menu.close() # 嵌套后，点击通常会自动关闭，这行可有可无
                                            
                                            ui.menu_item(f"{current_status_info['badge']} {current_status_info['name']}", 
                                                   on_click=change_status).props('dense')
                        
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
                # 🌀 裂变类型选择
                ui.label('🌀 裂变策略').classes('text-xs font-bold text-gray-500')
                fission_options = {k: f"{v['name']} - {v['description']}" for k, v in FISSION_TYPES.items()}
                fission_type = ui.select(fission_options, value='standard').classes('w-full').props('outlined dense bg-white')

                # 模板选择
                ui.label('📚 叙事模型').classes('text-xs font-bold text-gray-500 mt-2')
                template = ui.select(
                    ['网文升级流 (换地图)', '英雄之旅 (12步)', '救猫咪 (15节拍)', '无限流 (单元剧)', '三段式 (起承转合)'],
                    value='网文升级流 (换地图)'
                ).classes('w-full').props('outlined dense bg-white')

                # 滑块
                ui.separator().classes('bg-gray-200 mt-2')
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

            # 2. 根据裂变类型构建不同的Prompt
            fission_info = FISSION_TYPES.get(fission_type.value, FISSION_TYPES['standard'])

            prompt = f"""
            你是一个网文主编。请基于以下信息，为全书规划 {vol_count.value} 个左右的【分卷 (Volumes)】。

            【裂变策略】{fission_info['name']} - {fission_info['description']}
            【全书核心】{ctx.get('self_info', '')}
            【用户引导】{guidance.value}
            【叙事模型】{template.value}

            【特殊要求】
            """

            # 根据裂变类型添加特殊指令
            if fission_type.value == 'time_based':
                prompt += "请严格按时间顺序规划，每个分卷代表一个明确的时间段（如：少年期、青年期、巅峰期）。"
            elif fission_type.value == 'space_based':
                prompt += "请按空间/地域划分，每个分卷发生在不同的主要地点（如：新手村、主城、秘境）。"
            elif fission_type.value == 'character_based':
                prompt += "请围绕不同的人物支线来规划分卷，每个分卷聚焦一个主要人物的成长弧光。"
            elif fission_type.value == 'conflict_based':
                prompt += "请围绕核心冲突的演变来规划分卷，每个分卷代表冲突的一个阶段（如：冲突酝酿、爆发、高潮、解决）。"
            else:
                prompt += "请根据剧情发展阶段自然划分分卷，确保每个分卷有明确的起承转合。"

            prompt += "\n\n要求：JSON格式列表，包含 title, desc, estimated_chapters（预估章节数）。"

            print(f">>> [DEBUG] 3. Prompt 构建完成 (长度: {len(prompt)})")

            # 3. 调用执行函数
            try:
                print(">>> [DEBUG] 4. 准备调用 call_ai_and_preview...")
                await call_ai_and_preview(prompt, 'create_volumes', fission_type=fission_type.value)
                print(">>> [DEBUG] 5. call_ai_and_preview 调用结束")
            except Exception as e:
                import traceback
                print(f">>> [FATAL ERROR] do_plan 执行崩溃: {e}")
                traceback.print_exc()

        ui.button('生成全书分卷骨架', icon='auto_awesome', on_click=do_plan) \
            .props('unelevated size=lg color=deep-purple') \
            .classes('w-full shadow-lg hover:shadow-xl transition-shadow rounded-lg font-bold text-lg')

        # 新增：生成世界观按钮
        async def generate_world_view():
            print("\n>>> [DEBUG] 1. '生成世界观'按钮被点击")

            # 检查 API Key
            api_key = CFG.get('api_key')
            if not api_key:
                print(">>> [ERROR] API Key 未配置！")
                ui.notify('请先在系统配置中填写 API Key', type='negative')
                return
            print(f">>> [DEBUG] 2. API Key 检查通过: {api_key[:4]}***")

            # 构建生成世界观的提示词
            prompt = f"""
            请基于以下信息生成一个完整的世界观设定：

            【全书核心】{ctx.get('self_info', '')}
            【用户引导】{guidance.value}
            【叙事模型】{template.value}

            请生成详细的世界观设定，包括但不限于：
            1. 世界基本设定（时空背景、社会结构、修炼/职业体系等）
            2. 主要势力分布（门派、国家、组织等）
            3. 人物等级体系（实力划分、境界设定等）
            4. 重要物品/道具体系（武器、丹药、功法等）
            5. 世界规则（魔法系统、科技水平、法律法规等）

            请用结构化的格式输出，便于后续写作时查阅。
            """

            print(f">>> [DEBUG] 3. 世界观Prompt 构建完成 (长度: {len(prompt)})")

            # 调用生成世界观函数
            try:
                print(">>> [DEBUG] 4. 准备调用 generate_world_view_preview...")
                await generate_world_view_preview(prompt)
                print(">>> [DEBUG] 5. generate_world_view_preview 调用结束")
            except Exception as e:
                import traceback
                print(f">>> [FATAL ERROR] generate_world_view 执行崩溃: {e}")
                traceback.print_exc()

        ui.button('生成世界观设定', icon='travel_explore', on_click=generate_world_view) \
            .props('unelevated size=lg color=teal') \
            .classes('w-full mt-4 shadow-lg hover:shadow-xl transition-shadow rounded-lg font-bold text-lg')

def render_volume_actions(ctx, vol_data):
    with ui.card().classes('w-full bg-white shadow-md rounded-xl p-6 gap-6'):
        with ui.row().classes('w-full gap-8 items-start no-wrap'):
            # 左侧引导
            with ui.column().classes('flex-grow gap-2'):
                ui.label('本卷剧情走向').classes('text-sm font-bold text-gray-700')
                guidance = ui.textarea(placeholder='例如：主角刚进入宗门，被师兄刁难...').classes('w-full').props('outlined rows=6')

            # 右侧参数
            with ui.column().classes('w-1/3 gap-5 min-w-[250px] bg-gray-50 p-4 rounded-lg border border-gray-100'):
                # 🌀 裂变类型选择
                ui.label('🌀 章节裂变策略').classes('text-xs font-bold text-gray-500')
                fission_options = {k: f"{v['name']}" for k, v in FISSION_TYPES.items()}
                fission_type = ui.select(fission_options, value='standard').classes('w-full').props('outlined dense bg-white')

                ui.label('🎭 风格与节奏').classes('text-xs font-bold text-gray-500 mt-2')
                template = ui.select(['爽文打脸流', '三幕式结构', '悬疑解谜流', '日常种田流'], value='爽文打脸流').classes('w-full').props('outlined dense bg-white')

                ui.label('📄 预计章节数').classes('text-xs font-bold text-gray-500 mt-2')
                count = ui.number(value=15, min=1, max=100).classes('w-full').props('outlined dense bg-white suffix="章"')

        async def do_plan():
            fission_info = FISSION_TYPES.get(fission_type.value, FISSION_TYPES['standard'])

            prompt = f"""
            你是一个网文架构师。请将【{vol_data['title']}】拆解为 {int(count.value)} 个左右的章节。

            【裂变策略】{fission_info['name']} - {fission_info['description']}
            【本卷目标】{ctx['self_info']}
            【用户引导】{guidance.value}
            【风格模型】{template.value}

            【特殊要求】
            """

            # 根据裂变类型添加特殊指令
            if fission_type.value == 'time_based':
                prompt += "请严格按时间顺序规划章节，每章代表一个明确的时间点或时间段。"
            elif fission_type.value == 'space_based':
                prompt += "请按空间/场景划分章节，每章发生在不同的具体地点。"
            elif fission_type.value == 'character_based':
                prompt += "请围绕不同的人物视角或人物成长阶段来规划章节。"
            elif fission_type.value == 'conflict_based':
                prompt += "请围绕冲突的展开来规划章节，每章代表冲突的一个回合或转折点。"
            else:
                prompt += "请根据剧情自然流程度划分章节，确保每章有明确的冲突和解决。"

            prompt += "\n\n要求：JSON格式列表，包含 title, outline, estimated_words（预估字数）。"

            await call_ai_and_preview(prompt, 'create_chapters', parent_id=vol_data['id'], fission_type=fission_type.value)

        ui.button('推演本卷章节细纲', icon='psychology', on_click=do_plan) \
            .props('unelevated size=lg color=purple') \
            .classes('w-full shadow-lg hover:shadow-xl transition-shadow rounded-lg font-bold')

        # 新增：生成世界观按钮
        async def generate_world_view():
            print("\n>>> [DEBUG] 1. '生成分卷世界观'按钮被点击")

            # 检查 API Key
            api_key = CFG.get('api_key')
            if not api_key:
                print(">>> [ERROR] API Key 未配置！")
                ui.notify('请先在系统配置中填写 API Key', type='negative')
                return
            print(f">>> [DEBUG] 2. API Key 检查通过: {api_key[:4]}***")

            # 构建生成世界观的提示词
            prompt = f"""
            请基于以下信息为【{vol_data['title']}】这一分卷生成详细的世界观设定：

            【本卷核心】{ctx['self_info']}
            【全书世界观】{app_state.settings.get('world_view', '暂无')}
            【用户引导】{guidance.value}
            【风格模型】{template.value}

            请重点描述这一分卷中的特殊设定，包括但不限于：
            1. 本分卷涉及的地点与环境
            2. 本分卷中出现的新势力或重要人物
            3. 本分卷特有的规则或变化
            4. 本分卷中的关键物品或资源

            请注意与全书世界观保持一致，只补充本分卷的细节。
            """

            print(f">>> [DEBUG] 3. 分卷世界观Prompt 构建完成 (长度: {len(prompt)})")

            # 调用生成世界观函数
            try:
                print(">>> [DEBUG] 4. 准备调用 generate_world_view_preview...")
                await generate_world_view_preview(prompt)
                print(">>> [DEBUG] 5. generate_world_view_preview 调用结束")
            except Exception as e:
                import traceback
                print(f">>> [FATAL ERROR] generate_world_view 执行崩溃: {e}")
                traceback.print_exc()

        ui.button('生成分卷世界观', icon='travel_explore', on_click=generate_world_view) \
            .props('unelevated size=lg color=teal') \
            .classes('w-full mt-4 shadow-lg hover:shadow-xl transition-shadow rounded-lg font-bold')

def render_chapter_actions(ctx, chap_data):
    with ui.card().classes('w-full bg-white shadow-md rounded-xl p-6 gap-6'):
        with ui.row().classes('w-full gap-8 items-start no-wrap'):
            with ui.column().classes('flex-grow gap-2'):
                ui.label('本章具体构思').classes('text-sm font-bold text-gray-700')
                guidance = ui.textarea(value=chap_data.get('outline', ''), placeholder='如果大纲为空，请先补充...').classes('w-full').props('outlined rows=6')

            with ui.column().classes('w-1/3 gap-4 min-w-[250px] bg-gray-50 p-4 rounded-lg border border-gray-100'):
                # 🌀 场景裂变类型选择
                ui.label('🌀 场景裂变策略').classes('text-xs font-bold text-gray-500')
                scene_fission_options = {
                    'dialogue_based': '对话驱动型',
                    'action_based': '动作驱动型',
                    'emotion_based': '情感驱动型',
                    'reveal_based': '揭示驱动型',
                    'standard': '标准场景流'
                }
                scene_fission_type = ui.select(scene_fission_options, value='standard').classes('w-full').props('outlined dense bg-white')

                with ui.row().classes('justify-between w-full mt-2'):
                    ui.label('场景切分 (Beats)').classes('text-xs font-bold text-gray-500')
                    scene_label = ui.label('4 个').classes('text-xs font-bold text-indigo-600')

                scene_count = ui.slider(min=2, max=8, value=4, step=1).props('color=indigo label-always') \
                    .on_value_change(lambda e: scene_label.set_text(f'{e.value} 个'))

                ui.label('提示：场景是写作的最小单位，包含地点、人物和冲突。').classes('text-xs text-gray-400 italic leading-tight')

        async def do_plan():
            # 场景裂变类型描述
            scene_fission_descriptions = {
                'dialogue_based': '以对话为核心驱动剧情发展，每个场景围绕关键对话展开',
                'action_based': '以动作为核心驱动剧情发展，每个场景包含明确的动作序列',
                'emotion_based': '以情感变化为核心驱动剧情发展，每个场景聚焦情感转折',
                'reveal_based': '以信息揭示为核心驱动剧情发展，每个场景包含关键信息揭露',
                'standard': '标准的场景划分，包含完整的起承转合'
            }

            fission_desc = scene_fission_descriptions.get(scene_fission_type.value, scene_fission_descriptions['standard'])

            prompt = f"""
            微观剧情设计：将【{chap_data['title']}】拆解为 {scene_count.value} 个具体的【场景】。

            【场景策略】{fission_desc}
            【本章大纲】{guidance.value}
            【上级分卷】{ctx['parent_info']}

            要求：JSON格式列表，包含 scene（场景标题）, desc（场景描述）, est_words（预估字数）, key_elements（关键元素：对话/动作/情感/揭示）。
            """
            await call_ai_and_preview(prompt, 'update_outline', target_chap=chap_data, fission_type=scene_fission_type.value)

        ui.button('生成场景流 (Beat Sheet)', icon='movie_filter', on_click=do_plan) \
            .props('unelevated size=lg color=indigo') \
            .classes('w-full shadow-lg hover:shadow-xl transition-shadow rounded-lg font-bold')

        # 新增：生成世界观按钮
        async def generate_world_view():
            print("\n>>> [DEBUG] 1. '生成章节世界观'按钮被点击")

            # 检查 API Key
            api_key = CFG.get('api_key')
            if not api_key:
                print(">>> [ERROR] API Key 未配置！")
                ui.notify('请先在系统配置中填写 API Key', type='negative')
                return
            print(f">>> [DEBUG] 2. API Key 检查通过: {api_key[:4]}***")

            # 构建生成世界观的提示词
            prompt = f"""
            请基于以下信息为【{chap_data['title']}】这一章节生成详细的世界观细节：

            【本章大纲】{guidance.value}
            【本章目标】{ctx['self_info']}
            【上级分卷世界观】{ctx['parent_info']}
            【全书世界观】{app_state.settings.get('world_view', '暂无')}

            请重点描述这一章节中的具体设定，包括但不限于：
            1. 本章涉及的具体地点和环境描述
            2. 本章中出现的特定人物及其状态
            3. 本章中的关键道具或资源
            4. 本章涉及的特殊规则或情境

            请注意与全书和分卷世界观保持一致，只补充本章节的细节。
            """

            print(f">>> [DEBUG] 3. 章节世界观Prompt 构建完成 (长度: {len(prompt)})")

            # 调用生成世界观函数
            try:
                print(">>> [DEBUG] 4. 准备调用 generate_world_view_preview...")
                await generate_world_view_preview(prompt)
                print(">>> [DEBUG] 5. generate_world_view_preview 调用结束")
            except Exception as e:
                import traceback
                print(f">>> [FATAL ERROR] generate_world_view 执行崩溃: {e}")
                traceback.print_exc()

        ui.button('生成章节世界观', icon='travel_explore', on_click=generate_world_view) \
            .props('unelevated size=lg color=teal') \
            .classes('w-full mt-4 shadow-lg hover:shadow-xl transition-shadow rounded-lg font-bold')

# ================= ⚡ 预览窗口 (AI Result) =================

async def call_ai_and_preview(prompt, action_type, **kwargs):
    print(f">>> [DEBUG] A. 进入 call_ai_and_preview (Type: {action_type})")
    
    # 获取裂变类型
    fission_type = kwargs.get('fission_type', 'standard')
    fission_info = FISSION_TYPES.get(fission_type, FISSION_TYPES['standard'])

    result_area = ui.dialog().classes('backdrop-blur-sm')
    
    # 弹窗本体
    with result_area, ui.card().classes('w-3/4 h-5/6 flex flex-col rounded-2xl shadow-2xl p-0 overflow-hidden'):
        
        # 1. 顶部 Header
        with ui.row().classes('w-full items-center justify-between bg-gray-900 text-white p-4 shrink-0'):
            with ui.row().classes('items-center gap-2'):
                ui.icon(fission_info.get('icon', 'smart_toy'), color='purple-300')
                ui.label('AI 分形裂变结果').classes('text-lg font-bold')
                
                # 显示裂变类型标签
                with ui.badge(fission_info['name'], color=fission_info['color']).classes('ml-2'):
                    pass
            
            ui.button(icon='close', on_click=result_area.close).props('flat round dense color=white')
            
        # 2. 内容容器 (关键：这里只定义容器，不预先创建内部元素)
        content_wrapper = ui.column().classes('w-full flex-grow relative bg-gray-50')
        
        # 3. 初始显示 Loading
        with content_wrapper:
            with ui.column().classes('absolute-center items-center gap-4'):
                ui.spinner('dots', size='4rem', color=fission_info['color'])
                ui.label(f'{fission_info["name"]}裂变中...').classes('text-purple-600 font-bold animate-pulse')
                ui.label(fission_info['description']).classes('text-sm text-gray-400')

        result_area.open()
        
        try:
            print(">>> [DEBUG] C. 请求后端 LLM...")
            # 调用后端
            res = await run.io_bound(backend.sync_call_llm, prompt, CFG['prompts']['json_only_architect_system'], "architect")
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
                    
                    # 显示裂变信息标题
                    with ui.row().classes('items-center gap-3 mb-4'):
                        ui.icon(fission_info.get('icon', 'account_tree'), size='lg', color=fission_info['color'])
                        with ui.column().classes('gap-0'):
                            ui.label(f'🎉 {fission_info["name"]}裂变成功！').classes('text-green-600 font-bold text-lg')
                            # 
                            # 用一个简单的字典把 action_type 翻译成中文
                            target_name_map = {
                                'create_volumes': '分卷', 
                                'create_chapters': '章节', 
                                'create_scenes': '场景'
                            }
                            target_name = target_name_map.get(action_type, '节点') # 找不到默认叫"节点"

                            # 然后再渲染 label
                            ui.label(f'生成 {len(data)} 个{target_name}').classes('text-gray-500 text-sm')
                    
                    # 裂变策略说明
                    with ui.card().classes('w-full bg-blue-50 border border-blue-200 p-3 mb-4'):
                        with ui.row().classes('items-start gap-2'):
                            ui.icon('info', color='blue-500', size='sm').classes('mt-0.5')
                            with ui.column().classes('gap-1'):
                                ui.label('裂变策略说明').classes('text-xs font-bold text-blue-700')
                                ui.label(fission_info['description']).classes('text-xs text-blue-600')
                    
                    # 帮助函数：获取目标名称
                    def get_target_name(action_type):
                        if action_type == 'create_volumes': return '分卷'
                        elif action_type == 'create_chapters': return '章节'
                        elif action_type == 'update_outline': return '场景'
                        return '结果'
                    
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


# ================= 🌍 世界观生成功能 =================

async def generate_world_view_preview(prompt):
    """
    生成世界观设定的预览窗口
    """
    print(f">>> [DEBUG] A. 进入 generate_world_view_preview")

    result_area = ui.dialog().classes('backdrop-blur-sm')

    # 弹窗本体
    with result_area, ui.card().classes('w-3/4 h-5/6 flex flex-col rounded-2xl shadow-2xl p-0 overflow-hidden'):

        # 1. 顶部 Header
        with ui.row().classes('w-full items-center justify-between bg-teal-900 text-white p-4 shrink-0'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('travel_explore', color='teal-300')
                ui.label('AI 世界观生成').classes('text-lg font-bold')

            ui.button(icon='close', on_click=result_area.close).props('flat round dense color=white')

        # 2. 内容容器
        content_wrapper = ui.column().classes('w-full flex-grow relative bg-gray-50')

        # 3. 初始显示 Loading
        with content_wrapper:
            with ui.column().classes('absolute-center items-center gap-4'):
                ui.spinner('dots', size='4rem', color='teal')
                ui.label('世界观生成中...').classes('text-teal-600 font-bold animate-pulse')
                ui.label('正在构建世界设定').classes('text-sm text-gray-400')

        result_area.open()

        try:
            print(">>> [DEBUG] C. 请求后端 LLM...")
            # 调用后端生成世界观
            res = await run.io_bound(backend.sync_call_llm, prompt, CFG['prompts']['writer_system'], "architect")
            print(f">>> [DEBUG] D. 后端返回: {len(res)} chars")

            # ==========================================
            # 【核心修复】直接清空容器，从头绘制结果
            # ==========================================
            content_wrapper.clear()

            with content_wrapper:
                # 重新创建一个占满空间的 Scroll Area
                with ui.scroll_area().classes('w-full h-full p-6'):

                    # 显示结果标题
                    with ui.row().classes('items-center gap-3 mb-4'):
                        ui.icon('travel_explore', size='lg', color='teal')
                        with ui.column().classes('gap-0'):
                            ui.label('🎉 世界观生成成功！').classes('text-teal-600 font-bold text-lg')
                            ui.label('详细的世界设定已生成').classes('text-gray-500 text-sm')

                    # 显示生成的世界观内容
                    with ui.card().classes('w-full bg-white p-4 border border-teal-200 shadow-sm'):
                        ui.markdown(res).classes('text-base text-gray-800 leading-relaxed')

                    # 保存选项
                    with ui.row().classes('items-center gap-4 mt-6 p-4 bg-teal-50 rounded-lg border border-teal-100'):
                        ui.icon('info', color='teal-500').classes('text-lg')
                        ui.label('您可以选择如何处理生成的世界观设定：').classes('text-teal-700 font-medium')

                    # 保存按钮区域
                    with ui.row().classes('w-full gap-4 mt-2'):
                        # 选项1：追加到现有世界观
                        async def append_to_world_view():
                            current_world_view = app_state.settings.get('world_view', '')
                            new_world_view = current_world_view + ('\n\n' if current_world_view else '') + res
                            app_state.settings['world_view'] = new_world_view

                            # 保存到后端
                            await run.io_bound(manager.save_settings, app_state.settings)

                            # 更新Codemirror编辑器的值（如果存在的话）
                            if 'world_editor' in ui_refs and ui_refs['world_editor'] is not None:
                                ui_refs['world_editor'].value = new_world_view

                            ui.notify('世界观已追加到现有设定！', type='positive')
                            result_area.close()

                        # 选项2：替换现有世界观
                        async def replace_world_view():
                            app_state.settings['world_view'] = res

                            # 保存到后端
                            await run.io_bound(manager.save_settings, app_state.settings)

                            # 更新Codemirror编辑器的值（如果存在的话）
                            if 'world_editor' in ui_refs and ui_refs['world_editor'] is not None:
                                ui_refs['world_editor'].value = res

                            ui.notify('世界观已替换现有设定！', type='positive')
                            result_area.close()

                        # 选项3：仅复制到剪贴板
                        async def copy_to_clipboard():
                            # 在 NiceGUI 中复制到剪贴板需要 JavaScript
                            await ui.run_javascript(f'''
                                navigator.clipboard.writeText(`{res.replace("`", "\\`")}`);
                            ''', respond=False)
                            ui.notify('世界观内容已复制到剪贴板！', type='positive')

                        with ui.column().classes('w-1/3'):
                            ui.button('📋 追加到现有设定',
                                     on_click=append_to_world_view) \
                                .props('unelevated color=teal').classes('w-full font-bold')

                        with ui.column().classes('w-1/3'):
                            ui.button('🔄 替换现有设定',
                                     on_click=replace_world_view) \
                                .props('unelevated color=red').classes('w-full font-bold')

                        with ui.column().classes('w-3/4'):
                            ui.button('📄 仅复制内容',
                                     on_click=copy_to_clipboard) \
                                .props('outline color=gray').classes('w-full font-bold')

        except Exception as e:
            import traceback
            traceback.print_exc()

            # 出错时也直接清空重绘
            content_wrapper.clear()
            with content_wrapper:
                with ui.column().classes('w-full h-full items-center justify-center bg-red-50 p-6'):
                    ui.icon('error_outline', size='4rem', color='red-400')
                    ui.label('世界观生成失败').classes('text-xl font-bold text-red-700 mt-2')
                    ui.label(str(e)).classes('text-red-500 mt-2 text-center')
                    with ui.expansion('原始数据'):
                        ui.code(res if 'res' in locals() else 'No response').classes('text-xs')
