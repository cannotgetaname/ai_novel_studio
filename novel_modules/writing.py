from nicegui import ui, run
import backend
import json
from .state import app_state, ui_refs, manager, memory, CFG
from . import timeline  # 【关键】导入 timeline 模块以使用 analyze_time

# ================= 辅助函数 =================

def update_char_count():
    if ui_refs['editor_content'] and ui_refs['char_count']:
        text = ui_refs['editor_content'].value or ""
        ui_refs['char_count'].set_text(f"当前章节字数: {len(text)}")

# ================= 核心章节逻辑 =================

async def load_chapter(index):
    if not app_state.structure: return
    if index < 0: index = 0
    if index >= len(app_state.structure): index = len(app_state.structure) - 1
    
    app_state.current_chapter_idx = index
    chapter = app_state.structure[index]
    
    content = await run.io_bound(manager.load_chapter_content, chapter['id'])
    app_state.current_content = content
    
    # 更新 UI
    if ui_refs['editor_title']: ui_refs['editor_title'].value = chapter['title']
    if ui_refs['editor_outline']: ui_refs['editor_outline'].value = chapter['outline']
    if ui_refs['editor_content']: ui_refs['editor_content'].value = content
    
    # 加载审稿意见
    if ui_refs['review_panel']:
        ui_refs['review_panel'].clear()
        report = chapter.get('review_report', '')
        with ui_refs['review_panel']:
            if report: ui.markdown(report).classes('w-full text-sm p-2')
            else: ui.label("暂无审稿记录").classes('text-grey italic p-2')
        
        if report and ui_refs['right_tabs']: ui_refs['right_tabs'].set_value(ui_refs['tab_rev'])
        elif ui_refs['right_tabs']: ui_refs['right_tabs'].set_value(ui_refs['tab_ctx'])

    # 加载时间信息
    time_info = chapter.get('time_info', {"label": "未知", "events": []})
    if ui_refs['time_label']: ui_refs['time_label'].value = time_info.get('label', '未知')
    if ui_refs['time_events']: 
        events = time_info.get('events', [])
        ui_refs['time_events'].value = "\n".join(events) if isinstance(events, list) else str(events)

    update_char_count()
    if app_state.refresh_sidebar: app_state.refresh_sidebar()

async def save_current_chapter():
    chapter = app_state.get_current_chapter()
    if not chapter: return
    
    chapter['title'] = ui_refs['editor_title'].value
    chapter['outline'] = ui_refs['editor_outline'].value
    new_content = ui_refs['editor_content'].value
    
    events_list = [e.strip() for e in ui_refs['time_events'].value.split('\n') if e.strip()]
    chapter['time_info'] = {
        "label": ui_refs['time_label'].value,
        "duration": chapter.get('time_info', {}).get('duration', '-'),
        "events": events_list
    }
    
    ui.notify('正在保存...', type='info')
    await run.io_bound(manager.save_chapter_content, chapter['id'], new_content)
    await run.io_bound(manager.save_structure, app_state.structure)
    await run.io_bound(memory.add_chapter_memory, chapter['id'], new_content)
    
    ui.notify('保存成功！', type='positive')
    if app_state.refresh_sidebar: app_state.refresh_sidebar()
    timeline.refresh_timeline() # 刷新时间轴
    if app_state.refresh_total_word_count: await app_state.refresh_total_word_count()

async def generate_content():
    chapter = app_state.get_current_chapter()
    title = ui_refs['editor_title'].value
    outline = ui_refs['editor_outline'].value
    
    if ui_refs['right_tabs']: ui_refs['right_tabs'].set_value(ui_refs['tab_ctx'])
    ui.notify(f'正在执行智能检索...', type='info')
    
    query = f"{title} {outline}"
    if len(query) < 5: query = f"{title} {app_state.settings['world_view'][:50]}"
    
    filtered_context, debug_info = await run.io_bound(manager.smart_rag_pipeline, query, chapter['id'], memory)
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
    
    prompt = f"【世界观】{app_state.settings['world_view']}\n【本章相关资料】{char_prompt_str}\n【历史背景资料 (已清洗)】{filtered_context}\n【本章大纲】标题：{title}\n内容：{outline}\n请撰写正文。"
    ui.notify('AI 正在思考...', type='info', spinner=True)
    res = await run.io_bound(backend.sync_call_llm, prompt, CFG['prompts']['writer_system'], task_type="writer")
    
    if "Error" in res: ui.notify(res, type='negative')
    else:
        ui_refs['editor_content'].value = res
        update_char_count()
        ui.notify('生成完毕！', type='positive')

async def add_new_chapter():
    last_id = app_state.structure[-1]['id'] if app_state.structure else 0
    new_id = last_id + 1
    new_chap = {"id": new_id, "title": f"第{new_id}章", "outline": "待补充", "summary": "", "time_info": {"label": "未知", "events": []}}
    app_state.structure.append(new_chap)
    await run.io_bound(manager.save_structure, app_state.structure)
    await load_chapter(len(app_state.structure) - 1)

async def delete_current_chapter():
    if len(app_state.structure) <= 1: ui.notify('至少保留一章', type='warning'); return
    idx = app_state.current_chapter_idx
    chap_id = app_state.structure[idx]['id']
    await run.io_bound(manager.delete_chapter, chap_id)
    await run.io_bound(memory.delete_chapter_memory, chap_id)
    del app_state.structure[idx]
    await run.io_bound(manager.save_structure, app_state.structure)
    await load_chapter(max(0, idx - 1))
    ui.notify('章节及记忆已删除', type='negative')

async def export_novel():
    ui.notify('正在打包全书...', spinner=True)
    full_text = await run.io_bound(backend.export_full_novel, manager)
    ui.download(full_text.encode('utf-8'), 'my_novel.txt')
    ui.notify('下载已开始', type='positive')

# ================= 弹窗逻辑 (重绘/审稿/状态) =================

async def open_rewrite_dialog():
    js_code = "var t = document.querySelector('.main-editor textarea'); return t ? [t.selectionStart, t.selectionEnd] : [0,0];"
    try: selection = await ui.run_javascript(js_code)
    except: return
    start, end = selection[0], selection[1]
    full_text = ui_refs['editor_content'].value or ""
    selected_text = full_text[start:end]
    if not selected_text.strip(): ui.notify('请先选中文字', type='warning'); return

    with ui.dialog() as dialog, ui.card().classes('w-1/2'):
        ui.label('✨ 局部重绘').classes('text-h6')
        ui.label(selected_text[:100]+"...").classes('text-sm italic bg-grey-2 p-2 w-full rounded')
        instruction = ui.input('修改要求').classes('w-full')
        async def confirm():
            ui.notify('AI 重写中...', spinner=True); dialog.close()
            pre, post = full_text[:start], full_text[end:]
            new_text = await run.io_bound(backend.sync_rewrite_llm, selected_text, pre, post, instruction.value)
            if "Error" in new_text: ui.notify('失败', type='negative')
            else:
                ui_refs['editor_content'].value = pre + new_text + post
                ui.notify('完成', type='positive')
        ui.button('开始重写', on_click=confirm).props('color=purple')
    dialog.open()

async def open_review_dialog():
    content = ui_refs['editor_content'].value
    if not content or len(content) < 50: ui.notify('正文太短', type='warning'); return
    ui.notify('主编正在审稿...', spinner=True)
    
    ctx = f"【世界观】{app_state.settings['world_view']}\n"
    for c in app_state.characters: ctx += f"- {c['name']}: {c['status']}, {c['role']}\n"
    
    report = await run.io_bound(backend.sync_review_chapter, content, ctx)
    
    idx = app_state.current_chapter_idx
    app_state.structure[idx]['review_report'] = report
    await run.io_bound(manager.save_structure, app_state.structure)
    
    if ui_refs['review_panel']:
        ui_refs['review_panel'].clear()
        with ui_refs['review_panel']: ui.markdown(report).classes('w-full text-sm p-2')
    if ui_refs['right_tabs']: ui_refs['right_tabs'].set_value(ui_refs['tab_rev'])
    if app_state.refresh_sidebar: app_state.refresh_sidebar()
    
    with ui.dialog() as d, ui.card().classes('w-2/3 h-3/4'):
        ui.label('📋 审稿报告').classes('text-h6')
        with ui.scroll_area().classes('w-full flex-grow'): ui.markdown(report)
    d.open()

# 【补全】状态自动结算逻辑
async def open_state_audit_dialog():
    content = ui_refs['editor_content'].value
    if not content or len(content) < 50: ui.notify('正文太短', type='warning'); return
    ui.notify('正在审计世界状态...', spinner=True)
    
    summary = {
        "existing_chars": [c['name'] for c in app_state.characters],
        "existing_items": [i['name'] for i in app_state.items],
        "existing_locs": [l['name'] for l in app_state.locations]
    }
    res = await run.io_bound(backend.sync_analyze_state, content, json.dumps(summary, ensure_ascii=False))
    
    try:
        clean = res.replace("```json", "").replace("```", "").strip()
        start, end = clean.find('{'), clean.rfind('}')
        if start == -1: raise ValueError
        changes = json.loads(clean[start:end+1])
        
        with ui.dialog() as d, ui.card().classes('w-2/3 h-3/4'):
            ui.label('🌍 状态结算单').classes('text-h6')
            with ui.scroll_area().classes('w-full flex-grow border p-2'):
                selected = {"char_updates":[], "item_updates":[], "new_chars":[], "new_items":[], "new_locs":[], "relation_updates":[]}
                
                def render_sec(title, key, items, fmt):
                    if items:
                        ui.label(title).classes('font-bold mt-2 text-blue-600')
                        for it in items:
                            selected[key].append(it)
                            def chk(e, x=it, k=key): 
                                if e.value: selected[k].append(x)
                                else: selected[k].remove(x)
                            ui.checkbox(fmt(it), value=True, on_change=chk).classes('text-sm')

                render_sec("👤 人物变更", "char_updates", changes.get('char_updates', []), lambda x: f"{x['name']} [{x['field']}] -> {x['new_value']}")
                render_sec("🕸️ 关系变更", "relation_updates", changes.get('relation_updates', []), lambda x: f"{x['source']}->{x['target']}: {x['type']}")
                render_sec("📦 物品变更", "item_updates", changes.get('item_updates', []), lambda x: f"{x['name']} [{x['field']}] -> {x['new_value']}")
                render_sec("🆕 新人物", "new_chars", changes.get('new_chars', []), lambda x: f"[新] {x['name']} ({x.get('role','')})")
                render_sec("🆕 新物品", "new_items", changes.get('new_items', []), lambda x: f"[新] {x['name']} ({x.get('type','')})")
                render_sec("🆕 新地点", "new_locs", changes.get('new_locs', []), lambda x: f"[新] {x['name']} ({x.get('desc','')[:20]}...)")

            async def apply():
                from . import settings # 延迟导入防止循环
                logs = await run.io_bound(backend.apply_state_changes, manager, selected)
                # 重新加载数据
                app_state.characters = await run.io_bound(manager.load_characters)
                app_state.items = await run.io_bound(manager.load_items)
                app_state.locations = await run.io_bound(manager.load_locations)
                settings.refresh_char_ui()
                settings.refresh_item_ui()
                settings.refresh_loc_ui()
                d.close()
                ui.notify(f'应用 {len(logs)} 项变更', type='positive')
            
            ui.button('确认执行', on_click=apply).props('color=green')
        d.open()
    except: ui.notify('解析失败', type='negative')

# ================= 【补全】UI 构建函数 =================

def create_writing_tab():
    with ui.splitter(value=75).classes('w-full h-full') as splitter:
        with splitter.before:
            with ui.column().classes('w-full h-full p-4'):
                # 时间信息
                with ui.row().classes('w-full items-center gap-2 mb-2'):
                    ui_refs['time_label'] = ui.input('当前时间点', placeholder='如：修仙历1024年').classes('w-1/3')
                    # 【关键】绑定 timeline.analyze_time
                    ui.button('⏱️ 分析时间', on_click=timeline.analyze_time).props('size=sm color=teal')
                
                ui_refs['time_events'] = ui.textarea('本章关键事件', placeholder='一行一个').classes('w-full').props('rows=2')

                ui_refs['editor_title'] = ui.input(label='章节标题').classes('w-full')
                ui_refs['editor_outline'] = ui.textarea(label='本章大纲').classes('w-full').props('rows=3')
                
                with ui.row().classes('items-center'):
                    ui.button('🚀 生成', on_click=generate_content).props('color=primary')
                    ui.button('💾 保存', on_click=save_current_chapter).props('color=green')
                    ui.button('🌍 结算', on_click=open_state_audit_dialog).props('color=blue outline')
                    ui.button('✨ 重绘', on_click=open_rewrite_dialog).props('color=purple outline')
                    ui.button('🔍 审稿', on_click=open_review_dialog).props('color=orange outline')
                    ui_refs['char_count'] = ui.label('字数: 0').classes('ml-4 text-grey-7')
                
                ui_refs['editor_content'] = ui.textarea(label='正文') \
                    .classes('w-full h-full font-mono main-editor') \
                    .props('rows=20 borderless spellcheck="false" input-style="line-height: 2.0; font-size: 16px;"') \
                    .on_value_change(update_char_count)
        
        with splitter.after:
            with ui.column().classes('w-full h-full p-0 bg-blue-50'):
                with ui.tabs().classes('w-full bg-blue-100 text-grey-8') as right_tabs:
                    ui_refs['right_tabs'] = right_tabs
                    ui_refs['tab_ctx'] = ui.tab('上下文')
                    ui_refs['tab_rev'] = ui.tab('审稿意见')

                with ui.tab_panels(right_tabs, value=ui_refs['tab_ctx']).classes('w-full flex-grow bg-transparent').props('keep-alive animated vertical'):
                    with ui.tab_panel(ui_refs['tab_ctx']).classes('w-full h-full p-0 flex flex-col'):
                        with ui.scroll_area().classes('w-full flex-grow p-2'):
                            ui_refs['rag_debug'] = ui.column().classes('w-full')
                    with ui.tab_panel(ui_refs['tab_rev']).classes('w-full h-full p-0 flex flex-col'):
                        with ui.scroll_area().classes('w-full flex-grow p-2'):
                            ui_refs['review_panel'] = ui.column().classes('w-full')
                            ui.label("暂无记录").classes('text-grey italic')