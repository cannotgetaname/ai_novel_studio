from nicegui import ui, run
import copy
import backend
import colorsys
from .state import app_state, ui_refs, manager, CFG  # 确保这里有 CFG

# --- 人物 ---
def refresh_char_ui():
    mode = ui_refs['char_view_mode'].text if ui_refs['char_view_mode'] else 'list'
    if ui_refs['char_container']:
        ui_refs['char_container'].clear()
        if mode == 'list':
            with ui_refs['char_container']:
                for idx, char in enumerate(app_state.characters):
                    with ui.card().classes('w-full p-2 mb-2 bg-white border'):
                        with ui.row().classes('justify-between items-center w-full'):
                            with ui.row().classes('items-center'):
                                ui.label(char['name']).classes('text-lg font-bold')
                                ui.badge(char['role'], color='blue').classes('ml-2')
                            with ui.row():
                                ui.button(icon='edit', on_click=lambda i=idx: open_char_dialog(i)).props('flat size=sm dense')
                                ui.button(icon='delete', on_click=lambda i=idx: delete_char(i)).props('flat size=sm dense color=red')
                        ui.label(f"[{char['gender']}] {char['bio']}").classes('text-sm text-grey-8')
                        if char.get('relations'):
                            rels = [f"{r['type']}->{r['target']}" for r in char['relations']]
                            ui.label(f"关系: {', '.join(rels)}").classes('text-xs text-purple-600')
    if ui_refs['char_graph_container']:
        ui_refs['char_graph_container'].clear()
        if mode == 'graph':
            with ui_refs['char_graph_container']:
                render_relation_graph()

def render_relation_graph():
    nodes = []
    links = []
    categories = [{"name": "主角"}, {"name": "配角"}, {"name": "反派"}, {"name": "路人"}]
    for char in app_state.characters:
        symbol_size = 40 if char['role'] == '主角' else 25
        nodes.append({"name": char['name'], "category": char['role'] if char['role'] in ["主角", "配角", "反派"] else "路人", "symbolSize": symbol_size, "draggable": True, "value": char['bio'][:20]})
        for rel in char.get('relations', []):
            links.append({"source": char['name'], "target": rel['target'], "value": rel['type'], "label": {"show": True, "formatter": "{c}"}})
    ui.echart({
        "title": {"text": "人物关系图谱", "top": "bottom", "left": "right"},
        "tooltip": {},
        "legend": [{"data": ["主角", "配角", "反派", "路人"]}],
        "series": [{"type": "graph", "layout": "force", "data": nodes, "links": links, "categories": categories, "roam": True, "label": {"show": True, "position": "right"}, "force": {"repulsion": 300, "edgeLength": 100}, "lineStyle": {"color": "source", "curveness": 0.3}}]
    }).classes('w-full h-full')

def open_char_dialog(index=None):
    is_edit = index is not None
    default_data = {"name": "", "gender": "男", "role": "配角", "status": "存活", "bio": "", "relations": []}
    data = copy.deepcopy(app_state.characters[index]) if is_edit else default_data
    if 'relations' not in data: data['relations'] = []
    temp_relations = list(data['relations']) 
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('编辑人物').classes('text-h6')
        with ui.tabs().classes('w-full') as d_tabs:
            dt_info = ui.tab('基本信息')
            dt_rel = ui.tab('人际关系')
        with ui.tab_panels(d_tabs, value=dt_info).classes('w-full'):
            with ui.tab_panel(dt_info):
                name = ui.input('姓名', value=data['name']).classes('w-full')
                with ui.row().classes('w-full'):
                    gender_opts = ['男', '女', '未知']; cur_gender = data.get('gender', '男')
                    if cur_gender not in gender_opts: gender_opts.append(cur_gender)
                    gender = ui.select(gender_opts, value=cur_gender, label='性别', new_value_mode='add-unique').classes('w-1/3')
                    role_opts = ['主角', '配角', '反派', '路人']; cur_role = data.get('role', '配角')
                    if cur_role not in role_opts: role_opts.append(cur_role)
                    role = ui.select(role_opts, value=cur_role, label='角色', new_value_mode='add-unique').classes('w-1/3')
                    status_opts = ['存活', '死亡', '失踪']; cur_status = data.get('status', '存活')
                    if cur_status not in status_opts: status_opts.append(cur_status)
                    status = ui.select(status_opts, value=cur_status, label='状态', new_value_mode='add-unique').classes('w-1/3')
                bio = ui.textarea('简介', value=data['bio']).classes('w-full')
            with ui.tab_panel(dt_rel):
                rel_container = ui.column().classes('w-full')
                def refresh_rels():
                    rel_container.clear()
                    with rel_container:
                        for r_idx, rel in enumerate(temp_relations):
                            with ui.row().classes('w-full items-center'):
                                others = [c['name'] for c in app_state.characters if c['name'] != name.value]
                                cur_target = rel['target']
                                if cur_target not in others: cur_target = None
                                ui.select(others, value=cur_target, label='目标', on_change=lambda e, i=r_idx: update_rel(i, 'target', e.value)).classes('w-1/3')
                                ui.input(value=rel['type'], label='关系', on_change=lambda e, i=r_idx: update_rel(i, 'type', e.value)).classes('w-1/3')
                                ui.button(icon='delete', on_click=lambda i=r_idx: del_rel(i)).props('flat dense color=red')
                def update_rel(idx, key, val): temp_relations[idx][key] = val
                def del_rel(idx): del temp_relations[idx]; refresh_rels()
                def add_rel(): temp_relations.append({"target": None, "type": ""}); refresh_rels()
                ui.button('➕ 添加关系', on_click=add_rel).props('size=sm w-full'); refresh_rels()
        async def save():
            if not name.value: return
            new_data = {"name": name.value, "gender": gender.value, "role": role.value, "status": status.value, "bio": bio.value, "relations": temp_relations}
            if is_edit: app_state.characters[index] = new_data
            else: app_state.characters.append(new_data)
            await run.io_bound(manager.save_characters, app_state.characters)
            refresh_char_ui(); dialog.close()
        with ui.row().classes('w-full justify-end mt-4'):
            ui.button('取消', on_click=dialog.close).props('flat')
            ui.button('保存', on_click=save).props('color=primary')
    dialog.open()

async def delete_char(index):
    del app_state.characters[index]
    await run.io_bound(manager.save_characters, app_state.characters)
    refresh_char_ui()

# --- 物品 ---
def refresh_item_ui():
    if not ui_refs['item_container']: return
    ui_refs['item_container'].clear()
    with ui_refs['item_container']:
        for idx, item in enumerate(app_state.items):
            with ui.card().classes('w-full p-2 mb-2 bg-white border'):
                with ui.row().classes('justify-between items-center w-full'):
                    with ui.row().classes('items-center'):
                        ui.label(item['name']).classes('text-lg font-bold')
                        ui.badge(item['type'], color='orange').classes('ml-2')
                    with ui.row():
                        ui.button(icon='edit', on_click=lambda i=idx: open_item_dialog(i)).props('flat size=sm dense')
                        ui.button(icon='delete', on_click=lambda i=idx: delete_item(i)).props('flat size=sm dense color=red')
                ui.label(f"[持有: {item['owner']}] {item['desc']}").classes('text-sm text-grey-8')

def open_item_dialog(index=None):
    is_edit = index is not None
    data = copy.deepcopy(app_state.items[index]) if is_edit else {"name": "", "type": "武器", "owner": "主角", "desc": ""}
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('编辑物品').classes('text-h6')
        name = ui.input('名称', value=data['name']).classes('w-full')
        with ui.row().classes('w-full'):
            base_types = ['武器', '丹药', '杂物', '功法', '材料']
            cur_type = data.get('type', '杂物')
            if cur_type not in base_types: base_types.append(cur_type)
            itype = ui.select(base_types, value=cur_type, label='类型', new_value_mode='add-unique').classes('w-1/2')
            owner = ui.input('持有者', value=data['owner']).classes('w-1/2')
        desc = ui.textarea('描述', value=data['desc']).classes('w-full')
        async def save():
            if not name.value: return
            new_data = {"name": name.value, "type": itype.value, "owner": owner.value, "desc": desc.value}
            if is_edit: app_state.items[index] = new_data
            else: app_state.items.append(new_data)
            await run.io_bound(manager.save_items, app_state.items)
            refresh_item_ui(); dialog.close()
        ui.button('保存', on_click=save).props('color=primary w-full')
    dialog.open()

async def delete_item(index):
    del app_state.items[index]
    await run.io_bound(manager.save_items, app_state.items)
    refresh_item_ui()

# ================= 地点管理 (含智能连接整理) =================

def refresh_loc_ui():
    mode = ui_refs['loc_view_mode'].text if ui_refs['loc_view_mode'] else 'list'
    
    # 1. 渲染树形列表模式
    if ui_refs['loc_container']:
        ui_refs['loc_container'].clear()
        if mode == 'list':
            with ui_refs['loc_container']:
                # 构建树形数据
                loc_map = {l['name']: l for l in app_state.locations}
                children_map = {}
                roots = []
                for loc in app_state.locations:
                    parent = loc.get('parent')
                    if parent and parent in loc_map:
                        if parent not in children_map: children_map[parent] = []
                        children_map[parent].append(loc)
                    else:
                        roots.append(loc)
                
                def build_node(loc):
                    node = {'id': loc['name'], 'label': loc['name']}
                    children = children_map.get(loc['name'], [])
                    if children: node['children'] = [build_node(c) for c in children]
                    return node

                tree_nodes = [build_node(r) for r in roots]
                
                if not tree_nodes:
                    ui.label("暂无地点，请点击右上角添加").classes('text-grey italic p-4')
                else:
                    loc_tree = ui.tree(tree_nodes, label_key='label', node_key='id', on_select=lambda e: open_loc_dialog_by_name(e.value)) \
                        .props('filterable no-nodes-label="无数据"') \
                        .classes('w-full text-base')
                    
                    def get_all_ids(nodes):
                        ids = []
                        for node in nodes:
                            ids.append(node['id'])
                            if 'children' in node: ids.extend(get_all_ids(node['children']))
                        return ids
                    loc_tree.expand(get_all_ids(tree_nodes))
                    ui.label('💡 提示：点击树节点可编辑详情').classes('text-xs text-grey-500 mt-2 ml-2')

    # 2. 渲染地图模式
    if ui_refs['loc_graph_container']:
        ui_refs['loc_graph_container'].clear()
        if mode == 'graph':
            with ui_refs['loc_graph_container']:
                render_loc_graph()

def render_loc_graph():
    # 1. 预处理：建立快速索引
    loc_map = {l['name']: l for l in app_state.locations}
    
    # 2. 算法：寻找每个地点的“老祖宗”和“层级深度”
    def get_root_and_depth(loc_name):
        current = loc_map.get(loc_name)
        depth = 0
        visited = set()
        while current and current.get('parent') and current['parent'] in loc_map:
            if current['name'] in visited: break
            visited.add(current['name'])
            current = loc_map[current['parent']]
            depth += 1
        return current['name'] if current else loc_name, depth

    # 3. 提取所有根节点并分配色相 (Hue)
    root_names = sorted(list(set([get_root_and_depth(l['name'])[0] for l in app_state.locations])))
    # 为每个根节点分配一个独一无二的色相值
    root_hues = {name: i / max(1, len(root_names)) for i, name in enumerate(root_names)}
    
    # 【修复核心】构建 Categories 时，强制指定颜色，使其与根节点一致
    categories = []
    for r_name in root_names:
        hue = root_hues.get(r_name, 0)
        # 根节点深度为0，对应亮度0.45，饱和度0.75
        rgb = colorsys.hls_to_rgb(hue, 0.45, 0.75)
        hex_color = '#%02x%02x%02x' % (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
        
        categories.append({
            "name": r_name,
            "itemStyle": {"color": hex_color} # <--- 强制图例使用此颜色
        })
    
    nodes = []
    links = []

    # 4. 构建节点 (Nodes)
    for loc in app_state.locations:
        root_name, depth = get_root_and_depth(loc['name'])
        
        # 色系渐变算法
        hue = root_hues.get(root_name, 0)
        lightness = min(0.9, 0.45 + (depth * 0.1)) # 深度越深越亮(浅)
        saturation = 0.75
        
        rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
        hex_color = '#%02x%02x%02x' % (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
        
        symbol_size = max(20, 60 - (depth * 10))
        
        nodes.append({
            "name": loc['name'],
            "category": root_name, 
            "symbolSize": symbol_size,
            "draggable": True,
            "value": loc.get('desc', '')[:20],
            "itemStyle": {
                "color": hex_color,
                "borderColor": "#fff",
                "borderWidth": 1
            },
            "label": {
                "show": True, 
                "position": "inside" if depth == 0 else "right",
                "fontSize": 14 if depth == 0 else 12,
                "fontWeight": "bold" if depth == 0 else "normal",
                "color": "#fff" if depth == 0 else "#333"
            }
        })
        
        # 5. 构建连线 (Links)
        for neighbor in loc.get('neighbors', []):
            if neighbor in loc_map:
                links.append({
                    "source": loc['name'], 
                    "target": neighbor,
                    "lineStyle": {
                        "type": "solid", "width": 2, "color": "#bbb", "curveness": 0.2, "opacity": 0.5
                    }
                })
        
        parent = loc.get('parent')
        if parent and parent in loc_map:
            links.append({
                "source": loc['name'], 
                "target": parent,
                "symbol": ['none', 'arrow'],
                "symbolSize": [0, 8],
                "lineStyle": {
                    "width": 2, "type": "dashed", 
                    "color": hex_color, # 线条颜色跟随子节点
                    "curveness": 0.1, "opacity": 0.8
                },
                "label": {"show": False}
            })

    # 6. 渲染 ECharts
    ui.echart({
        "title": {"text": "世界地理聚类图", "subtext": "同色系代表同一区域，箭头代表归属关系", "top": "bottom", "left": "right"},
        "tooltip": {},
        "legend": [{
            "data": list(root_names), 
            "type": "scroll", 
            "orient": "vertical", 
            "left": "left", 
            "top": "middle"
        }],
        "series": [{
            "type": "graph",
            "layout": "force",
            "data": nodes,
            "links": links,
            "categories": categories, # 这里现在包含了颜色信息
            "roam": True,
            "label": {"show": True},
            "force": {
                "repulsion": 350,
                "gravity": 0.15,
                "edgeLength": [30, 100],
                "layoutAnimation": True
            }
        }]
    }).classes('w-full h-full')

def open_loc_dialog_by_name(name):
    if not name: return
    idx = next((i for i, l in enumerate(app_state.locations) if l['name'] == name), None)
    if idx is not None: open_loc_dialog(idx)

# 【新增】连接管理器：批量整理单向/双向连接
def open_connection_manager():
    # 1. 扫描所有连接
    loc_map = {l['name']: l for l in app_state.locations}
    issues = [] # (source, target)
    
    for loc in app_state.locations:
        src = loc['name']
        for target in loc.get('neighbors', []):
            # 检查 target 是否也连接了 src
            if target in loc_map:
                target_loc = loc_map[target]
                if src not in target_loc.get('neighbors', []):
                    issues.append({"src": src, "target": target})
    
    if not issues:
        ui.notify("✅ 完美！所有连接均已双向同步。", type='positive')
        return

    # 2. 弹出整理对话框
    with ui.dialog() as dialog, ui.card().classes('w-1/2'):
        ui.label('🛠️ 连接关系整理').classes('text-h6')
        ui.label(f'检测到 {len(issues)} 个单向连接。请勾选需要“自动补全反向连接”的项目。').classes('text-grey-7 text-sm')
        ui.label('未勾选的项目将保留为“单向连接”（特殊情况）。').classes('text-red-400 text-xs italic')
        
        selected_issues = []
        with ui.scroll_area().classes('h-64 border p-2 bg-grey-1'):
            for issue in issues:
                # 默认全部勾选
                selected_issues.append(issue)
                def on_check(e, item=issue):
                    if e.value: selected_issues.append(item)
                    else: selected_issues.remove(item)
                    
                with ui.row().classes('items-center w-full justify-between mb-1'):
                    ui.label(f"{issue['src']} ➝ {issue['target']}").classes('font-mono')
                    ui.checkbox('补全反向', value=True, on_change=on_check).classes('text-sm')
        
        async def apply_fix():
            count = 0
            for issue in selected_issues:
                target_loc = loc_map[issue['target']]
                if 'neighbors' not in target_loc: target_loc['neighbors'] = []
                if issue['src'] not in target_loc['neighbors']:
                    target_loc['neighbors'].append(issue['src'])
                    count += 1
            
            await run.io_bound(manager.save_locations, app_state.locations)
            refresh_loc_ui()
            dialog.close()
            ui.notify(f'已自动补全 {count} 条反向连接', type='positive')

        with ui.row().classes('w-full justify-end mt-4'):
            ui.button('全部保留单向', on_click=dialog.close).props('flat color=grey')
            ui.button('执行整理', on_click=apply_fix).props('color=primary')
    dialog.open()

def open_loc_dialog(index=None):
    is_edit = index is not None
    default_data = {"name": "", "faction": "中立", "desc": "", "neighbors": [], "parent": None}
    
    # 获取原始数据
    if is_edit:
        # 必须使用 deepcopy，否则修改会直接影响 app_state
        data = copy.deepcopy(app_state.locations[index])
    else:
        data = default_data

    if 'neighbors' not in data: data['neighbors'] = []
    
    # 临时编辑区
    temp_neighbors = list(data['neighbors']) 
    # 【关键】记录原始连接，用于计算删除了哪些
    original_neighbors = set(data['neighbors']) 

    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('编辑地点').classes('text-h6')
        name = ui.input('地名', value=data['name']).classes('w-full')
        
        with ui.row().classes('w-full'):
            faction_opts = ['中立', '敌对', '友善', '未知']
            cur_faction = data.get('faction', '中立')
            if cur_faction not in faction_opts: faction_opts.append(cur_faction)
            faction = ui.select(faction_opts, value=cur_faction, label='势力', new_value_mode='add-unique').classes('w-1/2')
            
            other_locs = [l['name'] for l in app_state.locations if l['name'] != data['name']]
            other_locs.insert(0, None)
            current_parent = data.get('parent')
            if current_parent not in other_locs: current_parent = None
            parent = ui.select(other_locs, value=current_parent, label='📍 所属上级').classes('w-1/2')

        desc = ui.textarea('描述', value=data['desc']).classes('w-full')

        ui.separator().classes('my-2')
        ui.label('🛤️ 连通地点').classes('text-sm font-bold text-grey-7')
        neighbors_container = ui.column().classes('w-full gap-1')

        def refresh_neighbors_list():
            neighbors_container.clear()
            with neighbors_container:
                if not temp_neighbors: ui.label("暂无连接").classes('text-xs text-grey italic')
                for idx, n_name in enumerate(temp_neighbors):
                    with ui.row().classes('w-full items-center justify-between bg-grey-1 p-1 rounded'):
                        ui.label(f"➡️ {n_name}").classes('text-sm') # 改为单向箭头提示
                        ui.button(icon='close', on_click=lambda i=idx: remove_neighbor(i)).props('flat size=xs color=red dense')

        def remove_neighbor(idx):
            del temp_neighbors[idx]
            refresh_neighbors_list()

        def add_neighbor():
            opts = [l['name'] for l in app_state.locations if l['name'] != name.value and l['name'] not in temp_neighbors]
            if not opts: ui.notify('没有其他地点可连接', type='warning'); return
            with ui.dialog() as d, ui.card():
                ui.label('添加连接 (默认为单向)')
                sel = ui.select(opts, label='目标地点').classes('w-48')
                ui.button('确定', on_click=lambda: [temp_neighbors.append(sel.value), refresh_neighbors_list(), d.close()] if sel.value else None)
            d.open()

        refresh_neighbors_list()
        ui.button('➕ 添加连接', on_click=add_neighbor).props('size=sm flat color=primary w-full dashed')

        async def save():
            if not name.value: return
            
            # --- 【核心逻辑修改】 ---
            
            # 1. 自动同步删除 (Sync Delete)
            # 算出本次操作删除了哪些连接
            removed_neighbors = original_neighbors - set(temp_neighbors)
            loc_map = {l['name']: l for l in app_state.locations}
            del_count = 0
            
            # 我的旧名字 (用于在对方列表中找到我)
            my_old_name = data['name'] 
            
            for target_name in removed_neighbors:
                if target_name in loc_map:
                    target_loc = loc_map[target_name]
                    # 如果对方连接列表里有我，就删掉 (同步断开)
                    if 'neighbors' in target_loc and my_old_name in target_loc['neighbors']:
                        target_loc['neighbors'].remove(my_old_name)
                        del_count += 1

            # 2. 自动同步新增 (已移除)
            # 根据您的要求，这里不再自动添加反向连接。
            # 如果需要双向，请使用主界面的“整理”工具进行批量修复。

            # ---------------------

            new_data = {
                "name": name.value, "faction": faction.value, "desc": desc.value,
                "neighbors": temp_neighbors, "parent": parent.value 
            }
            
            if is_edit: app_state.locations[index] = new_data
            else: app_state.locations.append(new_data)
            
            await run.io_bound(manager.save_locations, app_state.locations)
            refresh_loc_ui()
            dialog.close()
            
            msg = []
            if del_count > 0: msg.append(f"同步断开了 {del_count} 个反向连接")
            if msg: ui.notify(", ".join(msg), type='positive')
            
        async def delete():
            if is_edit: await delete_loc(index); dialog.close()

        with ui.row().classes('w-full justify-between mt-4'):
            if is_edit: ui.button('删除', on_click=delete, color='red').props('flat icon=delete')
            else: ui.label('') 
            with ui.row():
                ui.button('取消', on_click=dialog.close).props('flat')
                ui.button('保存', on_click=save).props('color=primary')
    dialog.open()

async def delete_loc(index):
    target_loc = app_state.locations[index]
    deleted_name = target_loc['name']
    del app_state.locations[index]
    for loc in app_state.locations:
        if loc.get('parent') == deleted_name: loc['parent'] = None
        if 'neighbors' in loc and deleted_name in loc['neighbors']:
            loc['neighbors'] = [n for n in loc['neighbors'] if n != deleted_name]
    await run.io_bound(manager.save_locations, app_state.locations)
    refresh_loc_ui()
    ui.notify(f'已删除 "{deleted_name}"', type='positive')

# --- 系统配置 UI ---
def refresh_config_ui():
    container = ui_refs.get('config_container')
    if not container: return
    
    container.clear()
    
    # 使用导入的 CFG 和 copy 库
    try:
        local_cfg = copy.deepcopy(CFG)
    except NameError:
        ui.notify("配置加载失败：CFG未导入", type='negative')
        return
    
    with container:
        # 1. 基础配置
        with ui.expansion('🔑 基础设置 (API & 路径)', icon='settings', value=True).classes('w-full bg-grey-1'):
            with ui.column().classes('w-full p-2'):
                ui.input('API Key', value=local_cfg.get('api_key', '')) \
                    .bind_value(local_cfg, 'api_key').classes('w-full').props('type=password')
                ui.input('Base URL', value=local_cfg.get('base_url', '')) \
                    .bind_value(local_cfg, 'base_url').classes('w-full')
                ui.input('Chunk Size (RAG切片大小)', value=str(local_cfg.get('chunk_size', 500))) \
                    .bind_value(local_cfg, 'chunk_size').classes('w-full')
        
        # 2. 模型路由配置
        with ui.expansion('🤖 模型路由 (Models & Temp)', icon='smart_toy').classes('w-full bg-grey-1 mt-2'):
            with ui.grid(columns=2).classes('w-full p-2 gap-4'):
                models = local_cfg.get('models', {})
                temps = local_cfg.get('temperatures', {})
                task_types = ['writer', 'architect', 'editor', 'reviewer', 'timekeeper', 'auditor']
                
                for task in task_types:
                    with ui.card().classes('p-2'):
                        ui.label(f'Task: {task.upper()}').classes('font-bold text-xs text-grey')
                        ui.input('Model Name', value=models.get(task, '')) \
                            .on_value_change(lambda e, t=task: models.update({t: e.value})).classes('w-full dense')
                        ui.number('Temperature', value=temps.get(task, 0.7), min=0.0, max=2.0, step=0.1, format='%.1f') \
                            .on_value_change(lambda e, t=task: temps.update({t: e.value})).classes('w-full dense')

        # 3. 提示词配置
        with ui.expansion('📝 系统提示词 (System Prompts)', icon='description').classes('w-full bg-grey-1 mt-2'):
            with ui.column().classes('w-full p-2'):
                prompts = local_cfg.get('prompts', {})
                prompt_keys = [
                    ('writer_system', '写作助手'),
                    ('architect_system', '架构师'),
                    ('auditor_system', '状态审计'),
                    ('reviewer_system', '审稿人'),
                    ('timekeeper_system', '时间记录员'),
                    ('knowledge_filter_system', '知识清洗'),
                    ('summary_chapter_system', '章节摘要'),
                    ('summary_book_system', '全书总结')
                ]
                
                for key, label in prompt_keys:
                    ui.label(f'{label} ({key})').classes('text-sm font-bold mt-2')
                    ui.textarea(value=prompts.get(key, '')) \
                        .on_value_change(lambda e, k=key: prompts.update({k: e.value})) \
                        .classes('w-full').props('rows=3 input-style="font-size: 13px"')

        # 保存按钮
        async def save_config():
            try:
                local_cfg['chunk_size'] = int(local_cfg['chunk_size'])
            except: pass
            
            # 这里需要 backend 模块
            res = await run.io_bound(backend.save_global_config, local_cfg)
            if "❌" in res:
                ui.notify(res, type='negative')
            else:
                ui.notify(res, type='positive')
                
        ui.button('💾 保存系统配置', on_click=save_config).props('color=primary icon=save').classes('w-full mt-4 h-12 text-lg')