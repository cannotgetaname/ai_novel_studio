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
    ui_refs['save_status'] = None
    ui_refs['config_container'] = None

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
                            
                            ui.button(f"{chap['id']}. {chap['title']} {status_icon}", 
                                      on_click=lambda i=real_idx: writing.load_chapter(i)) \
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

    # 4. 布局
    with ui.left_drawer(value=True).classes('bg-blue-50 flex flex-col') as drawer:
        ui.label('📚 章节目录').classes('text-h6 q-mb-md')
        
        with ui.card().classes('w-full q-mb-sm bg-white p-2'):
            ui_refs['total_count'] = ui.label('全书字数: ---').classes('text-sm font-bold')
            with ui.row().classes('w-full'):
                ui.button('🔄 刷新', on_click=lambda: refresh_total_word_count()).props('flat size=sm color=primary').classes('w-1/2')
                ui.button('📤 导出', on_click=lambda: writing.export_novel()).props('flat size=sm color=grey').classes('w-1/2')
            
            with ui.row().classes('w-full q-mt-sm'):
                async def show_book_summary():
                    settings = await run.io_bound(manager.load_settings)
                    summary = settings.get('book_summary', '暂无总结，请先保存章节触发生成。')
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
    with ui.header().classes('bg-white text-black shadow-sm'):
        ui.button(on_click=lambda: drawer.toggle(), icon='menu').props('flat color=black')
        ui.label('AI 网文工作站 (V15.2 配置管理版)').classes('text-h6')

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
        # 【核心修复】这里必须加上 flex flex-col，否则子级 flex-grow 无效，导致高度塌陷
        with ui.tab_panel(tab_setting).classes('h-full p-0 flex flex-col'):
            with ui.tabs().classes('w-full bg-grey-2') as set_tabs:
                t_world = ui.tab('世界观')
                t_char = ui.tab('人物')
                t_item = ui.tab('物品')
                t_loc = ui.tab('地点')
                t_config = ui.tab('系统配置')
            
            with ui.tab_panels(set_tabs, value=t_world).classes('w-full flex-grow'):
                with ui.tab_panel(t_world).classes('h-full p-4'):
                    with ui.column().classes('w-full h-full'):
                        ui.textarea(value=app_state.settings['world_view']).classes('w-full flex-grow').props('borderless input-style="height: 100%"')
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
                        # 顶部工具栏：切换按钮 + 刷新 + 添加
                        with ui.row().classes('w-full justify-between items-center pb-2'):
                            # 切换视图按钮组
                            with ui.button_group():
                                ui.button('列表', on_click=lambda: [ui_refs['loc_view_mode'].set_text('list'), settings.refresh_loc_ui()]).props('size=sm')
                                ui.button('地图', on_click=lambda: [ui_refs['loc_view_mode'].set_text('graph'), settings.refresh_loc_ui()]).props('size=sm')
                            # 隐藏的状态标签
                            ui_refs['loc_view_mode'] = ui.label('list').classes('hidden')
                            
                            with ui.row():
                                ui.button('整理', icon='build', on_click=settings.open_connection_manager).props('flat size=sm dense color=grey').tooltip('扫描并修复单向连接')
                                ui.button(icon='refresh', on_click=settings.refresh_loc_ui).props('flat round dense')
                                ui.button('添加地点', icon='add', on_click=lambda: settings.open_loc_dialog()).props('size=sm color=green')
                        
                        # 内容区域：双容器（列表/图谱）
                        with ui.element('div').classes('w-full').style('height: calc(100vh - 200px); position: relative;'):
                            # 1. 列表容器 (绑定可见性)
                            with ui.scroll_area().classes('w-full h-full').bind_visibility_from(ui_refs['loc_view_mode'], 'text', backward=lambda x: x == 'list'):
                                ui_refs['loc_container'] = ui.column().classes('w-full p-1')
                            
                            # 2. 地图容器 (绑定可见性)
                            with ui.element('div').classes('w-full h-full').bind_visibility_from(ui_refs['loc_view_mode'], 'text', backward=lambda x: x == 'graph'):
                                ui_refs['loc_graph_container'] = ui.column().classes('w-full h-full')
                            
                            # 初始刷新
                            settings.refresh_loc_ui()
                
                with ui.tab_panel(t_config).classes('h-full p-2'):
                    with ui.column().classes('w-full h-full'):
                        # 使用 calc 计算高度，减去顶部导航栏和 Tab 栏的大致高度(约200px)
                        # 这种写法绝对不会塌陷
                        with ui.scroll_area().classes('w-full').style('height: calc(100vh - 200px);'):
                            ui_refs['config_container'] = ui.column().classes('w-full')
                            settings.refresh_config_ui()

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