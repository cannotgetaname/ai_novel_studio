import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nicegui import ui, run
import backend
from novel_modules.state import app_state, ui_refs, manager
from novel_modules import writing, settings, architect, timeline

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
            for idx, chap in enumerate(app_state.structure):
                color = 'primary' if idx == app_state.current_chapter_idx else 'grey-8'
                icon = ' 📝' if chap.get('review_report') else ''
                time_icon = ' ⏱️' if chap.get('time_info', {}).get('events') else ''
                ui.button(f"{chap['id']}. {chap['title']}{icon}{time_icon}", on_click=lambda i=idx: writing.load_chapter(i)) \
                    .props(f'flat color={color} align=left no-caps').classes('w-full text-left')

    # 3. 注册全局回调
    app_state.refresh_sidebar = refresh_sidebar
    app_state.refresh_total_word_count = refresh_total_word_count

    # 4. 布局
    with ui.left_drawer(value=True).classes('bg-blue-50') as drawer:
        ui.label('📚 章节目录').classes('text-h6 q-mb-md')
        with ui.card().classes('w-full q-mb-md bg-white p-2'):
            ui_refs['total_count'] = ui.label('全书字数: ---').classes('text-sm font-bold')
            with ui.row().classes('w-full'):
                ui.button('🔄 刷新', on_click=lambda: refresh_total_word_count()).props('flat size=sm color=primary').classes('w-1/2')
                ui.button('📤 导出', on_click=lambda: writing.export_novel()).props('flat size=sm color=grey').classes('w-1/2')

        with ui.scroll_area().classes('h-full'):
            ui_refs['chapter_list'] = ui.column().classes('w-full')
            refresh_sidebar()
        
        with ui.row().classes('w-full q-mt-md'):
            ui.button('➕ 新建', on_click=writing.add_new_chapter).props('flat color=green')
            ui.button('🗑️ 删除', on_click=writing.delete_current_chapter).props('flat color=red')

    with ui.header().classes('bg-white text-black shadow-sm'):
        ui.button(on_click=lambda: drawer.toggle(), icon='menu').props('flat color=black')
        ui.label('AI 网文工作站 (V14.2 模块化完整版)').classes('text-h6')

    with ui.tabs().classes('w-full') as tabs:
        tab_write = ui.tab('写作')
        tab_setting = ui.tab('设定')
        tab_arch = ui.tab('架构师')
        tab_timeline = ui.tab('时间轴')

    with ui.tab_panels(tabs, value=tab_write).classes('w-full h-full p-0'):
        
        # Tab 1: 写作
        with ui.tab_panel(tab_write).classes('h-full p-0'):
            writing.create_writing_tab()

        # Tab 2: 设定
        with ui.tab_panel(tab_setting).classes('h-full p-0'):
            with ui.tabs().classes('w-full bg-grey-2') as set_tabs:
                t_world = ui.tab('世界观')
                t_char = ui.tab('人物')
                t_item = ui.tab('物品')
                t_loc = ui.tab('地点')
            
            with ui.tab_panels(set_tabs, value=t_world).classes('w-full flex-grow'):
                with ui.tab_panel(t_world).classes('h-full p-4'):
                    with ui.column().classes('w-full h-full'):
                        world_input = ui.textarea(value=app_state.settings['world_view']).classes('w-full flex-grow').props('borderless input-style="height: 100%"')
                        ui.button('保存', on_click=lambda: run.io_bound(manager.save_settings, app_state.settings)).props('color=green w-full')
                
                with ui.tab_panel(t_char).classes('h-full p-2'):
                    with ui.column().classes('w-full h-full'):
                        with ui.row().classes('w-full justify-between items-center pb-2'):
                            with ui.button_group():
                                ui.button('列表', on_click=lambda: [ui_refs['char_view_mode'].set_text('list'), settings.refresh_char_ui()]).props('size=sm')
                                ui.button('图谱', on_click=lambda: [ui_refs['char_view_mode'].set_text('graph'), settings.refresh_char_ui()]).props('size=sm')
                            ui_refs['char_view_mode'] = ui.label('list').classes('hidden') 
                            with ui.row():
                                ui.button(icon='refresh', on_click=settings.refresh_char_ui).props('flat round dense')
                                ui.button('添加人物', icon='add', on_click=lambda: settings.open_char_dialog()).props('size=sm color=blue')
                        
                        with ui.element('div').classes('w-full').style('height: calc(100vh - 200px); position: relative;'):
                            with ui.scroll_area().classes('w-full h-full').bind_visibility_from(ui_refs['char_view_mode'], 'text', backward=lambda x: x == 'list'):
                                ui_refs['char_container'] = ui.column().classes('w-full p-1')
                            with ui.element('div').classes('w-full h-full').bind_visibility_from(ui_refs['char_view_mode'], 'text', backward=lambda x: x == 'graph'):
                                ui_refs['char_graph_container'] = ui.column().classes('w-full h-full')
                            settings.refresh_char_ui()

                with ui.tab_panel(t_item).classes('h-full p-2'):
                    with ui.column().classes('w-full h-full'):
                        with ui.row().classes('w-full justify-end pb-2'):
                            ui.button(icon='refresh', on_click=settings.refresh_item_ui).props('flat round dense')
                            ui.button('添加物品', icon='add', on_click=lambda: settings.open_item_dialog()).props('size=sm color=orange')
                        with ui.scroll_area().classes('w-full').style('height: calc(100vh - 200px); border: 1px solid #eee'):
                            ui_refs['item_container'] = ui.column().classes('w-full p-1')
                            settings.refresh_item_ui()

                with ui.tab_panel(t_loc).classes('h-full p-2'):
                    with ui.column().classes('w-full h-full'):
                        with ui.row().classes('w-full justify-end pb-2'):
                            ui.button(icon='refresh', on_click=settings.refresh_loc_ui).props('flat round dense')
                            ui.button('添加地点', icon='add', on_click=lambda: settings.open_loc_dialog()).props('size=sm color=green')
                        with ui.scroll_area().classes('w-full').style('height: calc(100vh - 200px); border: 1px solid #eee'):
                            ui_refs['loc_container'] = ui.column().classes('w-full p-1')
                            settings.refresh_loc_ui()

        # Tab 3: 架构师
        with ui.tab_panel(tab_arch).classes('p-4'):
            ui.label('🏗️ 批量大纲生成').classes('text-h6')
            theme_input = ui.textarea(label='后续剧情走向').classes('w-full')
            count_slider = ui.slider(min=3, max=10, value=5).props('label-always')
            ui.button('开始规划', on_click=lambda: architect.run_architect(theme_input, count_slider)).props('color=purple icon=psychology')

        # Tab 4: 时间轴
        with ui.tab_panel(tab_timeline).classes('h-full p-4 flex flex-col'):
            with ui.row().classes('w-full justify-between items-center mb-4'):
                ui.label('⏳ 剧情时间轴').classes('text-h6')
                ui.button('🔄 刷新', on_click=timeline.refresh_timeline).props('flat icon=refresh')
            with ui.scroll_area().classes('w-full flex-grow bg-grey-1 p-4 rounded'):
                ui_refs['timeline_container'] = ui.column().classes('w-full')
                timeline.refresh_timeline()

    # 启动加载
    await writing.load_chapter(0)
    await refresh_total_word_count()

ui.run(title='AI Novel Studio', port=8080, reload=False)