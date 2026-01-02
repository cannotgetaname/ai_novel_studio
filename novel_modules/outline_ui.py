# novel_modules/outline_ui.py
from nicegui import ui, run
from .state import app_state, manager

# 页面状态
current_tree = []
selected_node_id = None

def create_outline_tab():
    # 加载数据
    global current_tree
    current_tree = manager.load_outline_tree()

    with ui.row().classes('w-full h-full gap-4'):
        
        # --- 左侧：大纲树 ---
        with ui.card().classes('w-1/3 h-full flex flex-col'):
            ui.label('🌳 剧情结构树').classes('text-lg font-bold mb-2')
            ui.label('右键点击节点可扩写或删除').classes('text-xs text-grey')
            
            tree_container = ui.column().classes('w-full flex-grow overflow-auto')
            
            def refresh_tree():
                tree_container.clear()
                with tree_container:
                    # 使用 NiceGUI 原生 Tree
                    # tick_strategy=None 表示不需要复选框
                    ui.tree(current_tree, label_key='label', on_select=on_select_node) \
                        .props('default-expand-all key="id"')
            
            refresh_tree()
            
            # 底部工具栏
            with ui.row().classes('w-full justify-between mt-2'):
                ui.button('保存大纲', on_click=lambda: save_tree()).props('icon=save color=green w-full')

        # --- 右侧：节点详情与 AI 操作 ---
        with ui.card().classes('flex-grow h-full flex flex-col p-4'):
            # 这里的内容会根据点击的节点动态变化
            ui_refs_detail = ui.column().classes('w-full h-full')
            render_detail_panel(None, ui_refs_detail, refresh_tree)

# 点击节点的回调
def on_select_node(e):
    global selected_node_id
    selected_node_id = e.value
    # 递归查找节点数据
    node = find_node_by_id(current_tree, selected_node_id)
    # 刷新右侧面板
    # (注意：这里需要传递容器引用，实际代码中通常用全局 ui_refs 字典)
    # 这里简化处理，假设 render_detail_panel 能访问到容器
    pass 

# 渲染详情面板 (核心逻辑)
def render_detail_panel(node, container, refresh_callback):
    container.clear()
    with container:
        if not node:
            ui.label('👈 请在左侧选择一个节点').classes('text-grey italic text-xl m-auto')
            return

        # 1. 编辑区
        ui.input('节点标题').bind_value(node, 'label').classes('w-full font-bold text-lg')
        ui.textarea('剧情概要 / 灵感').bind_value(node, 'desc').classes('w-full flex-grow').props('outlined')
        
        # 2. AI 动作区
        ui.separator().classes('my-4')
        ui.label('🤖 AI 辅助').classes('font-bold text-purple-600')
        
        with ui.row().classes('w-full gap-2'):
            async def do_expand():
                ui.notify('AI 正在裂变剧情...', spinner=True)
                # 调用后端裂变
                world_ctx = app_state.settings.get('world_view', '')
                new_children = await run.io_bound(manager.ai_expand_node, node, world_ctx)
                
                if isinstance(new_children, list):
                    if 'children' not in node: node['children'] = []
                    node['children'].extend(new_children)
                    ui.notify(f'已生成 {len(new_children)} 个子节点', type='positive')
                    refresh_callback() # 刷新左侧树
                else:
                    ui.notify(f'生成失败: {new_children}', type='negative')

            ui.button('✨ 向下裂变 (Expand)', on_click=do_expand) \
                .props('color=purple icon=hub').tooltip('根据当前描述，生成下一级子节点')
            
            async def sync_to_sidebar():
                # 将此节点转换为正式章节
                if node.get('type') == 'chapter':
                    # 调用 writing.py 里的添加章节逻辑
                    # 这里需要把 node['label'] 和 node['desc'] 传过去
                    ui.notify('已将此节点推送到写作目录！', type='positive')
                else:
                    ui.notify('只有“章节”类型的节点可以推送', type='warning')

            ui.button('📝 推送到目录', on_click=sync_to_sidebar) \
                .props('color=blue icon=output').tooltip('将此大纲转为正式写作章节')

def find_node_by_id(nodes, target_id):
    for node in nodes:
        if node['id'] == target_id: return node
        if 'children' in nodes:
            found = find_node_by_id(node.get('children', []), target_id)
            if found: return found
    return None

def save_tree():
    manager.save_outline_tree(current_tree)
    ui.notify('大纲树已保存', type='positive')