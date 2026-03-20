#!/usr/bin/env python3
import os
import sys

# 设置环境变量以避免代理问题
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

# 临时设置环境变量以避免代理
for env_var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'all_proxy']:
    if env_var in os.environ:
        del os.environ[env_var]

# 设置正确的路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 首先导入 nicegui 以便稍后在函数中使用
from nicegui import ui, run

try:
    # 延迟导入以避免在模块级别连接
    import backend

    # 重新定义 sync_call_llm 以便在需要时才创建客户端
    def create_client():
        """延迟创建OpenAI客户端，仅在需要时创建"""
        from openai import OpenAI
        import backend
        CFG = backend.CFG
        return OpenAI(api_key=CFG.get('api_key'), base_url=CFG.get('base_url'))

    original_sync_call_llm = backend.sync_call_llm
    def patched_sync_call_llm(prompt, system_prompt, task_type="writer"):
        # 创建临时客户端进行调用
        temp_client = create_client()
        model_name = backend.CFG['models'].get(task_type, "deepseek-chat")
        temperature = backend.CFG['temperatures'].get(task_type, 1.3)
        print(f"\n[LLM Router] 任务: {task_type} | 模型: {model_name}")
        try:
            response = temp_client.chat.completions.create(
                model=model_name,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                stream=False,
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"

    # 替换函数
    backend.sync_call_llm = patched_sync_call_llm

    # 现在安全地运行主程序
    from novel_modules.state import app_state, ui_refs, manager
    from novel_modules import writing, settings, architect, timeline
    from novel_modules import outline_ui
    from novel_modules import bookshelf

    @ui.page('/')
    async def main_page():
        # 1. 初始化 UI 引用
        ui_refs['editor_title'] = None
        ui_refs['editor_outline'] = None
        ui_refs['editor_content'] = None
        ui_refs['char_container'] = None
        ui_refs['item_container'] = None
        ui_refs['loc_container'] = None
        ui_refs['chapter_list'] = None
        ui_refs['rag_debug'] = None
        ui_refs['review_panel'] = None
        ui_refs['right_tabs'] = None
        ui_refs['tab_ctx'] = None
        ui_refs['tab_rev'] = None
        ui_refs['char_count'] = None
        ui_refs['total_count'] = None
        ui_refs['char_view_mode'] = None
        ui_refs['char_graph_container'] = None
        ui_refs['time_label'] = None
        ui_refs['time_events'] = None
        ui_refs['timeline_container'] = None
        ui_refs['save_status'] = None
        ui_refs['config_container'] = None
        ui_refs['loc_view_mode'] = None
        ui_refs['loc_graph_container'] = None
        ui_refs['api_container'] = None
        ui_refs['prompts_container'] = None

        # 2. 定义辅助函数
        async def refresh_total_word_count():
            if ui_refs['total_count']:
                ui_refs['total_count'].set_text("统计中...")
                total = await run.io_bound(manager.get_total_word_count)
                ui_refs['total_count'].set_text(f"全书字数: {total:,}")

        def refresh_sidebar():
            if not ui_refs['chapter_list']: return
            ui_refs['chapter_list'].clear()

            with ui_refs['chapter_list']:
                for vol in app_state.volumes:
                    vol_chapters = [c for c in app_state.structure if c.get('volume_id') == vol['id']]
                    is_expanded = vol['id'] in app_state.expanded_volumes

                    with ui.expansion(f"{vol['title']} ({len(vol_chapters)}章)", icon='book', value=is_expanded) \
                            .classes('w-full bg-blue-50 mb-1 border rounded shadow-sm') \
                            .on_value_change(lambda e, v=vol['id']: (app_state.expanded_volumes.add(v) if e.value else app_state.expanded_volumes.discard(v))) as expansion:

                        with ui.column().classes('w-full pl-0 gap-1 bg-white p-1'):
                            for chap in vol_chapters:
                                real_idx = app_state.structure.index(chap)
                                color = 'purple' if real_idx == app_state.current_chapter_idx else 'grey-8'
                                status_icon = ''
                                if chap.get('review_report'): status_icon += '📝'
                                if chap.get('time_info', {}).get('events'): status_icon += '⏱️'

                                async def on_chapter_click(i=real_idx):
                                    await writing.load_chapter(i)

                                ui.button(f"{chap['id']}. {chap['title']} {status_icon}",
                                          on_click=on_chapter_click) \
                                    .props(f'flat color={color} align=left no-caps dense size=sm') \
                                    .classes('w-full text-left pl-4 hover:bg-grey-100')

                            with ui.row().classes('w-full justify-end pr-2 pt-1 border-t border-dashed'):
                                ui.button(icon='edit', on_click=lambda v=vol['id']: writing.rename_volume(v)) \
                                    .props('flat size=xs color=grey').tooltip('重命名分卷')

                                ui.button(icon='add', on_click=lambda v=vol['id']: writing.add_chapter_to_volume(v)) \
                                    .props('flat size=xs color=green').tooltip('在此卷添加章节')

        # 3. 注册全局回调
        app_state.refresh_sidebar = refresh_sidebar
        app_state.refresh_total_word_count = refresh_total_word_count

        # 4. 布局开始 (修正：Header 和 Drawer 必须在最外层)

        # --- 4.1 Header (固定顶部) ---
        with ui.header().classes('bg-white text-black shadow-sm shrink-0'):
            ui.button(on_click=lambda: drawer.toggle(), icon='menu').props('flat color=black')
            ui.label('AI 网文工作站 (V15.2 配置管理版)').classes('text-h6')

        # --- 4.2 Left Drawer (左侧边栏) ---
        with ui.left_drawer(value=True).classes('bg-blue-50 flex flex-col') as drawer:
            # === 新增：书架入口区 ===
            with ui.column().classes('w-full p-2 mb-2 bg-purple-100 rounded border border-purple-200'):
                ui.label('当前作品:').classes('text-xs text-purple-600 font-bold')
                # 绑定显示当前书名
                book_label = ui.label().bind_text_from(app_state, 'current_book_name') \
                    .classes('text-lg font-bold text-purple-900 truncate w-full')

                ui.button('📚 切换/管理书籍', on_click=bookshelf.open_bookshelf_dialog) \
                    .props('size=sm color=purple icon=swap_horiz w-full')

            ui.separator().classes('mb-2')

            ui.label('📚 章节目录').classes('text-h6 q-mb-md')

            with ui.card().classes('w-full q-mb-sm bg-white p-2'):
                ui_refs['total_count'] = ui.label('全书字数: ---').classes('text-sm font-bold')
                with ui.row().classes('w-full'):
                    ui.button('🔄 刷新', on_click=lambda: refresh_total_word_count()).props('flat size=sm color=primary').classes('w-1/2')
                    ui.button('📤 导出', on_click=lambda: writing.export_novel()).props('flat size=sm color=grey').classes('w-1/2')

                with ui.row().classes('w-full q-mt-sm'):
                    async def show_book_summary():
                        settings_data = await run.io_bound(manager.load_settings)
                        summary = settings_data.get('book_summary', '暂无总结，请先保存章节触发生成。')
                        with ui.dialog() as d, ui.card().classes('w-1/2'):
                            ui.label('📖 全书剧情总纲').classes('text-h6 font-bold')
                            with ui.scroll_area().classes('h-64 border p-4 bg-grey-1 rounded'):
                                ui.markdown(summary).classes('text-lg leading-relaxed')
                            ui.button('关闭', on_click=d.close).props('flat')
                        d.open()
                    ui.button('📖 全书梗概', on_click=show_book_summary).props('flat size=sm color=purple').classes('w-full')

            with ui.scroll_area().classes('w-full flex-grow'):
                ui_refs['chapter_list'] = ui.column().classes('w-full')
                refresh_sidebar()

            ui.separator().classes('my-2')
            with ui.grid(columns=2).classes('w-full gap-2 pb-2'):
                ui.button('新建分卷', on_click=writing.add_new_volume).props('outline color=indigo size=sm icon=create_new_folder')
                ui.button('删除分卷', on_click=writing.delete_volume_dialog).props('outline color=red size=sm icon=folder_delete')
                ui.button('新建章节', on_click=writing.add_new_chapter_auto).props('color=green size=sm icon=note_add')
                ui.button('删除章节', on_click=writing.delete_current_chapter).props('color=red size=sm icon=delete_forever')
            ui.separator().classes('my-2')
            ui.label('🛠️ 全局工具').classes('text-xs font-bold text-grey-6 mb-1')
            ui.button('🔍 全局查找与替换', on_click=settings.open_global_search_dialog) \
                .props('flat color=blue-grey icon=find_replace w-full align=left').classes('w-full')
            ui.button('🎲 灵感百宝箱', on_click=settings.open_inspiration_dialog) \
                .props('flat color=deep-purple icon=auto_fix_high w-full align=left').classes('w-full')

        # --- 4.3 主内容区域 (Tabs) ---
        # 【关键修正】这里使用 calc(100vh - 60px) 来扣除 Header 的高度，防止滚动条。
        # Header 大约 50-60px，这里预留 60px 比较安全。
        with ui.column().classes('w-full h-[calc(100vh-60px)] p-0 gap-0 no-wrap'):

            # 4.3.1 Tabs 栏 (固定高度)
            with ui.tabs().classes('w-full bg-primary text-white shadow-2 shrink-0') as tabs:
                # tab_outline = ui.tab('大纲树', icon='account_tree')
                tab_write = ui.tab('写作', icon='edit')
                tab_setting = ui.tab('设定', icon='people')
                t_graph = ui.tab('图谱', icon='hub')
                tab_arch = ui.tab('架构', icon='construction')
                tab_timeline = ui.tab('时间轴', icon='schedule')

            # 4.3.2 Tab Panels (占据剩余所有高度)
            # flex-grow: 占据剩余空间
            # h-0: 强制 Flex 容器根据空间计算高度，而非内容
            with ui.tab_panels(tabs, value=tab_write).classes('w-full flex-grow p-0 h-0').props('keep-alive'):

                # --- Tab 1: 写作 ---
                with ui.tab_panel(tab_write).classes('h-full w-full p-0'):
                    writing.create_writing_tab()

                # --- Tab 2: 设定 ---
                with ui.tab_panel(tab_setting).classes('h-full w-full p-0 flex flex-col'):
                    # 二级 Tabs
                    with ui.tabs().classes('w-full bg-grey-2 shrink-0') as set_tabs:
                        t_world = ui.tab('世界观')
                        t_char = ui.tab('人物')
                        t_item = ui.tab('物品')
                        t_loc = ui.tab('地点')
                        t_api = ui.tab('API与模型')
                        t_prompts = ui.tab('提示词管理')

                    # 二级 Tab Panels
                    with ui.tab_panels(set_tabs, value=t_world).classes('w-full flex-grow h-0'):

                        # 2.1 世界观
                        # removing p-4 to make it full edge-to-edge
                        with ui.tab_panel(t_world).classes('h-full w-full p-0'):

                            # 1. 外层容器：Row (左右布局)
                            # no-wrap: 防止宽度不够时换行
                            # items-stretch: 让左右两边高度一致（撑满）
                            with ui.row().classes('w-full h-full no-wrap gap-0 items-stretch'):

                                # --- 左侧：Column (工具栏) ---
                                # w-48: 固定宽度
                                # border-r: 右边框分割线
                                with ui.column().classes('w-48 h-full p-4 bg-grey-1 border-r shrink-0 gap-4'):

                                    # 标题区
                                    with ui.column().classes('gap-1'):
                                        ui.label('🌍 世界观').classes('text-xl font-bold text-grey-8')
                                        ui.label('Markdown 格式').classes('text-xs text-grey-5')

                                    ui.separator().classes('w-full')

                                    # 按钮区
                                    def save_world_view():
                                        app_state.settings['world_view'] = world_editor.value
                                        run.io_bound(manager.save_settings, app_state.settings)
                                        ui.notify('世界观已保存', type='positive')

                                    ui.button('保存设定', icon='save', on_click=save_world_view) \
                                        .props('color=green w-full unelevated')

                                    ui.label('提示：此处设定的内容会被 RAG 系统索引，用于保持剧情逻辑一致。').classes('text-xs text-grey-5 italic mt-auto')

                                # --- 右侧：Editor (编辑器) ---
                                # flex-grow: 占据剩余所有宽度
                                # h-full: 占满高度
                                with ui.card().classes('flex-grow h-full p-0 rounded-none border-none'):
                                    # 创建标签切换按钮
                                    with ui.row().classes('w-full bg-grey-100 shrink-0') as tab_row:
                                        editor_active = ui.element('div').props('innerHTML="edit"').classes('hidden')  # 默认为编辑状态

                                        async def switch_to_edit():
                                            edit_panel.classes(replace='w-full h-full')  # 显示编辑面板
                                            preview_panel.classes(replace='w-full h-full hidden')  # 隐藏预览面板
                                            edit_btn.props('color=primary')
                                            preview_btn.props('color=grey')
                                            editor_active._props['innerHTML'] = 'edit'

                                        async def switch_to_preview():
                                            edit_panel.classes(replace='w-full h-full hidden')  # 隐藏编辑面板
                                            preview_panel.classes(replace='w-full h-full')  # 显示预览面板
                                            edit_btn.props('color=grey')
                                            preview_btn.props('color=primary')
                                            editor_active._props['innerHTML'] = 'preview'

                                        with ui.row().classes('w-full justify-start pl-2 py-1'):  # 靠左对齐并添加内边距
                                            edit_btn = ui.button('📝 编辑', on_click=switch_to_edit).props('flat no-caps color=primary size=sm').classes('mr-2')  # 缩小按钮尺寸
                                            preview_btn = ui.button('👁️ 预览', on_click=switch_to_preview).props('flat no-caps color=grey size=sm')  # 缩小按钮尺寸

                                    # 内容面板容器
                                    with ui.column().classes('w-full h-full flex-grow') as editor_content:
                                        # 编辑面板 - 使用classes方法控制可见性而不是set_visibility
                                        with ui.column().classes('w-full h-full') as edit_panel:
                                            # 确保codemirror编辑器正确填充空间并启用换行
                                            world_editor = ui.codemirror(value=app_state.settings['world_view'], language='markdown') \
                                                .classes('w-full h-full text-base font-sans overflow-hidden') \
                                                .style('font-family: system-ui, -apple-system, sans-serif !important; width: 100% !important; height: 100% !important; word-wrap: break-word; word-break: break-word; overflow-wrap: break-word;') \
                                                .props('options="{lineWrapping: true, lineNumbers: true, scrollbarStyle: \"native\", mode: \"gfm\", foldGutter: true, gutters: [\"CodeMirror-linenumbers\", \"CodeMirror-foldgutter\"], autoCloseBrackets: true, matchBrackets: true, theme: \"default\"}"')

                                        # 预览面板 - 使用classes方法控制可见性而不是set_visibility
                                        with ui.column().classes('w-full h-full hidden') as preview_panel:
                                            world_preview = ui.markdown(app_state.settings['world_view']).classes('w-full h-full p-4 bg-white overflow-auto')

                                    # 实时更新预览
                                    def update_preview(e):
                                        # 实时更新预览内容
                                        world_preview.content = e.value

                                    # 等待编辑器创建完成后再绑定事件
                                    async def setup_editor_events():
                                        await ui.run_javascript('''
                                            // 等待DOM更新完成
                                        ''')
                                        world_editor.on('input', update_preview)  # 当输入时更新预览

                                    # 初始化时设置默认状态 - 使用classes方法
                                    edit_panel.classes(replace='w-full h-full')  # 显示编辑面板
                                    preview_panel.classes(replace='w-full h-full hidden')  # 隐藏预览面板
                                    edit_btn.props('color=primary')
                                    preview_btn.props('color=grey')

                                    # 初始化事件绑定
                                    ui.timer(0.1, setup_editor_events, once=True)
                        with ui.tab_panel(t_char).classes('h-full w-full p-2 flex flex-col'):
                            with ui.row().classes('w-full justify-between items-center pb-2 shrink-0'):
                                with ui.button_group():
                                    ui.button('列表', on_click=lambda: [ui_refs['char_view_mode'].set_text('list'), settings.refresh_char_ui()]).props('size=sm')
                                    ui.button('图谱', on_click=lambda: [ui_refs['char_view_mode'].set_text('graph'), settings.refresh_char_ui()]).props('size=sm')
                                ui_refs['char_view_mode'] = ui.label('list').classes('hidden')
                                with ui.row():
                                    ui.button(icon='refresh', on_click=settings.refresh_char_ui).props('flat round dense')
                                    ui.button('添加人物', icon='add', on_click=lambda: settings.open_char_dialog()).props('size=sm color=blue')

                            # 内容容器
                            with ui.element('div').classes('w-full flex-grow relative bg-white border'):
                                with ui.scroll_area().classes('w-full h-full').bind_visibility_from(ui_refs['char_view_mode'], 'text', backward=lambda x: x == 'list'):
                                    ui_refs['char_container'] = ui.column().classes('w-full p-1')
                                with ui.element('div').classes('w-full h-full').bind_visibility_from(ui_refs['char_view_mode'], 'text', backward=lambda x: x == 'graph'):
                                    ui_refs['char_graph_container'] = ui.column().classes('w-full h-full')
                                settings.refresh_char_ui()

                        # 2.3 物品
                        with ui.tab_panel(t_item).classes('h-full w-full p-2 flex flex-col'):
                            with ui.row().classes('w-full justify-end pb-2 shrink-0'):
                                ui.button(icon='refresh', on_click=settings.refresh_item_ui).props('flat round dense')
                                ui.button('添加物品', icon='add', on_click=lambda: settings.open_item_dialog()).props('size=sm color=orange')

                            with ui.scroll_area().classes('w-full flex-grow border'):
                                ui_refs['item_container'] = ui.column().classes('w-full p-1')
                                settings.refresh_item_ui()

                        # 2.4 地点
                        with ui.tab_panel(t_loc).classes('h-full w-full p-2 flex flex-col'):
                            with ui.row().classes('w-full justify-between items-center pb-2 shrink-0'):
                                with ui.button_group():
                                    ui.button('列表', on_click=lambda: [ui_refs['loc_view_mode'].set_text('list'), settings.refresh_loc_ui()]).props('size=sm')
                                    ui.button('地图', on_click=lambda: [ui_refs['loc_view_mode'].set_text('graph'), settings.refresh_loc_ui()]).props('size=sm')
                                ui_refs['loc_view_mode'] = ui.label('list').classes('hidden')

                                with ui.row():
                                    ui.button('整理', icon='build', on_click=settings.open_connection_manager).props('flat size=sm dense color=grey')
                                    ui.button(icon='refresh', on_click=settings.refresh_loc_ui).props('flat round dense')
                                    ui.button('添加地点', icon='add', on_click=lambda: settings.open_loc_dialog()).props('size=sm color=green')

                            with ui.element('div').classes('w-full flex-grow relative border'):
                                with ui.scroll_area().classes('w-full h-full').bind_visibility_from(ui_refs['loc_view_mode'], 'text', backward=lambda x: x == 'list'):
                                    ui_refs['loc_container'] = ui.column().classes('w-full p-1')

                                with ui.element('div').classes('w-full h-full').bind_visibility_from(ui_refs['loc_view_mode'], 'text', backward=lambda x: x == 'graph'):
                                    ui_refs['loc_graph_container'] = ui.column().classes('w-full h-full')
                                settings.refresh_loc_ui()

                        # 2.5 API与模型
                        with ui.tab_panel(t_api).classes('h-full w-full p-2 flex flex-col'):
                            with ui.scroll_area().classes('w-full flex-grow'):
                                ui_refs['api_container'] = ui.column().classes('w-full')
                                settings.refresh_api_ui()

                        # 2.6 提示词管理
                        with ui.tab_panel(t_prompts).classes('h-full w-full p-2 flex flex-col'):
                            with ui.scroll_area().classes('w-full flex-grow'):
                                ui_refs['prompts_container'] = ui.column().classes('w-full')
                                settings.refresh_prompts_ui()

                # --- Tab 3: 图谱 ---
                with ui.tab_panel(t_graph).classes('h-full w-full p-0 flex flex-col'):
                    settings.create_global_graph_panel()

                # --- Tab 4: 架构师 ---
                with ui.tab_panel(tab_arch).classes('h-full w-full p-4 flex flex-col'):
                    architect.create_architect_ui()

                # --- Tab 5: 时间轴 ---
                with ui.tab_panel(tab_timeline).classes('h-full w-full p-4 flex flex-col'):
                    with ui.row().classes('w-full justify-between items-center mb-4 shrink-0'):
                        ui.label('⏳ 剧情时间轴').classes('text-h6')
                        ui.button('🔄 刷新', on_click=timeline.refresh_timeline).props('flat icon=refresh')
                    with ui.scroll_area().classes('w-full flex-grow bg-grey-1 p-4 rounded'):
                        ui_refs['timeline_container'] = ui.column().classes('w-full')
                        timeline.refresh_timeline()

        # 启动加载
        await writing.load_chapter(0)
        await refresh_total_word_count()

    ui.run(title='AI Novel Studio', port=8081, reload=False)

except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所需依赖。")
except Exception as e:
    print(f"启动过程中发生错误: {e}")
    import traceback
    traceback.print_exc()