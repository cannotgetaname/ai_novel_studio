from nicegui import ui, run, app
import backend
import json
import asyncio
import copy

# ================= 初始化后端 =================
manager = backend.NovelManager()
memory = backend.MemoryManager()
CFG = backend.CFG

# ================= 状态管理 =================
class AppState:
    def __init__(self):
        self.structure = manager.load_structure()
        self.settings = manager.load_settings()
        self.characters = manager.load_characters()
        self.items = manager.load_items()
        self.locations = manager.load_locations()
        
        self.current_chapter_idx = 0
        self.current_content = ""

state = AppState()

# ================= 主页面逻辑 =================

@ui.page('/')
async def main_page():
    # --- UI 引用字典 ---
    ui_refs = {
        'editor_title': None, 'editor_outline': None, 'editor_content': None,
        'char_container': None, 'item_container': None, 'loc_container': None,
        'chapter_list': None, 'rag_debug': None, 'review_panel': None,
        'right_tabs': None, 'tab_ctx': None, 'tab_rev': None,
        'char_count': None, 'total_count': None,
        'char_view_mode': None, 'char_graph_container': None,
        'time_label': None, 'time_events': None, 'timeline_container': None
    }

    # ================= 1. 基础辅助函数 =================

    def update_char_count():
        if ui_refs['editor_content'] and ui_refs['char_count']:
            text = ui_refs['editor_content'].value or ""
            ui_refs['char_count'].set_text(f"当前章节字数: {len(text)}")

    async def refresh_total_word_count():
        if ui_refs['total_count']:
            ui_refs['total_count'].set_text("正在统计...")
            total = await run.io_bound(manager.get_total_word_count)
            ui_refs['total_count'].set_text(f"全书字数: {total:,}")
            ui.notify(f"统计完成：共 {total:,} 字", type='positive')

    def refresh_sidebar():
        if not ui_refs['chapter_list']: return
        ui_refs['chapter_list'].clear()
        with ui_refs['chapter_list']:
            for idx, chap in enumerate(state.structure):
                color = 'primary' if idx == state.current_chapter_idx else 'grey-8'
                icon = ' 📝' if chap.get('review_report') else ''
                time_icon = ' ⏱️' if chap.get('time_info', {}).get('events') else ''
                ui.button(f"{chap['id']}. {chap['title']}{icon}{time_icon}", on_click=lambda i=idx: load_chapter(i)) \
                    .props(f'flat color={color} align=left no-caps').classes('w-full text-left')

    # ================= 2. 核心写作逻辑 =================

    async def load_chapter(index):
        if not state.structure: return
        if index < 0: index = 0
        if index >= len(state.structure): index = len(state.structure) - 1
        
        state.current_chapter_idx = index
        chapter = state.structure[index]
        
        content = await run.io_bound(manager.load_chapter_content, chapter['id'])
        state.current_content = content
        
        if ui_refs['editor_title']: ui_refs['editor_title'].value = chapter['title']
        if ui_refs['editor_outline']: ui_refs['editor_outline'].value = chapter['outline']
        if ui_refs['editor_content']: ui_refs['editor_content'].value = content
        
        # 加载审稿意见
        if ui_refs['review_panel']:
            ui_refs['review_panel'].clear()
            report = chapter.get('review_report', '')
            with ui_refs['review_panel']:
                if report:
                    ui.markdown(report).classes('w-full text-sm p-2')
                else:
                    ui.label("暂无审稿记录").classes('text-grey italic p-2')
            
            if report and ui_refs['right_tabs']:
                ui_refs['right_tabs'].set_value(ui_refs['tab_rev'])
            elif ui_refs['right_tabs']:
                ui_refs['right_tabs'].set_value(ui_refs['tab_ctx'])

        # 加载时间信息
        time_info = chapter.get('time_info', {"label": "未知", "events": []})
        if ui_refs['time_label']: ui_refs['time_label'].value = time_info.get('label', '未知')
        if ui_refs['time_events']: 
            events = time_info.get('events', [])
            if isinstance(events, list): ui_refs['time_events'].value = "\n".join(events)
            else: ui_refs['time_events'].value = str(events)

        update_char_count()
        refresh_sidebar()

    async def save_current_chapter():
        if not state.structure: return
        idx = state.current_chapter_idx
        chapter = state.structure[idx]
        
        # 1. 获取基础信息 (加保护)
        if ui_refs['editor_title']: chapter['title'] = ui_refs['editor_title'].value
        if ui_refs['editor_outline']: chapter['outline'] = ui_refs['editor_outline'].value
        if ui_refs['editor_content']: new_content = ui_refs['editor_content'].value
        else: new_content = "" # 防止报错
        
        # 2. 【修复点】获取时间信息 (加保护)
        events_list = []
        # 检查 ui_refs['time_events'] 是否存在
        if ui_refs['time_events'] and ui_refs['time_events'].value:
            events_list = [e.strip() for e in ui_refs['time_events'].value.split('\n') if e.strip()]
        
        # 检查 ui_refs['time_label'] 是否存在
        time_label = "未知"
        if ui_refs['time_label']:
            time_label = ui_refs['time_label'].value

        chapter['time_info'] = {
            "label": time_label,
            "duration": chapter.get('time_info', {}).get('duration', '-'),
            "events": events_list
        }
        
        ui.notify('正在保存...', type='info')
        await run.io_bound(manager.save_chapter_content, chapter['id'], new_content)
        await run.io_bound(manager.save_structure, state.structure)
        await run.io_bound(memory.add_chapter_memory, chapter['id'], new_content)
        
        ui.notify('保存成功！', type='positive')
        refresh_sidebar()
        refresh_timeline()
        await refresh_total_word_count()

    async def generate_content():
        idx = state.current_chapter_idx
        chapter = state.structure[idx]
        title = ui_refs['editor_title'].value
        outline = ui_refs['editor_outline'].value
        
        if ui_refs['right_tabs']:
            ui_refs['right_tabs'].set_value(ui_refs['tab_ctx'])

        ui.notify(f'正在执行智能检索...', type='info')
        query = f"{title} {outline}"
        if len(query) < 5: query = f"{title} {state.settings['world_view'][:50]}"
        
        filtered_context, debug_info = await run.io_bound(
            manager.smart_rag_pipeline, query, chapter['id'], memory
        )
        
        context_text = f"{title} {outline}"
        char_prompt_str, active_names = manager.get_relevant_context(context_text)
        if active_names: ui.notify(f"已激活: {', '.join(active_names)}", type='positive')
        
        if ui_refs['rag_debug']:
            ui_refs['rag_debug'].clear()
            with ui_refs['rag_debug']:
                ui.label("🧩 激活数据:").classes('font-bold text-sm')
                ui.label(f"{', '.join(active_names) if active_names else '无'}").classes('text-sm text-blue-600 mb-2')
                
                ui.label("🧠 智能清洗后的记忆:").classes('font-bold text-sm')
                ui.label(filtered_context).classes('text-sm text-green-800 bg-green-50 p-2 rounded mb-2')
                
                ui.label("📚 原始命中片段:").classes('font-bold text-sm')
                for item in debug_info:
                    icon = "✅" if item['valid'] else "🚫"
                    with ui.card().classes('w-full p-2 mb-2 bg-white border'):
                        ui.label(f"{icon} [{item['source']}] Dist:{item['distance']}").classes('text-xs font-bold')
                        ui.label(f"{item['text'][:100]}...").classes('text-sm text-grey-8 break-all')
        
        prompt = f"""
        【世界观】{state.settings['world_view']}
        【本章相关资料】{char_prompt_str}
        【历史背景资料 (已清洗)】{filtered_context}
        【本章大纲】标题：{title}\n内容：{outline}
        请撰写正文。
        """
        
        ui.notify('AI 正在思考...', type='info', spinner=True)
        res = await run.io_bound(backend.sync_call_llm, prompt, CFG['prompts']['writer_system'], task_type="writer")
        
        if "Error" in res:
            ui.notify(res, type='negative')
        else:
            ui_refs['editor_content'].value = res
            update_char_count()
            ui.notify('生成完毕！', type='positive')

    async def add_new_chapter():
        last_id = state.structure[-1]['id'] if state.structure else 0
        new_id = last_id + 1
        new_chap = {
            "id": new_id, "title": f"第{new_id}章", "outline": "待补充", "summary": "",
            "time_info": {"label": "未知时间", "duration": "-", "events": []}
        }
        state.structure.append(new_chap)
        await run.io_bound(manager.save_structure, state.structure)
        await load_chapter(len(state.structure) - 1)

    async def delete_current_chapter():
        if len(state.structure) <= 1:
            ui.notify('至少保留一章', type='warning')
            return
        idx = state.current_chapter_idx
        chap_id = state.structure[idx]['id']
        await run.io_bound(manager.delete_chapter, chap_id)
        await run.io_bound(memory.delete_chapter_memory, chap_id)
        del state.structure[idx]
        await run.io_bound(manager.save_structure, state.structure)
        new_idx = max(0, idx - 1)
        await load_chapter(new_idx)
        ui.notify('章节及记忆已删除', type='negative')

    # ================= 3. 高级功能 (重绘/审稿/导出/时间/状态) =================

    # --- 【V13】状态自动结算 (含关系提取) ---
    async def open_state_audit_dialog():
        content = ui_refs['editor_content'].value
        if not content or len(content) < 50:
            ui.notify('正文太短，无法分析状态', type='warning')
            return
        
        ui.notify('DeepSeek-R1 正在深度思考...', spinner=True)
        
        summary_data = {
            "existing_chars": [c['name'] for c in state.characters],
            "existing_items": [i['name'] for i in state.items],
            "existing_locs": [l['name'] for l in state.locations]
        }
        
        res = await run.io_bound(backend.sync_analyze_state, content, json.dumps(summary_data, ensure_ascii=False))
        
        try:
            clean_res = res.replace("```json", "").replace("```", "").strip()
            start = clean_res.find('{')
            end = clean_res.rfind('}')
            if start == -1 or end == -1: raise ValueError("JSON 解析失败")
            
            changes = json.loads(clean_res[start:end+1])
            
            with ui.dialog() as dialog, ui.card().classes('w-2/3 h-3/4'):
                ui.label('🌍 世界状态结算单').classes('text-h6')
                ui.label('请勾选需要执行的变更：').classes('text-sm text-grey')
                
                with ui.scroll_area().classes('w-full flex-grow border p-2'):
                    selected_changes = {
                        "char_updates": [], "item_updates": [], 
                        "new_chars": [], "new_items": [], "new_locs": [],
                        "relation_updates": []
                    }
                    
                    def render_section(title, key, items, label_func):
                        if items:
                            ui.label(title).classes('font-bold mt-2 text-blue-600')
                            for item in items:
                                selected_changes[key].append(item) 
                                def on_check(e, it=item, k=key):
                                    if e.value: selected_changes[k].append(it)
                                    else: selected_changes[k].remove(it)
                                ui.checkbox(label_func(item), value=True, on_change=on_check).classes('text-sm')

                    render_section("👤 人物状态变更", "char_updates", changes.get('char_updates', []), 
                                   lambda x: f"{x['name']} [{x['field']}] -> {x['new_value']} ({x.get('reason','')})")
                    
                    render_section("🕸️ 人际关系变更", "relation_updates", changes.get('relation_updates', []),
                                   lambda x: f"{x['source']} -> {x['target']} : {x['type']} ({x.get('desc','')})")

                    render_section("📦 物品变更", "item_updates", changes.get('item_updates', []), 
                                   lambda x: f"{x['name']} [{x['field']}] -> {x['new_value']}")
                    render_section("🆕 新发现人物", "new_chars", changes.get('new_chars', []), 
                                   lambda x: f"[新] {x['name']} - {x.get('role','')} ({x.get('bio','')[:20]}...)")
                    render_section("🆕 新获得物品", "new_items", changes.get('new_items', []), 
                                   lambda x: f"[新] {x['name']} ({x.get('type','')})")
                    render_section("🆕 新开启地点", "new_locs", changes.get('new_locs', []), 
                                   lambda x: f"[新] {x['name']} ({x.get('desc','')[:20]}...)")

                with ui.row().classes('w-full justify-end'):
                    ui.button('取消', on_click=dialog.close).props('flat color=grey')
                    async def confirm_apply():
                        logs = await run.io_bound(backend.apply_state_changes, manager, selected_changes)
                        state.characters = await run.io_bound(manager.load_characters)
                        state.items = await run.io_bound(manager.load_items)
                        state.locations = await run.io_bound(manager.load_locations)
                        refresh_char_ui()
                        refresh_item_ui()
                        refresh_loc_ui()
                        dialog.close()
                        ui.notify(f'成功应用 {len(logs)} 项变更', type='positive')
                    ui.button('确认执行', on_click=confirm_apply).props('color=green')
            dialog.open()

        except Exception as e:
            ui.notify('分析结果解析失败', type='negative')
            with ui.dialog() as d, ui.card():
                ui.label('Error').classes('text-red')
                ui.code(res)
            d.open()

    # --- 时间分析 ---
    async def analyze_time():
        content = ui_refs['editor_content'].value
        if not content or len(content) < 50:
            ui.notify('正文太短，无法分析', type='warning')
            return
        
        idx = state.current_chapter_idx
        prev_time = "故事开始"
        if idx > 0:
            prev_time = state.structure[idx-1].get('time_info', {}).get('label', '未知')
            
        ui.notify('正在推演时间线...', spinner=True)
        res = await run.io_bound(backend.sync_analyze_time, content, prev_time)
        
        try:
            clean_res = res.replace("```json", "").replace("```", "").strip()
            start = clean_res.find('{')
            end = clean_res.rfind('}')
            
            if start != -1 and end != -1:
                json_str = clean_res[start:end+1]
                data = json.loads(json_str)
                
                ui_refs['time_label'].value = data.get('label', '未知')
                events = data.get('events', [])
                ui_refs['time_events'].value = "\n".join(events)
                ui.notify(f"时间推进: {data.get('duration')}", type='positive')
                ui.notify('请点击【保存】以更新时间轴', type='warning', close_button=True)
            else:
                raise ValueError("未找到有效的 JSON 结构")
                
        except Exception as e:
            ui.notify(f'解析失败，请查看详情', type='negative')
            with ui.dialog() as dialog, ui.card().classes('w-1/2'):
                ui.label('❌ 解析错误 (Debug)').classes('text-h6 text-red')
                ui.label(f"错误信息: {str(e)}")
                ui.label("AI 返回的原始数据:").classes('font-bold mt-2')
                ui.code(res).classes('w-full h-64')
                ui.button('关闭', on_click=dialog.close)
            dialog.open()

    def refresh_timeline():
        if not ui_refs['timeline_container']: return
        ui_refs['timeline_container'].clear()
        
        with ui_refs['timeline_container']:
            has_data = False
            for chap in state.structure:
                t_info = chap.get('time_info', {})
                if t_info.get('events') or t_info.get('label') != "未知时间":
                    has_data = True
                    break
            
            if not has_data:
                ui.label("暂无时间线数据。请在写作页面点击【⏱️ 分析时间】并【保存】。").classes('text-grey italic p-4')
                return

            with ui.timeline(side='right'):
                for chap in state.structure:
                    t_info = chap.get('time_info', {})
                    events = t_info.get('events', [])
                    
                    if events or t_info.get('label') != "未知时间":
                        ui.timeline_entry(
                            title=f"第{chap['id']}章 {chap['title']}",
                            subtitle=t_info.get('label', ''),
                            body="\n".join([f"• {e}" for e in events]),
                            icon='schedule'
                        )

    async def open_rewrite_dialog():
        js_code = """
            var textarea = document.querySelector('.main-editor textarea');
            if (textarea) { return [textarea.selectionStart, textarea.selectionEnd]; } 
            else { return [0, 0]; }
        """
        try: selection = await ui.run_javascript(js_code)
        except: return
        start, end = selection[0], selection[1]
        full_text = ui_refs['editor_content'].value or ""
        selected_text = full_text[start:end]
        if not selected_text.strip():
            ui.notify('请先选中文字', type='warning')
            return

        with ui.dialog() as dialog, ui.card().classes('w-1/2'):
            ui.label('✨ 局部重绘').classes('text-h6')
            with ui.row().classes('w-full bg-grey-2 p-2 rounded'):
                ui.label(selected_text[:100] + "...").classes('text-sm italic')
            instruction_input = ui.input('修改要求').classes('w-full')
            with ui.row().classes('gap-2'):
                ui.button('润色', on_click=lambda: instruction_input.set_value('润色文笔')).props('size=xs outline')
                ui.button('扩写', on_click=lambda: instruction_input.set_value('扩写这段内容')).props('size=xs outline')
            async def confirm_rewrite():
                if not instruction_input.value: return
                ui.notify('AI 正在重写...', spinner=True)
                dialog.close()
                context_pre = full_text[:start]
                context_post = full_text[end:]
                new_text = await run.io_bound(backend.sync_rewrite_llm, selected_text, context_pre, context_post, instruction_input.value)
                if "Error" in new_text: ui.notify('重写失败', type='negative')
                else:
                    final_text = context_pre + new_text + context_post
                    ui_refs['editor_content'].value = final_text
                    ui.notify('重写完成！', type='positive')
                    update_char_count()
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('取消', on_click=dialog.close).props('flat')
                ui.button('开始重写', on_click=confirm_rewrite).props('color=purple')
        dialog.open()

    async def open_review_dialog():
        content = ui_refs['editor_content'].value
        if not content or len(content) < 50:
            ui.notify('正文太短，无法审查', type='warning')
            return
        ui.notify('正在召唤主编...', spinner=True)
        
        context_str = f"【世界观】{state.settings['world_view']}\n"
        for char in state.characters:
            context_str += f"- {char['name']}: {char['status']}, {char['role']}\n"
            
        report = await run.io_bound(backend.sync_review_chapter, content, context_str)
        
        idx = state.current_chapter_idx
        state.structure[idx]['review_report'] = report
        await run.io_bound(manager.save_structure, state.structure)
        
        if ui_refs['review_panel']:
            ui_refs['review_panel'].clear()
            with ui_refs['review_panel']:
                ui.markdown(report).classes('w-full text-sm p-2')
        
        if ui_refs['right_tabs']:
            ui_refs['right_tabs'].set_value(ui_refs['tab_rev'])
        
        refresh_sidebar()
        ui.notify('审稿报告已保存', type='positive')
        
        with ui.dialog() as dialog, ui.card().classes('w-2/3 h-3/4'):
            with ui.row().classes('w-full justify-between items-center'):
                ui.label('📋 审稿报告').classes('text-h6')
                ui.button(icon='close', on_click=dialog.close).props('flat round dense')
            ui.separator()
            with ui.scroll_area().classes('w-full flex-grow'):
                ui.markdown(report).classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('我知道了', on_click=dialog.close).props('color=primary')
        dialog.open()

    async def export_novel():
        ui.notify('正在打包全书...', spinner=True)
        full_text = await run.io_bound(backend.export_full_novel, manager)
        ui.download(full_text.encode('utf-8'), 'my_novel.txt')
        ui.notify('下载已开始', type='positive')

    # ================= 4. 设定管理逻辑 (CRUD + Graph) =================

    def refresh_char_ui():
        mode = ui_refs['char_view_mode'].text if ui_refs['char_view_mode'] else 'list'
        
        if ui_refs['char_container']:
            ui_refs['char_container'].clear()
            if mode == 'list':
                with ui_refs['char_container']:
                    for idx, char in enumerate(state.characters):
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
        
        for char in state.characters:
            symbol_size = 40 if char['role'] == '主角' else 25
            nodes.append({
                "name": char['name'],
                "category": char['role'] if char['role'] in ["主角", "配角", "反派"] else "路人",
                "symbolSize": symbol_size,
                "draggable": True,
                "value": char['bio'][:20]
            })
            
            for rel in char.get('relations', []):
                links.append({
                    "source": char['name'],
                    "target": rel['target'],
                    "value": rel['type'],
                    "label": {"show": True, "formatter": "{c}"}
                })

        ui.echart({
            "title": {"text": "人物关系图谱", "top": "bottom", "left": "right"},
            "tooltip": {},
            "legend": [{"data": ["主角", "配角", "反派", "路人"]}],
            "series": [{
                "type": "graph",
                "layout": "force",
                "data": nodes,
                "links": links,
                "categories": categories,
                "roam": True,
                "label": {"show": True, "position": "right"},
                "force": {"repulsion": 300, "edgeLength": 100},
                "lineStyle": {"color": "source", "curveness": 0.3}
            }]
        }).classes('w-full h-full')

    def open_char_dialog(index=None):
        is_edit = index is not None
        default_data = {"name": "", "gender": "男", "role": "配角", "status": "存活", "bio": "", "relations": []}
        data = copy.deepcopy(state.characters[index]) if is_edit else default_data
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
                        gender_opts = ['男', '女', '未知']
                        cur_gender = data.get('gender', '男')
                        if cur_gender not in gender_opts: gender_opts.append(cur_gender)
                        gender = ui.select(gender_opts, value=cur_gender, label='性别', new_value_mode='add-unique').classes('w-1/3')
                        
                        role_opts = ['主角', '配角', '反派', '路人']
                        cur_role = data.get('role', '配角')
                        if cur_role not in role_opts: role_opts.append(cur_role)
                        role = ui.select(role_opts, value=cur_role, label='角色', new_value_mode='add-unique').classes('w-1/3')
                        
                        status_opts = ['存活', '死亡', '失踪']
                        cur_status = data.get('status', '存活')
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
                                    others = [c['name'] for c in state.characters if c['name'] != name.value]
                                    
                                    current_target = rel['target']
                                    if current_target not in others:
                                        current_target = None
                                        
                                    ui.select(others, value=current_target, label='目标', 
                                              on_change=lambda e, i=r_idx: update_rel(i, 'target', e.value)).classes('w-1/3')
                                    ui.input(value=rel['type'], label='关系', 
                                             on_change=lambda e, i=r_idx: update_rel(i, 'type', e.value)).classes('w-1/3')
                                    ui.button(icon='delete', on_click=lambda i=r_idx: del_rel(i)).props('flat dense color=red')

                    def update_rel(idx, key, val):
                        temp_relations[idx][key] = val
                    
                    def del_rel(idx):
                        del temp_relations[idx]
                        refresh_rels()
                    
                    def add_rel():
                        temp_relations.append({"target": None, "type": ""})
                        refresh_rels()

                    ui.button('➕ 添加关系', on_click=add_rel).props('size=sm w-full')
                    refresh_rels()

            async def save():
                if not name.value: return
                new_data = {
                    "name": name.value, "gender": gender.value, "role": role.value, 
                    "status": status.value, "bio": bio.value, "relations": temp_relations
                }
                if is_edit: state.characters[index] = new_data
                else: state.characters.append(new_data)
                await run.io_bound(manager.save_characters, state.characters)
                refresh_char_ui()
                dialog.close()
            
            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('取消', on_click=dialog.close).props('flat')
                ui.button('保存', on_click=save).props('color=primary')
        dialog.open()

    async def delete_char(index):
        del state.characters[index]
        await run.io_bound(manager.save_characters, state.characters)
        refresh_char_ui()

    # --- 物品 ---
    def refresh_item_ui():
        if not ui_refs['item_container']: return
        ui_refs['item_container'].clear()
        with ui_refs['item_container']:
            for idx, item in enumerate(state.items):
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
        data = copy.deepcopy(state.items[index]) if is_edit else {"name": "", "type": "武器", "owner": "主角", "desc": ""}
        with ui.dialog() as dialog, ui.card().classes('w-96'):
            ui.label('编辑物品').classes('text-h6')
            name = ui.input('名称', value=data['name']).classes('w-full')
            with ui.row().classes('w-full'):
                base_types = ['武器', '丹药', '杂物', '功法', '材料']
                current_type = data.get('type', '杂物')
                if current_type and current_type not in base_types: base_types.append(current_type)
                itype = ui.select(base_types, value=current_type, label='类型', new_value_mode='add-unique').classes('w-1/2')
                owner = ui.input('持有者', value=data['owner']).classes('w-1/2')
            desc = ui.textarea('描述', value=data['desc']).classes('w-full')
            async def save():
                if not name.value: return
                new_data = {"name": name.value, "type": itype.value, "owner": owner.value, "desc": desc.value}
                if is_edit: state.items[index] = new_data
                else: state.items.append(new_data)
                await run.io_bound(manager.save_items, state.items)
                refresh_item_ui()
                dialog.close()
            ui.button('保存', on_click=save).props('color=primary w-full')
        dialog.open()

    async def delete_item(index):
        del state.items[index]
        await run.io_bound(manager.save_items, state.items)
        refresh_item_ui()

    # --- 地点 ---
    def refresh_loc_ui():
        if not ui_refs['loc_container']: return
        ui_refs['loc_container'].clear()
        with ui_refs['loc_container']:
            for idx, loc in enumerate(state.locations):
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
        data = copy.deepcopy(state.locations[index]) if is_edit else {"name": "", "faction": "中立", "desc": ""}
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
                if is_edit: state.locations[index] = new_data
                else: state.locations.append(new_data)
                await run.io_bound(manager.save_locations, state.locations)
                refresh_loc_ui()
                dialog.close()
            ui.button('保存', on_click=save).props('color=primary w-full')
        dialog.open()

    async def delete_loc(index):
        del state.locations[index]
        await run.io_bound(manager.save_locations, state.locations)
        refresh_loc_ui()

    # ================= 5. 界面布局构建 =================

    # --- 侧边栏 ---
    with ui.left_drawer(value=True).classes('bg-blue-50') as drawer:
        ui.label('📚 章节目录').classes('text-h6 q-mb-md')
        
        with ui.card().classes('w-full q-mb-md bg-white p-2'):
            ui_refs['total_count'] = ui.label('全书字数: ---').classes('text-sm font-bold')
            with ui.row().classes('w-full'):
                ui.button('🔄 刷新', on_click=refresh_total_word_count).props('flat size=sm color=primary').classes('w-1/2')
                ui.button('📤 导出', on_click=export_novel).props('flat size=sm color=grey').classes('w-1/2')

        with ui.scroll_area().classes('h-full'):
            ui_refs['chapter_list'] = ui.column().classes('w-full')
            refresh_sidebar()
        
        with ui.row().classes('w-full q-mt-md'):
            ui.button('➕ 新建', on_click=add_new_chapter).props('flat color=green')
            ui.button('🗑️ 删除', on_click=delete_current_chapter).props('flat color=red')

    # --- 顶部导航 ---
    with ui.header().classes('bg-white text-black shadow-sm'):
        ui.button(on_click=lambda: drawer.toggle(), icon='menu').props('flat color=black')
        ui.label('AI 网文工作站 (V13.0 完整版)').classes('text-h6')

    # --- 主内容 Tabs ---
    with ui.tabs().classes('w-full') as tabs:
        tab_write = ui.tab('写作')
        tab_setting = ui.tab('设定')
        tab_arch = ui.tab('架构师')
        tab_timeline = ui.tab('时间轴')

    with ui.tab_panels(tabs, value=tab_write).classes('w-full h-full p-0'):
        
        # --- Tab 1: 写作 ---
        with ui.tab_panel(tab_write).classes('h-full p-0'):
            with ui.splitter(value=75).classes('w-full h-full') as splitter:
                with splitter.before:
                    with ui.column().classes('w-full h-full p-4'):
                        ui_refs['editor_title'] = ui.input(label='章节标题').classes('w-full')
                        ui_refs['editor_outline'] = ui.textarea(label='本章大纲').classes('w-full').props('rows=3')
                        
                        with ui.row().classes('items-center'):
                            ui.button('🚀 生成正文', on_click=generate_content).props('color=primary')
                            ui.button('💾 保存', on_click=save_current_chapter).props('color=green')
                            ui.button('🌍 状态结算', on_click=open_state_audit_dialog).props('color=blue outline')
                            ui.button('✨ 局部重绘', on_click=open_rewrite_dialog).props('color=purple outline')
                            ui.button('🔍 智能审稿', on_click=open_review_dialog).props('color=orange outline')
                            
                            ui_refs['char_count'] = ui.label('当前章节字数: 0').classes('ml-4 text-grey-7')
                        
                        ui_refs['editor_content'] = ui.textarea(label='正文内容') \
                            .classes('w-full h-full font-mono main-editor') \
                            .props('rows=20 borderless spellcheck="false" input-style="line-height: 2.0; font-size: 16px;"') \
                            .on_value_change(update_char_count)
                
                with splitter.after:
                    with ui.column().classes('w-full h-full p-0 bg-blue-50'):
                        with ui.tabs().classes('w-full bg-blue-100 text-grey-8') as right_tabs:
                            ui_refs['right_tabs'] = right_tabs
                            ui_refs['tab_ctx'] = ui.tab('上下文')
                            ui_refs['tab_rev'] = ui.tab('审稿意见')

                        with ui.tab_panels(right_tabs, value=ui_refs['tab_ctx']) \
                                .classes('w-full flex-grow bg-transparent') \
                                .props('keep-alive animated vertical'):

                            with ui.tab_panel(ui_refs['tab_ctx']).classes('w-full h-full p-0 flex flex-col'):
                                with ui.scroll_area().classes('w-full flex-grow p-2'):
                                    ui_refs['rag_debug'] = ui.column().classes('w-full')

                            with ui.tab_panel(ui_refs['tab_rev']).classes('w-full h-full p-0 flex flex-col'):
                                with ui.scroll_area().classes('w-full flex-grow p-2'):
                                    ui_refs['review_panel'] = ui.column().classes('w-full')
                                    ui.label("暂无审稿记录").classes('text-grey italic')

        # --- Tab 2: 设定 ---
        with ui.tab_panel(tab_setting).classes('h-full p-0'):
            with ui.tabs().classes('w-full bg-grey-2') as set_tabs:
                t_world = ui.tab('世界观')
                t_char = ui.tab('人物')
                t_item = ui.tab('物品')
                t_loc = ui.tab('地点')
            
            with ui.tab_panels(set_tabs, value=t_world).classes('w-full flex-grow'):
                # 1. 世界观
                with ui.tab_panel(t_world).classes('h-full p-4'):
                    with ui.column().classes('w-full h-full'):
                        world_input = ui.textarea(value=state.settings['world_view']) \
                            .classes('w-full flex-grow').props('borderless input-style="height: 100%"')
                        ui.button('保存', on_click=lambda: run.io_bound(manager.save_settings, state.settings)).props('color=green w-full')
                
                # 2. 人物 (含图谱切换)
                with ui.tab_panel(t_char).classes('h-full p-2'):
                    with ui.column().classes('w-full h-full'):
                        with ui.row().classes('w-full justify-between items-center pb-2'):
                            with ui.button_group():
                                ui.button('列表', on_click=lambda: [ui_refs['char_view_mode'].set_text('list'), refresh_char_ui()]).props('size=sm')
                                ui.button('图谱', on_click=lambda: [ui_refs['char_view_mode'].set_text('graph'), refresh_char_ui()]).props('size=sm')
                            
                            ui_refs['char_view_mode'] = ui.label('list').classes('hidden') 

                            with ui.row():
                                ui.button(icon='refresh', on_click=refresh_char_ui).props('flat round dense')
                                ui.button('添加人物', icon='add', on_click=lambda: open_char_dialog()).props('size=sm color=blue')
                        
                        with ui.element('div').classes('w-full').style('height: calc(100vh - 200px); position: relative;'):
                            with ui.scroll_area().classes('w-full h-full').bind_visibility_from(ui_refs['char_view_mode'], 'text', backward=lambda x: x == 'list'):
                                ui_refs['char_container'] = ui.column().classes('w-full p-1')
                            with ui.element('div').classes('w-full h-full').bind_visibility_from(ui_refs['char_view_mode'], 'text', backward=lambda x: x == 'graph'):
                                ui_refs['char_graph_container'] = ui.column().classes('w-full h-full')
                            refresh_char_ui()

                # 3. 物品
                with ui.tab_panel(t_item).classes('h-full p-2'):
                    with ui.column().classes('w-full h-full'):
                        with ui.row().classes('w-full justify-end pb-2'):
                            ui.button('➕ 添加物品', on_click=lambda: open_item_dialog()).props('size=sm color=orange')
                        with ui.scroll_area().classes('w-full').style('height: calc(100vh - 200px); border: 1px solid #eee'):
                            ui_refs['item_container'] = ui.column().classes('w-full p-1')
                            refresh_item_ui()

                # 4. 地点
                with ui.tab_panel(t_loc).classes('h-full p-2'):
                    with ui.column().classes('w-full h-full'):
                        with ui.row().classes('w-full justify-end pb-2'):
                            ui.button('➕ 添加地点', on_click=lambda: open_loc_dialog()).props('size=sm color=green')
                        with ui.scroll_area().classes('w-full').style('height: calc(100vh - 200px); border: 1px solid #eee'):
                            ui_refs['loc_container'] = ui.column().classes('w-full p-1')
                            refresh_loc_ui()

        # --- Tab 3: 架构师 ---
        with ui.tab_panel(tab_arch).classes('p-4'):
            ui.label('🏗️ 批量大纲生成').classes('text-h6')
            theme_input = ui.textarea(label='后续剧情走向').classes('w-full')
            count_slider = ui.slider(min=3, max=10, value=5).props('label-always')
            
            async def run_architect_wrapper():
                if not state.structure:
                    ui.notify('请先创建第一章', type='warning')
                    return
                ui.notify('架构师正在回顾剧情...', spinner=True)
                recent_chapters = state.structure[-3:] 
                recent_context_text = ""
                for chap in recent_chapters:
                    recent_context_text += f"第{chap['id']}章 [{chap['title']}]: {chap['outline']}\n"
                ui.notify('正在检索相关伏笔...', spinner=True)
                query = f"{theme_input.value}"
                valid_docs, _ = await run.io_bound(memory.query_related_memory, query)
                rag_context_text = "\n".join(valid_docs)
                start_id = state.structure[-1]['id'] + 1
                prompt = f"""
                【角色与世界观】{state.settings['world_view']}
                【相关历史伏笔】{rag_context_text}
                【最近剧情回顾】{recent_context_text}
                【接下来的剧情要求】{theme_input.value}
                【任务】请规划接下来的 {count_slider.value} 章大纲（从第 {start_id} 章开始）。
                要求：1. 剧情必须紧接“最近剧情回顾”，逻辑连贯。2. 利用“相关历史伏笔”中的信息。3. 严格遵守 JSON 格式，不要废话。
                """
                ui.notify('架构师正在推演...', spinner=True)
                res = await run.io_bound(backend.sync_call_llm, prompt, CFG['prompts']['architect_system'], task_type="architect")
                try:
                    start_idx = res.find('[')
                    end_idx = res.rfind(']')
                    if start_idx == -1 or end_idx == -1: raise ValueError("未找到JSON数组")
                    json_str = res[start_idx : end_idx + 1]
                    new_data = json.loads(json_str)
                    with ui.dialog() as dialog, ui.card().classes('w-1/2'):
                        ui.label(f"✅ 成功规划 {len(new_data)} 章").classes('text-h6 text-green')
                        with ui.scroll_area().classes('h-64 border p-2'):
                            for item in new_data:
                                ui.label(f"📌 {item['title']}").classes('font-bold')
                                ui.label(f"{item['outline']}").classes('text-sm text-grey q-mb-sm')
                        with ui.row().classes('w-full justify-end'):
                            ui.button('放弃', on_click=dialog.close).props('flat color=grey')
                            def confirm():
                                for item in new_data:
                                    state.structure.append({"id": state.structure[-1]['id'] + 1, "title": item['title'], "outline": item['outline'], "summary": ""})
                                run.io_bound(manager.save_structure, state.structure)
                                refresh_sidebar()
                                dialog.close()
                                ui.notify('大纲已导入！', type='positive')
                            ui.button('确认导入', on_click=confirm).props('color=green')
                    dialog.open()
                except Exception as e:
                    ui.notify('格式解析失败', type='negative')
            ui.button('开始规划', on_click=run_architect_wrapper).props('color=purple icon=psychology')

        # --- Tab 4: 时间轴 ---
        with ui.tab_panel(tab_timeline).classes('h-full p-4 flex flex-col'):
            with ui.row().classes('w-full justify-between items-center mb-4'):
                ui.label('⏳ 剧情时间轴').classes('text-h6')
                ui.button('🔄 刷新', on_click=refresh_timeline).props('flat icon=refresh')
            
            with ui.scroll_area().classes('w-full flex-grow bg-grey-1 p-4 rounded'):
                ui_refs['timeline_container'] = ui.column().classes('w-full')
                refresh_timeline()

    # 启动加载
    await load_chapter(0)
    await refresh_total_word_count()

ui.run(title='AI Novel Studio', port=8080, reload=False)