from nicegui import ui, run
import backend
import json
import asyncio
import uuid
import time
from datetime import datetime
from .state import app_state, ui_refs, manager, memory, CFG
from . import timeline

last_backup_time = 0

# ================= 全局变量 =================
auto_save_timer = None
is_loading = False  # 【核心修复】加载锁：防止加载数据时触发自动保存
is_undo_redo_operation = False  # 【修复】撤销/重做操作标记：必须在 handle_text_change 使用前定义

# ================= 辅助函数 =================

def update_char_count():
    """更新当前章节字数统计"""
    char_count_ref = ui_refs.get('char_count')
    content_ref = ui_refs.get('editor_content')

    if content_ref is not None and char_count_ref is not None:
        text = content_ref.value or ""
        stats = backend.count_words(text)
        # 显示格式: 总字数(中文字) / 总字符
        char_count_ref.set_text(f"字数: {stats['total_words']:,} (汉字{stats['chinese']:,})")


def refresh_foreshadow_warning_ui():
    """刷新伏笔提醒 UI - 在写作时显示需要回收的伏笔"""
    container = ui_refs.get('foreshadow_warning_panel')
    if not container:
        return

    container.clear()

    try:
        from novel_modules.foreshadowing import ForeshadowManager
        project_path = manager.project_root if hasattr(manager, 'project_root') else None

        if not project_path:
            with container:
                ui.label('请先加载项目').classes('text-grey-5 italic')
            return

        fs_mgr = ForeshadowManager(project_path)
        current_chapter = app_state.current_chapter_idx + 1 if hasattr(app_state, 'current_chapter_idx') else 0

        # 获取预警伏笔
        warnings = fs_mgr.check_warnings(current_chapter)

        with container:
            # 当前章节提示
            ui.label(f'当前写作: 第 {current_chapter} 章').classes('text-sm text-grey-6 mb-2')

            if not warnings:
                with ui.card().classes('w-full p-3 bg-green-50'):
                    ui.label('✅ 当前无伏笔预警').classes('text-green-600')
                    ui.label('所有活跃伏笔状态正常').classes('text-sm text-grey-5')
            else:
                # 预警卡片
                with ui.card().classes('w-full p-2 bg-red-50 mb-2'):
                    with ui.row().classes('w-full items-center gap-2'):
                        ui.icon('warning', color='red').classes('text-lg')
                        ui.label(f'⚠️ 有 {len(warnings)} 个伏笔需要关注').classes('text-red-600 font-bold')

                for w in warnings[:5]:  # 只显示前5个
                    with ui.card().classes('w-full p-2 bg-white mb-1 border'):
                        # 类型标签
                        type_colors = {'物品': 'purple', '人物': 'blue', '剧情': 'green', '悬念': 'orange'}
                        type_badge_color = type_colors.get(w.get('type', '剧情'), 'grey')

                        with ui.row().classes('w-full items-center gap-2'):
                            ui.badge(w.get('type', '剧情'), color=type_badge_color).props('dense')
                            importance_colors = {'high': 'red', 'medium': 'orange', 'low': 'grey'}
                            ui.badge(w.get('importance', 'medium'), color=importance_colors.get(w.get('importance', 'medium'), 'grey')).props('dense')
                            ui.label(w['content'][:35]).classes('text-sm font-bold flex-grow')

                        ui.label(w.get('warning_message', '')).classes('text-xs text-red-500 mt-1')

                        with ui.row().classes('w-full justify-between items-center mt-1'):
                            ui.label(f"埋设: 第{w['source_chapter']}章 | 已过 {w.get('chapters_since', '?')} 章").classes('text-xs text-grey-5')
                            ui.button('标记回收', on_click=lambda fid=w['id']: quick_resolve_foreshadow(fid)).props('size=sm flat color=blue')

            # 显示本章埋设的伏笔
            chapter_foreshadows = fs_mgr.get_foreshadows_by_chapter(current_chapter, mode='source')
            if chapter_foreshadows:
                with ui.expansion(f'📖 本章埋设 ({len(chapter_foreshadows)}个)', icon='lightbulb').classes('w-full bg-yellow-50 mt-2'):
                    with ui.column().classes('w-full p-2'):
                        for fs in chapter_foreshadows:
                            with ui.row().classes('w-full items-center gap-2'):
                                ui.label(f"• {fs['content'][:30]}").classes('text-sm')
                                if fs['status'] == 'resolved':
                                    ui.badge('已回收', color='blue').props('dense')

            # 快速操作按钮
            with ui.row().classes('w-full justify-end mt-2'):
                ui.button('管理伏笔', on_click=lambda: ui_refs['foreshadow_status_filter'] and None).props('size=sm flat')  # 切换到设定页面的伏笔标签

    except Exception as e:
        with container:
            ui.label(f'加载伏笔失败: {str(e)}').classes('text-red-5')


def quick_resolve_foreshadow(foreshadow_id):
    """快速标记伏笔回收"""
    try:
        from novel_modules.foreshadowing import ForeshadowManager
        project_path = manager.project_root if hasattr(manager, 'project_root') else None

        if project_path:
            fs_mgr = ForeshadowManager(project_path)
            current_chapter = app_state.current_chapter_idx + 1 if hasattr(app_state, 'current_chapter_idx') else 0

            fs_mgr.resolve_foreshadow(foreshadow_id, current_chapter)
            ui.notify('已标记回收', type='positive')
            refresh_foreshadow_warning_ui()

    except Exception as e:
        ui.notify(f'操作失败: {str(e)}', type='warning')

# 执行自动保存
async def perform_auto_save():
    # 【双重保险】如果标题为空，坚决不保存！防止覆盖成空数据
    title_ref = ui_refs.get('editor_title')
    if title_ref is None or not title_ref.value:
        return

    chapter = app_state.get_current_chapter()
    if not chapter: return

    title = title_ref.value if title_ref is not None else ""
    outline_ref = ui_refs.get('editor_outline')
    outline = outline_ref.value if outline_ref is not None else ""
    content_ref = ui_refs.get('editor_content')
    content = content_ref.value if content_ref is not None else ""

    # 更新内存
    chapter['title'] = title
    chapter['outline'] = outline

    # 写入磁盘（同时更新段落结构）
    paragraphs = manager.text_to_paragraphs(content)
    await run.io_bound(manager.save_chapter_paragraphs, chapter['id'], paragraphs)
    await run.io_bound(manager.save_structure, app_state.structure)

    # 记录写作进度（自动保存时也记录字数）
    from novel_modules.goals import record_writing_progress
    word_count = backend.count_words(content)['total_words']
    record_writing_progress(words=word_count, book_name=app_state.current_book_name)

    save_status_ref = ui_refs.get('save_status')
    if save_status_ref:
        now_str = datetime.now().strftime("%H:%M:%S")
        save_status_ref.set_text(f"☁️ 已自动保存 ({now_str})")
        save_status_ref.classes('text-green-600')
        # 使用闭包捕获 save_status_ref，避免多次 get 调用
        def clear_save_status(ref=save_status_ref):
            if ref is not None:
                ref.set_text('')
        ui.timer(3.0, clear_save_status, once=True)

async def run_auto_backup_check():
    global last_backup_time

    # 获取配置的间隔 (默认 30 分钟)
    interval_min = CFG.get('backup_interval', 30)
    if interval_min <= 0: return # 0 表示关闭

    interval_sec = interval_min * 60
    now = time.time()
    
    if now - last_backup_time > interval_sec:
        ui.notify('正在后台执行全项目备份...', type='info', position='bottom-right')
        res = await run.io_bound(manager.create_project_backup)
        last_backup_time = now
        ui.notify(res, type='positive', position='bottom-right')

# 处理文本变更
def handle_text_change(e):
    global auto_save_timer

    # 【核心修复】如果是程序正在加载章节或执行撤销重做，忽略这次变更
    if is_loading or is_undo_redo_operation:
        return

    update_char_count()

    # 保存当前状态到撤销栈
    save_current_state()

    if auto_save_timer:
        auto_save_timer.cancel()

    auto_save_timer = ui.timer(3.0, perform_auto_save, once=True)

    save_status_ref = ui_refs.get('save_status')
    if save_status_ref:
        save_status_ref.set_text("✍️ 输入中...")
        save_status_ref.classes('text-orange-400')

def save_current_state():
    """保存当前编辑状态到撤销栈"""
    global is_loading, is_undo_redo_operation  # 使用全局变量来临时标记，但要小心控制范围

    # 只有在非加载状态下才保存状态
    # 并且不在撤销/重做操作期间
    if not is_loading and not is_undo_redo_operation:
        # 获取当前所有编辑字段的值，使用安全的引用检查
        title_ref = ui_refs.get('editor_title')
        outline_ref = ui_refs.get('editor_outline')
        content_ref = ui_refs.get('editor_content')
        time_label_ref = ui_refs.get('time_label')
        time_events_ref = ui_refs.get('time_events')

        title = title_ref.value if title_ref is not None else ""
        outline = outline_ref.value if outline_ref is not None else ""
        content = content_ref.value if content_ref is not None else ""
        time_label = time_label_ref.value if time_label_ref is not None else ""
        time_events = time_events_ref.value if time_events_ref is not None else ""

        # 只有当内容发生实质变化时才保存状态（防抖）
        if (not app_state.undo_stack or
            app_state.undo_stack[-1]['content'] != content or
            app_state.undo_stack[-1]['title'] != title or
            app_state.undo_stack[-1]['outline'] != outline):
            # 保存状态到撤销栈
            app_state.save_state_for_undo(title, outline, content, time_label, time_events)

# 全局标志，标记是否正在执行撤销/重做操作（已在文件开头定义）
# is_undo_redo_operation = False  # 注释掉冗余定义

async def undo_action():
    """执行撤销操作"""
    global is_loading, is_undo_redo_operation

    if not app_state.can_undo():
        ui.notify('没有可撤销的操作', type='info')
        return

    # 在执行撤销前，先把当前状态保存到重做栈
    # 使用安全的UI引用检查
    title_ref = ui_refs.get('editor_title')
    outline_ref = ui_refs.get('editor_outline')
    content_ref = ui_refs.get('editor_content')
    time_label_ref = ui_refs.get('time_label')
    time_events_ref = ui_refs.get('time_events')

    current_title = title_ref.value if title_ref is not None else ""
    current_outline = outline_ref.value if outline_ref is not None else ""
    current_content = content_ref.value if content_ref is not None else ""
    current_time_label = time_label_ref.value if time_label_ref is not None else ""
    current_time_events = time_events_ref.value if time_events_ref is not None else ""

    # 将当前状态保存到重做栈
    state_to_redo = {
        'title': current_title,
        'outline': current_outline,
        'content': current_content,
        'time_label': current_time_label,
        'time_events': current_time_events,
        'chapter_idx': app_state.current_chapter_idx
    }
    app_state.save_state_to_redo(state_to_redo)

    # 标记正在进行撤销/重做操作
    is_undo_redo_operation = True
    is_loading = True  # 使用现有的is_loading标志来防止handle_text_change被触发

    try:
        # 获取要撤销的状态
        state_to_restore = app_state.undo_state()
        if state_to_restore:
            # 更新UI控件，使用安全的UI引用检查
            title_ref = ui_refs.get('editor_title')
            if title_ref is not None:
                title_ref.value = state_to_restore['title']

            outline_ref = ui_refs.get('editor_outline')
            if outline_ref is not None:
                outline_ref.value = state_to_restore['outline']

            content_ref = ui_refs.get('editor_content')
            if content_ref is not None:
                content_ref.value = state_to_restore['content']

            time_label_ref = ui_refs.get('time_label')
            if time_label_ref is not None:
                time_label_ref.value = state_to_restore['time_label']

            time_events_ref = ui_refs.get('time_events')
            if time_events_ref is not None:
                time_events_ref.value = state_to_restore['time_events']

            # 更新字数统计
            update_char_count()

            ui.notify('✅ 已撤销', type='positive')
        else:
            ui.notify('撤销操作失败', type='negative')
    finally:
        is_loading = False
        is_undo_redo_operation = False

async def redo_action():
    """执行重做操作"""
    global is_loading, is_undo_redo_operation

    if not app_state.can_redo():
        ui.notify('没有可重做的操作', type='info')
        return

    # 在执行重做前，先把当前状态保存到撤销栈
    # 使用安全的UI引用检查
    title_ref = ui_refs.get('editor_title')
    outline_ref = ui_refs.get('editor_outline')
    content_ref = ui_refs.get('editor_content')
    time_label_ref = ui_refs.get('time_label')
    time_events_ref = ui_refs.get('time_events')

    current_title = title_ref.value if title_ref is not None else ""
    current_outline = outline_ref.value if outline_ref is not None else ""
    current_content = content_ref.value if content_ref is not None else ""
    current_time_label = time_label_ref.value if time_label_ref is not None else ""
    current_time_events = time_events_ref.value if time_events_ref is not None else ""

    # 将当前状态保存到撤销栈
    state_to_undo = {
        'title': current_title,
        'outline': current_outline,
        'content': current_content,
        'time_label': current_time_label,
        'time_events': current_time_events,
        'chapter_idx': app_state.current_chapter_idx
    }
    app_state.save_state_to_undo(state_to_undo)

    is_undo_redo_operation = True
    is_loading = True  # 防止handle_text_change被触发

    try:
        # 获取要重做的状态
        state_to_restore = app_state.redo_state()
        if state_to_restore:
            # 更新UI控件，使用安全的UI引用检查
            title_ref = ui_refs.get('editor_title')
            if title_ref is not None:
                title_ref.value = state_to_restore['title']

            outline_ref = ui_refs.get('editor_outline')
            if outline_ref is not None:
                outline_ref.value = state_to_restore['outline']

            content_ref = ui_refs.get('editor_content')
            if content_ref is not None:
                content_ref.value = state_to_restore['content']

            time_label_ref = ui_refs.get('time_label')
            if time_label_ref is not None:
                time_label_ref.value = state_to_restore['time_label']

            time_events_ref = ui_refs.get('time_events')
            if time_events_ref is not None:
                time_events_ref.value = state_to_restore['time_events']

            # 更新字数统计
            update_char_count()

            ui.notify('✅ 已重做', type='positive')
        else:
            ui.notify('重做操作失败', type='negative')
    finally:
        is_loading = False
        is_undo_redo_operation = False

# ================= 分卷与章节管理 (保持不变) =================
# ... (add_new_volume, rename_volume, delete_volume_dialog, add_chapter_to_volume, add_new_chapter_auto, delete_current_chapter 代码与之前相同，此处省略以节省篇幅，请保留您原有的这部分代码) ...

async def add_new_volume():
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('📚 新建分卷').classes('text-h6')
        default_name = f"第{len(app_state.volumes)+1}卷"
        name_input = ui.input('分卷名称', value=default_name).classes('w-full')
        async def confirm():
            if not name_input.value: return
            new_vol_id = f"vol_{str(uuid.uuid4())[:8]}"
            new_vol = {"id": new_vol_id, "title": name_input.value, "order": len(app_state.volumes) + 1}
            app_state.volumes.append(new_vol)
            await run.io_bound(manager.save_volumes, app_state.volumes)
            app_state.expanded_volumes.add(new_vol_id)
            if app_state.refresh_sidebar: app_state.refresh_sidebar()
            dialog.close()
            ui.notify(f'分卷 "{name_input.value}" 已创建', type='positive')
        with ui.row().classes('w-full justify-end'):
            ui.button('取消', on_click=dialog.close).props('flat')
            ui.button('创建', on_click=confirm).props('color=primary')
    dialog.open()

async def rename_volume(vol_id):
    target_vol = next((v for v in app_state.volumes if v['id'] == vol_id), None)
    if not target_vol: return
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('✏️ 重命名分卷').classes('text-h6')
        name_input = ui.input('新名称', value=target_vol['title']).classes('w-full')
        async def confirm():
            if not name_input.value: return
            target_vol['title'] = name_input.value
            await run.io_bound(manager.save_volumes, app_state.volumes)
            if app_state.refresh_sidebar: app_state.refresh_sidebar()
            dialog.close()
            ui.notify('分卷名称已更新', type='positive')
        with ui.row().classes('w-full justify-end'):
            ui.button('取消', on_click=dialog.close).props('flat')
            ui.button('保存', on_click=confirm).props('color=primary')
    dialog.open()

async def delete_volume_dialog():
    with ui.dialog() as dialog, ui.card().classes('w-96'):
        ui.label('🗑️ 删除分卷').classes('text-h6 text-red')
        vol_options = {v['id']: v['title'] for v in app_state.volumes}
        selected_vol = ui.select(vol_options, label='选择要删除的分卷').classes('w-full')
        move_to_default = ui.checkbox('将章节移至默认分卷而不是删除它们', value=True).classes('mt-2')

        async def confirm_del():
            vol_id = selected_vol.value
            if not vol_id: return

            # 获取该分卷中的所有章节
            chapters_to_delete = [c for c in app_state.structure if c['volume_id'] == vol_id]

            if chapters_to_delete:
                if move_to_default.value:
                    # 移动章节到默认分卷
                    default_vol_id = app_state.volumes[0]['id'] if app_state.volumes else 'vol_default'
                    for chap in chapters_to_delete:
                        chap['volume_id'] = default_vol_id
                    await run.io_bound(manager.save_structure, app_state.structure)
                    ui.notify(f'{len(chapters_to_delete)} 个章节已移至默认分卷', type='info')
                else:
                    # 删除该分卷中的所有章节
                    for chap in chapters_to_delete:
                        await run.io_bound(manager.delete_chapter, chap['id'])
                        await run.io_bound(memory.delete_chapter_memory, chap['id'])

                    # 从结构中移除这些章节
                    app_state.structure = [c for c in app_state.structure if c['volume_id'] != vol_id]
                    await run.io_bound(manager.save_structure, app_state.structure)
                    ui.notify(f'{len(chapters_to_delete)} 个章节已随分卷一起删除', type='info')

                    # 如果当前章节属于被删除的分卷，重新加载
                    current_chap = app_state.get_current_chapter()
                    if not current_chap or current_chap['volume_id'] == vol_id:
                        if app_state.structure:
                            await load_chapter(0)
                        else:
                            # 如果所有章节都被删除了，清空编辑器
                            if 'editor_title' in ui_refs and ui_refs['editor_title'] is not None:
                                ui_refs['editor_title'].value = ""
                            if 'editor_outline' in ui_refs and ui_refs['editor_outline'] is not None:
                                ui_refs['editor_outline'].value = ""
                            if 'editor_content' in ui_refs and ui_refs['editor_content'] is not None:
                                ui_refs['editor_content'].value = ""
                            if 'char_count' in ui_refs and ui_refs['char_count'] is not None:
                                ui_refs['char_count'].set_text("当前章节字数: 0")
                            app_state.current_chapter_idx = -1

            # 删除分卷
            vol_idx = next((i for i, v in enumerate(app_state.volumes) if v['id'] == vol_id), None)
            if vol_idx is not None:
                del app_state.volumes[vol_idx]
                await run.io_bound(manager.save_volumes, app_state.volumes)

                # 从展开的分卷列表中移除
                if vol_id in app_state.expanded_volumes:
                    app_state.expanded_volumes.discard(vol_id)

                ui.notify('分卷已删除', type='positive')

            if app_state.refresh_sidebar: app_state.refresh_sidebar()
            dialog.close()

        ui.button('确认删除', on_click=confirm_del).props('color=red w-full')
    dialog.open()

async def add_chapter_to_volume(vol_id=None):
    if not vol_id:
        if app_state.volumes:
            current_chap = app_state.get_current_chapter()
            if current_chap: vol_id = current_chap.get('volume_id', app_state.volumes[-1]['id'])
            else: vol_id = app_state.volumes[-1]['id']
        else:
            ui.notify('请先新建分卷！', type='warning'); return
    last_id = max([c['id'] for c in app_state.structure]) if app_state.structure else 0
    new_id = last_id + 1
    insert_index = len(app_state.structure)
    vol_indices = [i for i, c in enumerate(app_state.structure) if c.get('volume_id') == vol_id]
    if vol_indices: insert_index = vol_indices[-1] + 1
    new_chap = {"id": new_id, "title": f"第{new_id}章", "volume_id": vol_id, "outline": "待补充", "summary": "", "time_info": {"label": "未知", "events": []}}
    app_state.structure.insert(insert_index, new_chap)
    await run.io_bound(manager.save_structure, app_state.structure)
    await load_chapter(insert_index)
    ui.notify(f'已在当前卷末尾创建第{new_id}章', type='positive')

async def add_new_chapter_auto(): await add_chapter_to_volume(None)

async def delete_current_chapter():
    idx = app_state.current_chapter_idx
    chap_id = app_state.structure[idx]['id']
    with ui.dialog() as dialog, ui.card():
        ui.label(f'确认删除第 {chap_id} 章？').classes('text-h6')
        ui.label('注意：这是最后一个章节时也会被删除').classes('text-red text-sm')
        async def confirm():
            await run.io_bound(manager.delete_chapter, chap_id)
            await run.io_bound(memory.delete_chapter_memory, chap_id)
            del app_state.structure[idx]
            await run.io_bound(manager.save_structure, app_state.structure)

            # 如果还有章节，则加载相邻章节，否则清空编辑器
            if app_state.structure:
                new_idx = min(idx, len(app_state.structure)-1)
                new_idx = max(0, new_idx)
                await load_chapter(new_idx)
            else:
                # 没有章节时清空编辑器内容
                if 'editor_title' in ui_refs and ui_refs['editor_title'] is not None:
                    ui_refs['editor_title'].value = ""
                if 'editor_outline' in ui_refs and ui_refs['editor_outline'] is not None:
                    ui_refs['editor_outline'].value = ""
                if 'editor_content' in ui_refs and ui_refs['editor_content'] is not None:
                    ui_refs['editor_content'].value = ""
                if 'char_count' in ui_refs and ui_refs['char_count'] is not None:
                    ui_refs['char_count'].set_text("当前章节字数: 0")
                app_state.current_chapter_idx = -1

            ui.notify('章节已删除', type='negative')
            if app_state.refresh_sidebar: app_state.refresh_sidebar()
            dialog.close()
        ui.button('确认删除', on_click=confirm).props('color=red')
    dialog.open()

# ================= 核心章节逻辑 (关键修改) =================

async def load_chapter(index):
    global auto_save_timer, is_loading
    
    # 1. 切换前强制保存（只在非加载状态下）
    if auto_save_timer:
        auto_save_timer.cancel()
        auto_save_timer = None
        await perform_auto_save()

    if not app_state.structure:
        ui.notify('没有章节结构数据', type='negative')
        return
    if index < 0: index = 0
    if index >= len(app_state.structure): index = len(app_state.structure) - 1
    
    # 2. 【核心修复】开启加载锁
    is_loading = True
    
    try:
        app_state.current_chapter_idx = index
        chapter = app_state.structure[index]
        
        content = await run.io_bound(manager.load_chapter_content, chapter['id'])
        app_state.current_content = content
        
        # 更新 UI (此时 is_loading=True，handle_text_change 会忽略这些变更)
        # 【修复】使用更安全的UI引用检查方法
        if 'editor_title' in ui_refs and ui_refs['editor_title'] is not None:
            title_ref = ui_refs['editor_title']
            title_ref.value = chapter['title']
        if 'editor_outline' in ui_refs and ui_refs['editor_outline'] is not None:
            outline_ref = ui_refs['editor_outline']
            outline_ref.value = chapter['outline']
        if 'editor_content' in ui_refs and ui_refs['editor_content'] is not None:
            content_ref = ui_refs['editor_content']
            content_ref.value = content
        
        if 'save_status' in ui_refs and ui_refs['save_status'] is not None:
            status_ref = ui_refs['save_status']
            status_ref.set_text("")

        if 'review_panel' in ui_refs and ui_refs['review_panel'] is not None:
            panel_ref = ui_refs['review_panel']
            panel_ref.clear()
            review_data = chapter.get('review_data', {})

            with ui_refs['review_panel']:
                if review_data and review_data.get('issues'):
                    overall = review_data.get('overall_score', 0)
                    dim_scores = review_data.get('dimension_scores', {})
                    stats = review_data.get('statistics', {})

                    ui.label(f"📊 综合评分: {overall}/10").classes('text-lg font-bold mb-2')

                    # 如果已修复，显示修复信息
                    if review_data.get('fixed_at'):
                        ui.label(f"✅ 已于 {review_data['fixed_at'][:10]} 修复 {review_data.get('fixed_count', 0)} 个问题").classes('text-xs text-green-600 mb-2')

                    # 各维度评分
                    if dim_scores:
                        with ui.row().classes('gap-2 mb-2'):
                            for dim, score in dim_scores.items():
                                if score > 0:
                                    color = 'green' if score >= 8 else ('orange' if score >= 6 else 'red')
                                    ui.badge(f"{dim}:{score}", color=color).props('rounded')

                    # 问题统计
                    if stats:
                        ui.label(f"问题: 严重{stats.get('severe', 0)} 中等{stats.get('medium', 0)} 轻微{stats.get('minor', 0)}").classes('text-xs text-grey-6')

                    # 主要问题列表（折叠）
                    issues = review_data.get('issues', [])
                    if issues:
                        with ui.expansion(f"查看全部 {len(issues)} 个问题", icon='list').classes('w-full mt-2'):
                            for issue in issues[:10]:
                                severity = issue.get('severity', '轻微')
                                color = {'严重': 'red', '中等': 'orange', '轻微': 'grey'}.get(severity, 'grey')
                                with ui.row().classes('items-start gap-1 mb-1'):
                                    ui.badge(severity, color=color).props('dense size=xs')
                                    ui.label(f"[段{issue.get('paragraph_id', '?')}] {issue.get('description', '')[:30]}...").classes('text-xs')
                else:
                    ui.label("暂无审稿记录，点击「审稿」按钮开始").classes('text-grey italic p-2')

            # 切换到审稿意见tab
            tabs_ref = ui_refs.get('right_tabs')
            tab_rev_ref = ui_refs.get('tab_rev')
            if tabs_ref is not None and tab_rev_ref is not None:
                tabs_ref.set_value(tab_rev_ref)
            elif 'right_tabs' in ui_refs and ui_refs['right_tabs'] is not None and 'tab_ctx' in ui_refs and ui_refs['tab_ctx'] is not None:
                tabs_ref = ui_refs.get('right_tabs')
                tab_ctx_ref = ui_refs.get('tab_ctx')
                if tabs_ref is not None and tab_ctx_ref is not None:
                    tabs_ref.set_value(tab_ctx_ref)

        time_info = chapter.get('time_info', {"label": "未知", "events": []})
        if 'time_label' in ui_refs and ui_refs['time_label'] is not None:
            label_ref = ui_refs['time_label']
            label_ref.value = time_info.get('label', '未知')
        if 'time_events' in ui_refs and ui_refs['time_events'] is not None:
            events = time_info.get('events', [])
            events_ref = ui_refs['time_events']
            events_ref.value = "\n".join(events) if isinstance(events, list) else str(events)

        update_char_count()
        if app_state.refresh_sidebar: app_state.refresh_sidebar()
        
    finally:
        # 3. 【核心修复】关闭加载锁
        # 使用 asyncio.sleep(0) 让出控制权，确保 UI 更新事件处理完毕后再解锁
        await asyncio.sleep(0.01)  # 减少延迟时间以提高响应性
        is_loading = False

async def save_current_chapter():
    global auto_save_timer
    if auto_save_timer: auto_save_timer.cancel()

    chapter = app_state.get_current_chapter()
    if not chapter: return

    title_ref = ui_refs.get('editor_title')
    outline_ref = ui_refs.get('editor_outline')
    content_ref = ui_refs.get('editor_content')
    time_label_ref = ui_refs.get('time_label')
    time_events_ref = ui_refs.get('time_events')

    chapter['title'] = title_ref.value if title_ref is not None else ""
    chapter['outline'] = outline_ref.value if outline_ref is not None else ""
    new_content = content_ref.value if content_ref is not None else ""

    events_list = [e.strip() for e in time_events_ref.value.split('\n') if e.strip()] if time_events_ref is not None else []
    chapter['time_info'] = {
        "label": time_label_ref.value if time_label_ref is not None else "",
        "duration": chapter.get('time_info', {}).get('duration', '-'),
        "events": events_list
    }

    ui.notify('正在执行完整保存...', type='info')
    print(f"\n[完整保存] 章节: 第{chapter['id']}章 - {chapter.get('title', '未命名')}")
    print(f"[完整保存] 标题: {chapter['title']}")
    print(f"[完整保存] 大纲长度: {len(chapter['outline'])}")
    print(f"[完整保存] 正文长度: {len(new_content)}")

    # 保存内容（同时更新段落结构）
    paragraphs = manager.text_to_paragraphs(new_content)
    await run.io_bound(manager.save_chapter_paragraphs, chapter['id'], paragraphs)
    print("[完整保存] 章节内容和段落结构已写入磁盘")

    # 【新增】创建历史快照
    await run.io_bound(manager.create_chapter_snapshot, chapter['id'], new_content)
    print("[完整保存] 历史快照已创建")

    await run.io_bound(manager.save_structure, app_state.structure)
    print("[完整保存] 目录结构已保存")

    await run.io_bound(memory.add_chapter_memory, chapter['id'], new_content)
    print("[完整保存] RAG记忆库已更新")

    # 【新增】记录写作进度
    from novel_modules.goals import record_writing_progress
    word_count = backend.count_words(new_content)['total_words']
    record_writing_progress(words=word_count, chapters=1, book_name=app_state.current_book_name)
    print(f"[完整保存] 写作进度已记录: {word_count} 字")

    ui.notify('✅ 保存成功！记忆库已更新。', type='positive')
    save_status_ref = ui_refs.get('save_status')
    if save_status_ref: save_status_ref.set_text("✅ 已完整保存")

    current_client = ui.context.client
    async def background_update_summaries(chap_id, text, client):
        print(f"\n[后台任务] 开始生成第{chap_id}章摘要...")
        summary = await run.io_bound(manager.update_chapter_summary, chap_id, text)
        if "Error" not in summary:
            print(f"[后台任务] 第{chap_id}章摘要生成成功")
            with client:
                ui.notify(f'第{chap_id}章摘要已更新', type='positive')
            print("[后台任务] 开始生成全书剧情总纲...")
            global_sum = await run.io_bound(manager.update_global_summary)
            if "Error" not in global_sum:
                print(f"[后台任务] 全书剧情总纲生成成功，长度: {len(global_sum)}")
                app_state.settings['book_summary'] = global_sum
                with client:
                    ui.notify('📚 全书剧情总纲已刷新', type='positive')
            else:
                print(f"[后台任务] 全书剧情总纲生成失败: {global_sum}")
        else:
            print(f"[后台任务] 第{chap_id}章摘要生成失败: {summary}")

    asyncio.create_task(background_update_summaries(chapter['id'], new_content, current_client))

    if app_state.refresh_sidebar: app_state.refresh_sidebar()
    timeline.refresh_timeline()
    if app_state.refresh_total_word_count: await app_state.refresh_total_word_count()

async def generate_content():
    # 1. 获取基本信息
    chapter = app_state.get_current_chapter()
    if not chapter: return

    title_ref = ui_refs.get('editor_title')
    outline_ref = ui_refs.get('editor_outline')
    title = title_ref.value if title_ref is not None else ""
    outline = outline_ref.value if outline_ref is not None else ""

    # 自动切换到上下文 Tab，方便用户看到检索过程
    right_tabs_ref = ui_refs.get('right_tabs')
    tab_ctx_ref = ui_refs.get('tab_ctx')
    if right_tabs_ref and tab_ctx_ref: right_tabs_ref.set_value(tab_ctx_ref)
    ui.notify(f'正在构建多维记忆...', type='info')

    # ---------------------------------------------------------
    # 2. 🧠 Vector RAG (向量检索)：找历史剧情片段
    # ---------------------------------------------------------
    query = f"{title} {outline}"
    if len(query) < 5: query = f"{title} {app_state.settings['world_view'][:50]}"

    # 从 ChromaDB 检索相关切片
    filtered_context, debug_info = await run.io_bound(manager.smart_rag_pipeline, query, chapter['id'], memory)

    # 从 JSON 设定集中获取相关人物 Bio
    context_text_for_chars = f"{title} {outline}"
    char_prompt_str, active_names = manager.get_relevant_context(context_text_for_chars)

    # ---------------------------------------------------------
    # 3. 🕸️ Graph RAG (图谱检索)：找逻辑关系
    # ---------------------------------------------------------
    graph_context = ""
    active_graph_entities = []

    try:
        # 3.1 实例化图引擎并从当前 JSON 状态构建图谱
        # (这是一个轻量级操作，几百个节点毫秒级完成)
        world_graph = backend.WorldGraph(manager)
        await run.io_bound(world_graph.rebuild)

        # 3.2 提取当前大纲中的实体 (关键词匹配)
        full_text_to_scan = f"{title}\n{outline}"

        # 扫描人物
        for c in app_state.characters:
            if c['name'] in full_text_to_scan: active_graph_entities.append(c['name'])
        # 扫描地点
        for l in app_state.locations:
            if l['name'] in full_text_to_scan: active_graph_entities.append(l['name'])
        # 扫描物品
        for i in app_state.items:
            if i['name'] in full_text_to_scan: active_graph_entities.append(i['name'])

        # 去重
        active_graph_entities = list(set(active_graph_entities))

        # 3.3 检索图谱关系 (1跳邻居)
        if active_graph_entities:
            ui.notify(f"图谱激活: {', '.join(active_graph_entities)}", type='info')
            for entity in active_graph_entities:
                info = world_graph.get_context_text(entity, hops=1)
                if info:
                    graph_context += f"【{entity} 的社交/物品关系】\n{info}\n"
    except Exception as e:
        print(f"GraphRAG Error: {e}")
        graph_context = "(图谱构建失败，跳过)"

    # ---------------------------------------------------------
    # 4. 更新 Debug 面板 (让用户看到 AI 拿到了什么)
    # ---------------------------------------------------------
    rag_debug_ref = ui_refs.get('rag_debug')
    if rag_debug_ref:
        rag_debug_ref.clear()
        with rag_debug_ref:
            ui.label("🧠 向量记忆 (历史剧情):").classes('font-bold text-sm text-blue-800')
            ui.label(filtered_context[:300] + "...").classes('text-xs text-grey-600 bg-blue-50 p-2 rounded mb-2')

            ui.label("🕸️ 图谱记忆 (逻辑关系):").classes('font-bold text-sm text-purple-800')
            if graph_context:
                ui.label(graph_context).classes('text-xs text-purple-900 bg-purple-50 p-2 rounded mb-2 whitespace-pre-wrap')
            else:
                ui.label("无活跃关系").classes('text-xs text-grey-400 italic mb-2')

            ui.label("👤 激活设定 (人物卡):").classes('font-bold text-sm text-green-800')
            ui.label(char_prompt_str[:300] + "...").classes('text-xs text-green-800 bg-green-50 p-2 rounded')

    # ---------------------------------------------------------
    # 5. 组装 Prompt 并调用 LLM
    # ---------------------------------------------------------
    book_summary = app_state.settings.get('book_summary', '（暂无全书总结）')

    prompt = f"""
    【世界观设定】
    {app_state.settings['world_view']}

    【全书剧情脉络】
    {book_summary}

    【相关人物档案】
    {char_prompt_str}

    【当前场景关系网 (Graph Memory)】
    {graph_context}

    【历史背景资料 (Vector Memory)】
    {filtered_context}

    ---------------------------------------------------
    【本章写作任务】
    章节标题：{title}
    本章大纲：{outline}

    请基于以上资料，撰写本章正文。
    要求：
    1. 逻辑严密，注意利用【关系网】中的设定（如持有物品、人际恩怨）。
    2. 风格契合世界观，多用展示而非讲述。
    3. 篇幅要求：正文必须在 2000-4000 字之间，请充分展开情节，不要草草收尾。
    4. 细节丰富：每场戏都要有具体的环境描写、人物动作、对话互动。
    """

    ui.notify('AI 正在沉浸式思考...', type='info', spinner=True)

    # 调用 writer 模型 (流式输出)
    content_ref = ui_refs.get('editor_content')
    full_text = ""
    has_error = False

    print(f"\n[写作生成] 章节标题: {title}")
    print(f"[写作生成] 大纲长度: {len(outline)}")
    print(f"[写作生成] 世界观长度: {len(app_state.settings.get('world_view', ''))}")
    print(f"[写作生成] 人物上下文长度: {len(char_prompt_str)}")
    print(f"[写作生成] 图谱上下文长度: {len(graph_context)}")
    print(f"[写作生成] RAG上下文长度: {len(filtered_context)}")

    # 使用后台线程运行流式生成器
    import queue
    import threading

    text_queue = queue.Queue()
    stream_done = object()  # 结束标记

    def run_stream():
        try:
            for chunk in backend.stream_call_llm(prompt, backend.get_prompt('writer_system'), task_type="writer"):
                text_queue.put(chunk)
        except Exception as e:
            print(f"[写作生成] 流式调用异常: {str(e)}")
            text_queue.put(f"Error: {str(e)}")
        finally:
            text_queue.put(stream_done)

    # 启动后台线程
    thread = threading.Thread(target=run_stream, daemon=True)
    thread.start()

    # 在主协程中消费队列并更新UI
    while thread.is_alive() or not text_queue.empty():
        try:
            chunk = text_queue.get(timeout=0.05)
            if chunk is stream_done:
                break
            if chunk.startswith("Error:"):
                ui.notify(chunk, type='negative')
                has_error = True
                break
            full_text += chunk
            if content_ref:
                content_ref.value = full_text
            # 让出控制权，允许UI更新
            await asyncio.sleep(0.01)
        except queue.Empty:
            await asyncio.sleep(0.01)
            continue

    if not has_error:
        update_char_count()
        ui.notify('生成完毕！已融合图谱记忆。', type='positive')

async def open_history_dialog():
    chapter = app_state.get_current_chapter()
    if not chapter: return

    snapshots = await run.io_bound(manager.get_chapter_snapshots, chapter['id'])
    
    with ui.dialog() as dialog, ui.card().classes('w-2/3 h-3/4'):
        ui.label(f'🕰️ 第{chapter["id"]}章 - 历史版本快照').classes('text-h6')
        ui.label('点击“恢复”将覆盖当前编辑器内容（请先保存当前版本！）').classes('text-red-500 text-sm font-bold')
        
        with ui.scroll_area().classes('w-full flex-grow border p-2'):
            if not snapshots:
                ui.label('暂无历史快照').classes('text-grey italic w-full text-center mt-10')
            
            for snap in snapshots:
                with ui.card().classes('w-full mb-2 bg-grey-1'):
                    with ui.row().classes('w-full justify-between items-center'):
                        ui.label(f"📅 {snap['time']}").classes('font-mono font-bold text-blue-800')
                        
                        async def restore(f=snap['filename']):
                            # 读取文件内容
                            def read_file():
                                with open(f, 'r', encoding='utf-8') as file: return file.read()
                            content = await run.io_bound(read_file)
                            content_ref = ui_refs.get('editor_content')
                            if content_ref is not None:
                                content_ref.value = content
                                update_char_count()
                            dialog.close()
                            ui.notify(f'已恢复至 {snap["time"]} 版本', type='positive')

                        ui.button('恢复此版本', on_click=restore).props('size=sm color=red outline')
                    
                    ui.label(snap['preview']).classes('text-sm text-grey-600 mt-1 truncate')

        ui.button('关闭', on_click=dialog.close).props('flat w-full')
    dialog.open()

async def export_novel():
    ui.notify('正在打包全书...', spinner=True)
    full_text = await run.io_bound(backend.export_full_novel, manager)
    ui.download(full_text.encode('utf-8'), 'my_novel.txt')
    ui.notify('下载已开始', type='positive')

async def open_rewrite_dialog():
    js_code = "var t = document.querySelector('.main-editor textarea'); return t ? [t.selectionStart, t.selectionEnd] : [0,0];"
    try: selection = await ui.run_javascript(js_code)
    except: return
    start, end = selection[0], selection[1]
    content_ref = ui_refs.get('editor_content')
    full_text = content_ref.value if content_ref is not None else ""
    selected_text = full_text[start:end]
    if not selected_text.strip(): ui.notify('请先选中文字', type='warning'); return

    with ui.dialog() as dialog, ui.card().classes('w-1/2'):
        ui.label('✨ 局部重绘').classes('text-h6')
        ui.label(selected_text[:100]+"...").classes('text-sm italic bg-grey-2 p-2 w-full rounded')
        instruction = ui.input('修改要求').classes('w-full')
        async def confirm():
            ui.notify('AI 重写中...', spinner=True); dialog.close()
            pre, post = full_text[:start], full_text[end:]

            # 流式输出重写
            new_text = ""
            has_error = False

            import queue
            import threading

            text_queue = queue.Queue()
            stream_done = object()

            def run_stream():
                try:
                    for chunk in backend.stream_rewrite_llm(selected_text, pre, post, instruction.value):
                        text_queue.put(chunk)
                except Exception as e:
                    text_queue.put(f"Error: {str(e)}")
                finally:
                    text_queue.put(stream_done)

            thread = threading.Thread(target=run_stream, daemon=True)
            thread.start()

            while thread.is_alive() or not text_queue.empty():
                try:
                    chunk = text_queue.get(timeout=0.05)
                    if chunk is stream_done:
                        break
                    if chunk.startswith("Error:"):
                        ui.notify('失败: ' + chunk, type='negative')
                        has_error = True
                        break
                    new_text += chunk
                    if content_ref:
                        content_ref.value = pre + new_text + post
                    await asyncio.sleep(0.01)
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue

            if not has_error:
                update_char_count()
                ui.notify('完成', type='positive')
        ui.button('开始重写', on_click=confirm).props('color=purple')
    dialog.open()

async def open_review_dialog():
    """多维度审稿 - 人设、逻辑、节奏分别检查，然后汇总"""
    content_ref = ui_refs.get('editor_content')
    content = content_ref.value if content_ref is not None else ""
    if not content or len(content) < 100:
        ui.notify('正文太短，至少需要100字', type='warning')
        return

    # 获取当前章节
    chapter = app_state.get_current_chapter()
    chapter_id = chapter['id'] if chapter else 1
    chapter_outline = chapter.get('outline', '') if chapter else ''

    # 准备上下文信息
    characters_info = ""
    for c in app_state.characters:
        characters_info += f"- {c['name']}({c['role']}/{c['status']}): {c['bio']}\n"
        if c.get('relations'):
            rel_strs = [f"{r['type']}->{r['target']}" for r in c['relations']]
            characters_info += f"  关系: {', '.join(rel_strs)}\n"

    world_setting = app_state.settings.get('world_view', '')
    book_summary = app_state.settings.get('book_summary', '')

    # 获取前一章内容用于风格对比
    prev_content = ''
    prev_summary = ''
    if chapter_id > 1:
        prev_chapter = next((c for c in app_state.structure if c['id'] == chapter_id - 1), None)
        if prev_chapter:
            prev_summary = prev_chapter.get('summary', '')
            try:
                prev_paragraphs = await run.io_bound(manager.load_chapter_paragraphs, chapter_id - 1)
                if prev_paragraphs:
                    prev_content = '\n'.join([p['text'] for p in prev_paragraphs[:5]])  # 取前5段
            except:
                pass

    context_info = {
        "characters": characters_info,
        "world_setting": world_setting,
        "chapter_outline": chapter_outline,
        "book_summary": book_summary,
        "prev_summary": prev_summary,
        "prev_content": prev_content
    }

    with ui.dialog() as dialog, ui.card().classes('w-[900px] max-h-[90vh]'):
        ui.label('多维度审稿与分析').classes('text-h6 mb-2')

        # 进度显示
        status_label = ui.label('正在加载段落结构...').classes('text-sm text-grey-6 mb-2')

        # 维度评分显示区域
        dimension_row = ui.row().classes('w-full gap-4 mb-4')

        # 结果显示区域
        with ui.scroll_area().classes('w-full h-[50vh]'):
            result_container = ui.column().classes('w-full')

        ui.button('关闭', on_click=dialog.close).props('flat')

    dialog.open()

    # 异步执行审稿
    async def do_review():
        try:
            # 1. 转换为段落结构
            paragraphs = await run.io_bound(manager.load_chapter_paragraphs, chapter_id)

            if not paragraphs:
                paragraphs = manager.text_to_paragraphs(content)
                if paragraphs:
                    await run.io_bound(manager.save_chapter_paragraphs, chapter_id, paragraphs)

            if not paragraphs:
                status_label.set_text('无法解析内容')
                return

            status_label.set_text(f'共 {len(paragraphs)} 个段落，开始多维度审稿...')

            # 2. 执行多维度审稿
            # 获取项目路径和当前章节号（用于伏笔保存）
            project_path = manager.project_root if hasattr(manager, 'project_root') else None
            current_chapter_num = chapter_id

            result = await run.io_bound(
                backend.sync_review_chapter_multi_dimension,
                paragraphs,
                context_info,
                project_path,
                current_chapter_num
            )

            # 3. 显示维度评分
            dimension_row.clear()
            with dimension_row:
                dimension_scores = result.get('dimension_scores', {})
                for dim, score in dimension_scores.items():
                    color = 'green' if score >= 8 else ('orange' if score >= 6 else 'red')
                    with ui.card().classes(f'flex-1 bg-{color}-50 p-2 text-center'):
                        ui.label(dim).classes('font-bold')
                        ui.label(f'{score}/10').classes(f'text-2xl text-{color}-600')

            # 4. 显示结果
            result_container.clear()
            with result_container:
                # 总体统计
                stats = result.get('statistics', {})
                overall = result.get('overall_score', 0)

                with ui.card().classes('w-full bg-blue-50 mb-4 p-3'):
                    with ui.row().classes('items-center gap-4'):
                        ui.label(f'综合评分: {overall}/10').classes('text-xl font-bold')
                        ui.label(f'|').classes('text-grey-4')
                        ui.label(f'严重: {stats.get("severe", 0)}').classes('text-red-600')
                        ui.label(f'中等: {stats.get("medium", 0)}').classes('text-orange-600')
                        ui.label(f'轻微: {stats.get("minor", 0)}').classes('text-grey-600')

                # 按维度分组显示问题
                issues_by_dimension = {}
                for issue in result.get('issues', []):
                    dim = issue.get('dimension', '其他')
                    if dim not in issues_by_dimension:
                        issues_by_dimension[dim] = []
                    issues_by_dimension[dim].append(issue)

                # 显示分析数据
                analysis_data = result.get('analysis_data', {})

                # 情感曲线
                emotion_curve = analysis_data.get('emotion_curve', [])
                if emotion_curve:
                    with ui.expansion("情感曲线", icon='show_chart').classes('w-full mb-2 bg-purple-50'):
                        with ui.column().classes('w-full p-2'):
                            # 简单的曲线可视化
                            with ui.row().classes('w-full items-end gap-1 h-16'):
                                for point in emotion_curve[:20]:  # 最多显示20个点
                                    intensity = point.get('intensity', 5)
                                    emotion = point.get('emotion', '')
                                    height = int(intensity * 8)
                                    # 根据情绪类型着色
                                    color = 'red' if emotion in ['紧张', '愤怒', '恐惧'] else \
                                            'blue' if emotion in ['悲伤', '压抑', '忧郁'] else \
                                            'green' if emotion in ['喜悦', '轻松', '温暖'] else 'grey'
                                    with ui.column().classes('items-center'):
                                        with ui.element('div').classes(f'w-4 bg-{color}-400 rounded-t').style(f'height: {height}px'):
                                            pass
                            if analysis_data.get('emotion_analysis'):
                                ui.label(f"分析: {analysis_data['emotion_analysis']}").classes('text-sm text-grey-6 mt-2')

                # 叙事统计
                narrative_stats = analysis_data.get('narrative_stats', {})
                if narrative_stats:
                    with ui.expansion("叙事分析", icon='bar_chart').classes('w-full mb-2 bg-blue-50'):
                        with ui.column().classes('w-full p-2'):
                            ui.label(f"对话段落: {narrative_stats.get('dialogue_count', 0)}").classes('text-sm')
                            ui.label(f"描写段落: {narrative_stats.get('description_count', 0)}").classes('text-sm')
                            ui.label(f"对话占比: {narrative_stats.get('dialogue_ratio', '未知')}").classes('text-sm')

                # 伏笔追踪
                foreshadowing = analysis_data.get('foreshadowing', {})
                if foreshadowing:
                    with ui.expansion("伏笔追踪", icon='track_changes').classes('w-full mb-2 bg-green-50'):
                        with ui.column().classes('w-full p-2'):
                            new_foreshadows = foreshadowing.get('new', [])
                            if new_foreshadows:
                                ui.label("本章新埋伏笔:").classes('text-sm font-bold text-green-700')
                                for f in new_foreshadows[:5]:
                                    ui.label(f"  • [{f.get('paragraph_id', '?')}] {f.get('content', '')[:30]}").classes('text-xs')
                            resolved = foreshadowing.get('resolved', [])
                            if resolved:
                                ui.label("已回收伏笔:").classes('text-sm font-bold text-blue-700 mt-2')
                                for f in resolved[:5]:
                                    ui.label(f"  • {f.get('content', '')[:30]}").classes('text-xs')

                # 风格分析
                style_analysis = analysis_data.get('style_analysis', {})
                if style_analysis:
                    with ui.expansion("风格分析", icon='brush').classes('w-full mb-2 bg-amber-50'):
                        with ui.column().classes('w-full p-2'):
                            ui.label(f"主要风格: {style_analysis.get('dominant_style', '未知')}").classes('text-sm')
                            ui.label(f"句式特点: {style_analysis.get('sentence_pattern', '未知')}").classes('text-sm')
                            ui.label(f"用词水平: {style_analysis.get('vocabulary_level', '未知')}").classes('text-sm')

                # 显示各维度问题
                dimension_order = ['人设', '逻辑', '节奏', '情感', '叙事', '伏笔', '风格']
                for dim in dimension_order:
                    dim_issues = issues_by_dimension.get(dim, [])
                    if not dim_issues:
                        continue

                    with ui.expansion(f"{dim}问题 ({len(dim_issues)}个)", icon='warning') \
                            .classes('w-full mb-2'):
                        with ui.column().classes('w-full gap-2'):

                            for issue in dim_issues:
                                severity = issue.get('severity', '轻微')
                                color = {'严重': 'red', '中等': 'orange', '轻微': 'grey'}.get(severity, 'grey')
                                pid = issue.get('paragraph_id', '?')

                                with ui.card().classes('w-full bg-white p-2'):
                                    with ui.row().classes('items-center gap-2 mb-1'):
                                        ui.badge(severity, color=color).props('dense')
                                        ui.label(f'段落{pid}').classes('text-xs font-bold')

                                    ui.label(issue.get('description', '')).classes('text-sm')

                                    if issue.get('quote'):
                                        with ui.row().classes('items-center gap-1 mt-1'):
                                            ui.label('原文:').classes('text-xs text-grey-5')
                                            ui.label(f'"{issue.get("quote")[:50]}..."').classes('text-xs italic text-grey-6')

                                    ui.label(f'建议: {issue.get("suggestion", "")}').classes('text-xs text-blue-600 mt-1')

            # 5. 保存审稿结果
            review_data = {
                'overall_score': result.get('overall_score', 0),
                'dimension_scores': result.get('dimension_scores', {}),
                'issues': result.get('issues', []),
                'statistics': result.get('statistics', {}),
                'paragraph_count': len(paragraphs),
                'reviewed_at': datetime.now().isoformat()
            }

            chapter['review_data'] = review_data
            await run.io_bound(manager.save_structure, app_state.structure)

            status_label.set_text(f'审稿完成！总分: {overall}/10 | 共 {len(result.get("issues", []))} 个问题')

            # 更新右侧面板
            review_panel_ref = ui_refs.get('review_panel')
            if review_panel_ref:
                review_panel_ref.clear()
                with review_panel_ref:
                    ui.label(f"📊 总分: {overall}/10").classes('text-lg font-bold mb-2')

                    # 各维度评分
                    dim_scores = result.get('dimension_scores', {})
                    if dim_scores:
                        with ui.row().classes('gap-2 mb-2'):
                            for dim, score in dim_scores.items():
                                if score > 0:
                                    color = 'green' if score >= 8 else ('orange' if score >= 6 else 'red')
                                    ui.badge(f"{dim}:{score}", color=color).props('rounded')

                    # 问题统计
                    stats = result.get('statistics', {})
                    if stats:
                        ui.label(f"问题: 严重{stats.get('severe', 0)} 中等{stats.get('medium', 0)} 轻微{stats.get('minor', 0)}").classes('text-xs text-grey-6')

                    # 问题列表
                    issues = result.get('issues', [])
                    if issues:
                        with ui.expansion(f"查看 {len(issues)} 个问题", icon='list').classes('w-full mt-2'):
                            for issue in issues[:10]:
                                severity = issue.get('severity', '轻微')
                                color = {'严重': 'red', '中等': 'orange', '轻微': 'grey'}.get(severity, 'grey')
                                with ui.row().classes('items-start gap-1 mb-1'):
                                    ui.badge(severity, color=color).props('dense size=xs')
                                    ui.label(f"[段{issue.get('paragraph_id', '?')}] {issue.get('description', '')[:30]}...").classes('text-xs')

            ui.notify('审稿完成', type='positive')

        except Exception as e:
            import traceback
            traceback.print_exc()
            status_label.set_text(f'审稿失败: {str(e)}')
            ui.notify(f'审稿失败: {str(e)}', type='negative')

    await do_review()

async def open_section_rewrite_dialog():
    """
    基于段落结构的重绘 - 精确定位，安全修改
    用户选择问题，系统只修改对应段落
    """
    current_chapter = app_state.get_current_chapter()
    if not current_chapter:
        ui.notify('请先选择章节', type='warning')
        return

    chapter_id = current_chapter['id']

    # 检查是否有审稿结果
    review_data = current_chapter.get('review_data', {})
    issues = review_data.get('issues', [])

    # 加载段落结构
    paragraphs = await run.io_bound(manager.load_chapter_paragraphs, chapter_id)

    if not paragraphs:
        # 从编辑器内容创建段落
        content_ref = ui_refs.get('editor_content')
        content = content_ref.value if content_ref is not None else ""
        if content:
            paragraphs = manager.text_to_paragraphs(content)
            await run.io_bound(manager.save_chapter_paragraphs, chapter_id, paragraphs)

    if not paragraphs:
        ui.notify('无法解析内容', type='warning')
        return

    if not issues:
        ui.notify('请先进行审稿，获取修改建议', type='warning')
        return

    # 准备上下文
    ctx = f"【世界观】{app_state.settings.get('world_view', '')}\n"
    for c in app_state.characters:
        ctx += f"- {c['name']}: {c['status']}, {c['role']}\n"

    # 按段落分组问题
    issues_by_para = {}
    for issue in issues:
        pid = issue.get('paragraph_id', 'p1')
        if pid not in issues_by_para:
            issues_by_para[pid] = []
        issues_by_para[pid].append(issue)

    # 用户选择的问题
    selected_issues = set()  # issue.id 的集合
    checkbox_refs = {}  # 保存checkbox引用，用于全选时更新UI

    with ui.dialog() as dialog, ui.card().classes('w-[900px] max-h-[90vh]'):
        ui.label('✨ 选择要修复的问题').classes('text-h6 mb-2')
        ui.label('勾选需要修复的问题，系统将只修改对应段落').classes('text-sm text-grey-6 mb-2')

        with ui.scroll_area().classes('w-full h-[50vh] border p-2 bg-grey-1'):
            # 按段落显示问题
            for p in paragraphs:
                pid = p['id']
                para_issues = issues_by_para.get(pid, [])

                if not para_issues:
                    continue  # 没有问题的段落不显示

                with ui.card().classes('w-full mb-2 bg-white'):
                    ui.label(f"📝 段落{pid} ({p['word_count']}字)").classes('font-bold text-blue-800')
                    preview = p['text'][:100] + '...' if len(p['text']) > 100 else p['text']
                    ui.label(preview).classes('text-xs text-grey-6 italic ml-4')

                    ui.separator().classes('my-1')

                    # 显示该段落的问题
                    for issue in para_issues:
                        issue_id = issue.get('id', f"{pid}_{len(para_issues)}")
                        severity = issue.get('severity', '未知')
                        color = {'严重': 'red', '中等': 'orange', '轻微': 'grey'}.get(severity, 'grey')

                        with ui.row().classes('w-full items-start gap-2 p-1'):
                            cb = ui.checkbox().props('dense')
                            checkbox_refs[issue_id] = cb  # 保存引用
                            cb.on_value_change(
                                lambda e, iid=issue_id: selected_issues.add(iid) if e.value else selected_issues.discard(iid)
                            )

                            with ui.column().classes('flex-grow'):
                                with ui.row().classes('items-center gap-1'):
                                    ui.badge(severity, color=color).props('dense')
                                    ui.label(f"[{issue.get('dimension', '未知')}]").classes('text-xs font-bold')
                                ui.label(issue.get('description', '')).classes('text-sm')
                                if issue.get('quote'):
                                    quote_text = issue.get('quote', '')
                                    ui.label(f"原文: \"{quote_text[:30]}...\"").classes('text-xs text-grey-5 italic')
                                ui.label(f"建议: {issue.get('suggestion', '')}").classes('text-xs text-blue-600')

        # 底部操作栏
        def select_all_issues():
            for pid, p_issues in issues_by_para.items():
                for issue in p_issues:
                    issue_id = issue.get('id', f"{pid}_{len(p_issues)}")
                    selected_issues.add(issue_id)
                    # 更新checkbox UI
                    if issue_id in checkbox_refs:
                        checkbox_refs[issue_id].value = True

        def deselect_all():
            selected_issues.clear()
            # 更新所有checkbox UI
            for cb in checkbox_refs.values():
                cb.value = False

        with ui.row().classes('w-full justify-between mt-2'):
            ui.button('全选', on_click=select_all_issues).props('flat size=sm')
            ui.button('取消全选', on_click=deselect_all).props('flat size=sm')
            ui.button('取消', on_click=dialog.close).props('flat')
            ui.button('开始修复', on_click=lambda: do_rewrite()).props('color=purple')

    dialog.open()

    async def do_rewrite():
        if not selected_issues:
            ui.notify('请至少选择一个问题', type='warning')
            return

        dialog.close()

        # 收集需要修改的段落及其问题
        paragraphs_to_rewrite = {}  # {paragraph_id: [issues]}
        for pid, p_issues in issues_by_para.items():
            for issue in p_issues:
                issue_id = issue.get('id', f"{pid}_{len(p_issues)}")
                if issue_id in selected_issues:
                    if pid not in paragraphs_to_rewrite:
                        paragraphs_to_rewrite[pid] = []
                    paragraphs_to_rewrite[pid].append(issue)

        if not paragraphs_to_rewrite:
            ui.notify('没有选中任何问题', type='warning')
            return

        # 创建进度对话框
        with ui.dialog() as progress_dialog, ui.card().classes('w-[700px] max-h-[90vh]'):
            ui.label('🔄 正在修复...').classes('text-h6 mb-2')
            progress_bar = ui.linear_progress(value=0).classes('w-full mb-2')
            status_label = ui.label('准备中...').classes('text-sm text-grey-6 mb-2')

            with ui.scroll_area().classes('w-full h-[50vh] border p-2 bg-grey-1'):
                log_container = ui.column().classes('w-full')

        progress_dialog.open()

        total = len(paragraphs_to_rewrite)
        completed = 0
        success_count = 0

        try:
            # 获取最新的段落数据（只加载一次）
            current_paragraphs = await run.io_bound(manager.load_chapter_paragraphs, chapter_id)

            # 记录需要更新的段落
            updates = {}  # {paragraph_id: new_text}

            for pid, para_issues in paragraphs_to_rewrite.items():
                status_label.set_text(f'正在修复段落{pid} ({completed+1}/{total})...')

                # 找到原段落
                original_para = None
                for p in current_paragraphs:
                    if p['id'] == pid:
                        original_para = p
                        break

                if not original_para:
                    with log_container:
                        ui.label(f"❌ 段落{pid}未找到，跳过").classes('text-red text-xs')
                    completed += 1
                    continue

                original_text = original_para['text']

                # 调用重写
                new_text, error = await run.io_bound(
                    backend.sync_rewrite_paragraph,
                    original_text,
                    para_issues,
                    ctx
                )

                with log_container:
                    if error:
                        ui.label(f"❌ 段落{pid}修复失败: {error}").classes('text-red text-xs')
                    else:
                        old_words = backend.count_words(original_text)['total_words']
                        new_words = backend.count_words(new_text)['total_words']

                        ui.label(f"✅ 段落{pid}修复完成 ({old_words}字 → {new_words}字)").classes('text-green text-xs')

                        # 显示对比
                        with ui.expansion('查看修改').classes('w-full ml-4'):
                            with ui.row().classes('w-full gap-2'):
                                with ui.column().classes('flex-1'):
                                    ui.label('原文:').classes('text-xs font-bold')
                                    ui.label(original_text[:200] + '...' if len(original_text) > 200 else original_text).classes('text-xs text-grey-6 bg-grey-1 p-1 rounded')
                                with ui.column().classes('flex-1'):
                                    ui.label('新文:').classes('text-xs font-bold')
                                    ui.label(new_text[:200] + '...' if len(new_text) > 200 else new_text).classes('text-xs text-green-700 bg-green-50 p-1 rounded')

                        # 记录更新（稍后统一应用）
                        updates[pid] = new_text
                        success_count += 1

                completed += 1
                progress_bar.set_value(completed / total)
                await asyncio.sleep(0.05)

            # 统一应用所有更新
            if updates:
                for pid, new_text in updates.items():
                    for i, p in enumerate(current_paragraphs):
                        if p['id'] == pid:
                            current_paragraphs[i]['text'] = new_text
                            current_paragraphs[i]['word_count'] = backend.count_words(new_text)['total_words']
                            break

                # 一次性保存所有更新
                await run.io_bound(manager.save_chapter_paragraphs, chapter_id, current_paragraphs)

            # 更新编辑器内容（设置标志防止触发自动保存）
            global is_loading
            is_loading = True
            try:
                final_text = manager.paragraphs_to_text(current_paragraphs)
                content_ref = ui_refs.get('editor_content')
                if content_ref:
                    content_ref.value = final_text
                    update_char_count()
            finally:
                is_loading = False

            status_label.set_text(f'修复完成！成功: {success_count}/{total} 个段落')
            ui.notify(f'修复完成，共修改 {success_count} 个段落', type='positive')

            # 标记审稿意见为已修复（保留审稿记录供参考）
            if 'review_data' in current_chapter:
                current_chapter['review_data']['fixed_at'] = datetime.now().isoformat()
                current_chapter['review_data']['fixed_count'] = success_count
            await run.io_bound(manager.save_structure, app_state.structure)

        except Exception as e:
            import traceback
            traceback.print_exc()
            status_label.set_text(f'修复失败: {str(e)}')
            ui.notify(f'修复失败: {str(e)}', type='negative')

        ui.button('关闭', on_click=progress_dialog.close).props('flat color=primary')

async def open_state_audit_dialog():
    content_ref = ui_refs.get('editor_content')
    content = content_ref.value if content_ref is not None else ""
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
                selected = {"char_updates":[], "item_updates":[], "new_chars":[], "new_items":[], "new_locs":[], "relation_updates":[], "loc_connections": []}
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
                render_sec("🗺️ 地图连接", "loc_connections", changes.get('loc_connections', []), lambda x: f"{x['source']} ↔️ {x['target']}")
                render_sec("📦 物品变更", "item_updates", changes.get('item_updates', []), lambda x: f"{x['name']} [{x['field']}] -> {x['new_value']}")
                render_sec("🆕 新人物", "new_chars", changes.get('new_chars', []), lambda x: f"[新] {x['name']} ({x.get('role','')})")
                render_sec("🆕 新物品", "new_items", changes.get('new_items', []), lambda x: f"[新] {x['name']} ({x.get('type','')})")
                render_sec("🆕 新地点", "new_locs", changes.get('new_locs', []), lambda x: f"[新] {x['name']} ({x.get('desc','')[:20]}...)")
            async def apply():
                from . import settings
                logs = await run.io_bound(backend.apply_state_changes, manager, selected)
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

# ================= UI 构建函数 (保持不变) =================
def create_writing_tab():
    # ... (保持原有的 create_writing_tab 代码) ...
    with ui.splitter(value=75).classes('w-full h-full') as splitter:
        with splitter.before:
            with ui.column().classes('w-full h-full p-4'):
                with ui.row().classes('w-full items-center gap-2 mb-2'):
                    ui_refs['time_label'] = ui.input('当前时间点', placeholder='如：修仙历1024年').classes('w-1/3')
                    ui.button('⏱️ 分析时间', on_click=timeline.analyze_time).props('size=sm color=teal')
                
                ui_refs['time_events'] = ui.textarea('本章关键事件', placeholder='一行一个').classes('w-full').props('rows=2')
                ui_refs['editor_title'] = ui.input(label='章节标题').classes('w-full')
                ui_refs['editor_outline'] = ui.textarea(label='本章大纲').classes('w-full').props('rows=3')
                
                with ui.row().classes('items-center'):
                    ui.button('🚀 生成', on_click=generate_content).props('color=primary')
                    ui.button('保存', on_click=save_current_chapter).props('color=green').tooltip('完整保存：更新记忆库和摘要')
                    # 【新增】撤销重做按钮
                    ui.button('撤销', on_click=undo_action).props('color=grey outline').tooltip('撤销上一步操作')
                    ui.button('重做', on_click=redo_action).props('color=grey outline').tooltip('重做上一步撤销的操作')
                    # 【原有】历史按钮
                    ui.button('历史', on_click=open_history_dialog).props('color=grey outline').tooltip('查看历史版本快照')
                    ui.button('结算', on_click=open_state_audit_dialog).props('color=blue outline')
                    ui.button('重绘', on_click=open_rewrite_dialog).props('color=purple outline').tooltip('选中文字后重写')
                    ui.button('分段重绘', on_click=open_section_rewrite_dialog).props('color=deep-purple outline').tooltip('按审稿意见分段重写')
                    ui.button('审稿', on_click=open_review_dialog).props('color=orange outline')
                    
                    with ui.column().classes('ml-4 gap-0'):
                        ui_refs['char_count'] = ui.label('字数: 0').classes('text-grey-7 text-xs')
                        ui_refs['save_status'] = ui.label('').classes('text-xs font-bold')
                
                ui_refs['editor_content'] = ui.textarea(label='正文') \
                    .classes('w-full h-full font-mono main-editor') \
                    .props('rows=20 borderless spellcheck="false" input-style="line-height: 2.0; font-size: 16px;"') \
                    .on_value_change(handle_text_change)
        
        with splitter.after:
            with ui.column().classes('w-full h-full p-0 bg-blue-50'):
                with ui.tabs().classes('w-full bg-blue-100 text-grey-8') as right_tabs:
                    ui_refs['right_tabs'] = right_tabs
                    ui_refs['tab_ctx'] = ui.tab('上下文')
                    ui_refs['tab_rev'] = ui.tab('审稿意见')
                    tab_foreshadow = ui.tab('伏笔提醒')

                with ui.tab_panels(right_tabs, value=ui_refs.get('tab_ctx')).classes('w-full flex-grow bg-transparent').props('keep-alive animated vertical'):
                    with ui.tab_panel(ui_refs['tab_ctx']).classes('w-full h-full p-0 flex flex-col'):
                        with ui.scroll_area().classes('w-full flex-grow p-2'):
                            ui_refs['rag_debug'] = ui.column().classes('w-full')
                    with ui.tab_panel(ui_refs['tab_rev']).classes('w-full h-full p-0 flex flex-col'):
                        with ui.scroll_area().classes('w-full flex-grow p-2'):
                            ui_refs['review_panel'] = ui.column().classes('w-full')
                            ui.label("暂无记录").classes('text-grey italic')

                    # 伏笔提醒标签页
                    with ui.tab_panel(tab_foreshadow).classes('w-full h-full p-0 flex flex-col'):
                        with ui.scroll_area().classes('w-full flex-grow p-2'):
                            ui_refs['foreshadow_warning_panel'] = ui.column().classes('w-full')
                            refresh_foreshadow_warning_ui()