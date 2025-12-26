from nicegui import ui, run
import copy
from .state import app_state, ui_refs, manager

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

# --- 地点 ---
def refresh_loc_ui():
    if not ui_refs['loc_container']: return
    ui_refs['loc_container'].clear()
    with ui_refs['loc_container']:
        for idx, loc in enumerate(app_state.locations):
            with ui.card().classes('w-full p-2 mb-2 bg-white border'):
                with ui.row().classes('justify-between items-center w-full'):
                    with ui.row().classes('items-center'):
                        ui.label(loc['name']).classes('text-lg font-bold')
                        ui.badge(loc['faction'], color='green').classes('ml-2')
                    with ui.row():
                        ui.button(icon='edit', on_click=lambda i=idx: open_loc_dialog(i)).props('flat size=sm dense')
                        ui.button(icon='delete', on_click=lambda i=idx: delete_loc(i)).props('flat size=sm dense color=red')
                ui.label(f"{loc['desc']}").classes('text-sm text-grey-8')

def open_loc_dialog(index=None):
    is_edit = index is not None
    data = copy.deepcopy(app_state.locations[index]) if is_edit else {"name": "", "faction": "中立", "desc": ""}
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('编辑地点').classes('text-h6')
        name = ui.input('地名', value=data['name']).classes('w-full')
        faction_opts = ['中立', '敌对', '友善', '未知']
        cur_faction = data.get('faction', '中立')
        if cur_faction not in faction_opts: faction_opts.append(cur_faction)
        faction = ui.select(faction_opts, value=cur_faction, label='势力', new_value_mode='add-unique').classes('w-full')
        desc = ui.textarea('描述', value=data['desc']).classes('w-full')
        async def save():
            if not name.value: return
            new_data = {"name": name.value, "faction": faction.value, "desc": desc.value}
            if is_edit: app_state.locations[index] = new_data
            else: app_state.locations.append(new_data)
            await run.io_bound(manager.save_locations, app_state.locations)
            refresh_loc_ui(); dialog.close()
        ui.button('保存', on_click=save).props('color=primary w-full')
    dialog.open()

async def delete_loc(index):
    del app_state.locations[index]
    await run.io_bound(manager.save_locations, app_state.locations)
    refresh_loc_ui()